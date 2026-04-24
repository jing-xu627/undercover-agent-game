"""
AI Agent implementation using LLM for reasoning and decision making.

This agent encapsulates the existing LLM-based strategy logic from the strategy module.
"""

import asyncio
from typing import Any, Dict, List, Optional, cast

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage, SystemMessage

from game.agents.base import AgentType, GameEvent, PlayerAgent, SpeechContext, VoteContext
from game.common.schema import PlayerMindset, SelfBelief, Speech
from game.strategy.builders.context_builder import build_inference_user_context
from game.strategy.builders.prompt_builder import format_inference_system_prompt
from game.strategy.llm_schemas import PlayerMindsetModel, SelfBeliefModel
from game.strategy.strategy_core import (
    llm_generate_speech,
    llm_decide_vote,
    plan_player_speech,
    _invoke_async,
)
from game.strategy.utils.logging_utils import log_self_belief_update
from game.utils.logger import get_logger
from game.graph.state import GameState
from game.agent_tools.speech_tools import speech_planning_tools

logger = get_logger(__name__)


class AIAgent(PlayerAgent):
    """
    AI-controlled player agent.
    
    Uses LLM for:
    - Identity inference and mindset updates
    - Strategic speech planning and generation
    - Evidence-based voting decisions
    """

    def __init__(
        self,
        player_id: str,
        name: str,
        llm_client: Any,
        personality: Optional[str] = None,
    ):
        super().__init__(player_id, name)
        self._llm_client = llm_client
        self._personality = personality or "balanced"  # aggressive, cautious, deceptive, etc.

    @property
    def agent_type(self) -> AgentType:
        return AgentType.AI

    async def speak(self, context: SpeechContext) -> str:
        """
        Generate speech using LLM strategy.
        
        Flow:
        1. Update mindset based on game history
        2. Generate speech plan (clarity, goal, suspects)
        3. Generate actual speech text
        """
        logger.info("AIAgent %s generating speech for round %d", self._player_id, context.current_round)

        # Step 1: Update mindset with LLM inference
        await self._update_mindset(context)

        # Step 2: Generate speech plan
        try:
            speech_plan = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: plan_speech_from_context(context, self._mindset)
            )
        except Exception as exc:
            logger.warning("Speech planning failed for %s: %s", self._player_id, exc)
            speech_plan = None

        # Step 3: Generate speech with LLM
        try:
            speech_text = await llm_generate_speech(
                llm_client=self._llm_client,
                my_word=self._word or context.my_word,
                self_belief=self._mindset.get("self_belief", {}),
                suspicions=self._mindset.get("suspicions", {}),
                completed_speeches=context.completed_speeches,
                me=self._player_id,
                alive=context.alive_players,
                current_round=context.current_round,
                speech_plan=speech_plan,
            )
            logger.info("AIAgent %s speech: %s", self._player_id, speech_text[:50])
            return speech_text
        except Exception as exc:
            logger.error("Speech generation failed for %s: %s", self._player_id, exc)
            # Fallback: simple description
            return f"I think the word relates to {self._word or 'something familiar'}."

    async def vote(self, context: VoteContext) -> str:
        """
        Generate vote using LLM strategy.
        
        Returns the player_id to vote for.
        """
        logger.info("AIAgent %s voting in round %d", self._player_id, context.current_round)

        try:
            # Build minimal state for vote function
            
            minimal_state: GameState = {
                "game_id": "voting",
                "players": context.alive_players + [context.player_id],
                "game_phase": "voting",
                "current_round": context.current_round,
                "completed_speeches": [],
                "votes": [],
                "eliminated": [],
                "host_private_state": {},
                "player_private_states": {context.player_id: self._mindset},
            }

            vote_target = await llm_decide_vote(
                llm_client=self._llm_client,
                state=minimal_state,
                me=self._player_id,
                my_word=self._word or context.self_belief.get("word", ""),
                current_mindset=self._mindset,
            )
            logger.info("AIAgent %s votes for %s", self._player_id, vote_target)
            return vote_target
        except Exception as exc:
            logger.error("Vote generation failed for %s: %s", self._player_id, exc)
            # Fallback: vote for first other player
            for pid in context.alive_players:
                if pid != self._player_id:
                    return pid
            return context.alive_players[0] if context.alive_players else self._player_id

    async def observe(self, event: GameEvent) -> None:
        """
        Process game events.
        
        For AI agents, this can be used to:
        - Log events for debugging
        - Trigger incremental mindset updates (optional optimization)
        """
        logger.debug(
            "AIAgent %s observed event: %s at %s",
            self._player_id,
            event.type,
            event.timestamp
        )
        
        # Optionally update mindset incrementally based on events
        if event.type == "speech":
            # Could trigger lightweight mindset update here
            pass
        elif event.type == "elimination":
            # Mark eliminated player in mindset
            eliminated_player = event.data.get("eliminated_player")
            if eliminated_player:
                logger.info("AIAgent %s noted elimination of %s", self._player_id, eliminated_player)

    def _to_mindset_model(
        self,
        mindset: PlayerMindset | PlayerMindsetModel | None,
    ) -> PlayerMindsetModel:
        """Convert shared-state mindset data into a Pydantic model."""
        if isinstance(mindset, PlayerMindsetModel):
            return mindset

        if mindset is None:
            return PlayerMindsetModel(
                self_belief=SelfBeliefModel(role="civilian", confidence=0.5),
                suspicions={},
            )

        if hasattr(mindset, "model_dump"):
            return PlayerMindsetModel(**mindset.model_dump())

        return PlayerMindsetModel(**cast(Dict[str, Any], mindset))

    def _mindset_model_to_state(self, model: PlayerMindsetModel) -> PlayerMindset:
        """Convert a Pydantic mindset model into the plain dict state form."""
        return cast(PlayerMindset, model.model_dump())


    async def _update_mindset(self, context: SpeechContext) -> None:
        """Internal: Update agent's mindset using LLM inference."""
        try:
            existing_model = self._to_mindset_model(self._mindset)
            existing_state = self._mindset_model_to_state(existing_model)
            existing_self_belief = existing_state.get(
                "self_belief", {"role": "civilian", "confidence": 0.5}
            )

            players = context.alive_players + [self._player_id]
            alive = context.alive_players

            # 1. Format the system prompt (instructions)
            system_prompt = format_inference_system_prompt(
                my_word=self._word or context.my_word,
                player_count=len(players),
                spy_count=context.undercover_num,
            )

            # 2. Build the user context (structured, dynamic state)
            user_context = build_inference_user_context(
                context.completed_speeches, players, alive, self._player_id, existing_state
            )

            # 3. Create agent with ToolStrategy for structured output
            response_format = ToolStrategy(
                schema=PlayerMindsetModel,
                tool_message_content="Player mindset captured.",
            )

            agent = create_agent(
                model=self._llm_client,
                tools=[],
                response_format=response_format,
            )

            # 4. Invoke agent
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_context),
            ]
            result = await _invoke_async(agent, {"messages": messages})

            # 5. Extract structured response
            structured = result.get("structured_response")

            if structured:
                if not isinstance(structured, PlayerMindsetModel):
                    structured = PlayerMindsetModel.model_validate(structured)
                new_state = self._mindset_model_to_state(structured)
                log_self_belief_update(
                    self._player_id,
                    existing_self_belief,
                    new_state.get("self_belief", {"role": "civilian", "confidence": 0.5}),
                )
                self._mindset = new_state
                logger.debug("AIAgent %s mindset updated", self._player_id)
            else:
                # No structured response, preserve existing
                log_self_belief_update(
                    self._player_id, existing_self_belief, existing_self_belief
                )

        except Exception as exc:
            logger.warning("Mindset update failed for %s: %s", self._player_id, exc)
            # Keep existing mindset


def plan_speech_from_context(
    context: SpeechContext,
    mindset: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Wrapper to call speech planning without needing full GameState.
    
    Creates minimal state representation for the planning tool.
    """

    # Create minimal state for planning tool
    minimal_state: GameState = {
        "game_id": "planning",
        "players": context.alive_players + [context.player_id],
        "game_phase": "speaking",
        "current_round": context.current_round,
        "completed_speeches": list(context.completed_speeches),
        "votes": [],
        "eliminated": [],
        "host_private_state": {},
        "player_private_states": {context.player_id: mindset},
    }

    try:
        tools = speech_planning_tools(
            minimal_state,
            context.player_id,
            mindset_overrides={context.player_id: mindset},
        )
        planner = tools[0]
        return planner.func()
    except Exception as exc:
        logger.warning("Speech planning tool failed: %s", exc)
        return {}
