"""
AI Agent implementation using LLM for reasoning and decision making.

This agent encapsulates the existing LLM-based strategy logic from the strategy module.
"""

import asyncio
from typing import Any, Dict, List, Optional, cast, Sequence

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import HumanMessage, SystemMessage

from game.agents.base import AgentType, GameEvent, PlayerAgent, SpeechContext, VoteContext
from game.common.schema import PlayerMindset, SelfBelief, Speech
from game.utils.prompt_builder import (
    format_inference_system_prompt,
    format_vote_system_prompt,
    format_speech_system_prompt,
)
from game.common.llm_schemas import PlayerMindsetModel, VoteDecisionModel
from game.utils.context_builder import (
    build_speech_user_context,
    build_inference_user_context,
    build_vote_user_context,
)
from game.agents.tools.vote_tools import vote_tools
from game.utils.logging_utils import log_self_belief_update
from game.utils.logger import get_logger
from game.graph.state import GameState, alive_players
from game.core.speech_strategy import speech_planning_tools
from game.utils.text_utils import sanitize_speech_output

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
        self._base_agent = create_agent(model=llm_client)

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

        logger.debug(f"Speech plan for {self._player_id}: {speech_plan}")
        # Step 3: Generate speech with LLM
        try:
            speech_text = await self.generate_speech_content(
                completed_speeches=context.completed_speeches,
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

    
    async def generate_speech_content(
        self,
        completed_speeches: Sequence[Speech],
        alive: List[str],
        current_round: int,
        speech_plan: Dict[str, Any] | None = None,
    ) -> str:
        """
        Use LLM to generate a strategic speech based on current beliefs.

        Args:
            completed_speeches: History of all speeches
            alive: Currently alive player IDs
            current_round: Current game round number
            speech_plan: Optional structured plan produced by plan_speech tool

        Returns:
            Generated speech as a single-line string
        """
        self_belief = self._mindset.get("self_belief", {})  
                
        system_prompt = format_speech_system_prompt(self._word, self_belief)
        user_context = build_speech_user_context(
            self_belief,
            completed_speeches,
            self._player_id,
            alive,
            current_round,
            speech_plan=speech_plan,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_context),
        ]
        result = await self._base_agent.ainvoke({"messages": messages})
        # Extract content from result - could be AIMessage or dict with messages array
        if hasattr(result, "content"):
            res_raw_text = result.content
        elif isinstance(result, dict) and "messages" in result:
            last_message = result["messages"][-1]
            res_raw_text = last_message.content if hasattr(last_message, "content") else str(last_message)
        else:
            res_raw_text = str(result)
        return sanitize_speech_output(res_raw_text)


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
                "players": context.alive_players,
                "game_phase": "voting",
                "current_round": context.current_round,
                "completed_speeches": [],
                "votes": [],
                "eliminated": [],
                "host_private_state": {},
                "player_private_states": {self._player_id: self._mindset},
            }

            vote_target = await self.llm_decide_vote(
                state=minimal_state,
                current_mindset=self._mindset,
            )
            logger.info("AIAgent %s votes for %s", self._player_id, vote_target)
            return vote_target
        except Exception as exc:
            logger.error("Vote generation failed for %s: %s", self._player_id, exc)
            # Fallback: vote for first other player
            other_alives = [pid for pid in context.alive_players if pid != self._player_id]
            return random.choice(other_alives)

    async def llm_decide_vote(
        self,
        state: GameState,
        current_mindset: PlayerMindset,
    ) -> str:
        """
        Use LLM with voting tools to decide which player to vote for.

        Args:
            state: Current shared game state
            current_mindset: Player's latest mindset state

        Returns:
            Player ID selected as the vote target
        """
        # Pass the freshly inferred mindset so vote heuristics reflect the latest suspicions.
        tools = vote_tools(
            state,
            self._player_id,
            mindset_overrides={self._player_id: current_mindset},
        )
        response_format = ToolStrategy(
            schema=VoteDecisionModel,
            tool_message_content="Vote decision captured.",
        )

        my_word=self._word

        alive_now = alive_players(state)
        system_prompt = format_vote_system_prompt(
            my_word=my_word,
            alive_count=len(alive_now),
            current_round=state.get("current_round", 0),
        )
        vote_context = build_vote_user_context(
            alive=alive_now,
            me=self._player_id,
            current_mindset=current_mindset,
            current_round=state.get("current_round", 0),
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=vote_context),
        ]
        try:
            result = await self._base_agent.bind(tools=tools).ainvoke(
                {"messages": messages},
                response_format=response_format
            )
            structured = result.get("structured_response")
            if structured:
                if not isinstance(structured, VoteDecisionModel):
                    structured = VoteDecisionModel.model_validate(structured)
                return structured.target
        except Exception as exc:
            logger.exception("LLM vote decision failed: %s", exc)

        # Fallback: choose the first other alive player or self if alone
        alternatives = [pid for pid in alive_now if pid != self._player_id]
        if alternatives:
            return random.choice(alternatives)
        return self._player_id


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


    def _mindset_model_to_dict(self,
        mindset: PlayerMindset | PlayerMindsetModel | None,
    ) -> PlayerMindset:
        default_self_belief = {"role": "civilian", "confidence": 0.5}
        if mindset is None:
            return {
                "suspicions":{},
                "self_belief": default_self_belief,
            }
        
        if isinstance(mindset, PlayerMindsetModel):
            return cast(PlayerMindset, mindset.model_dump())
        
        # Ensure required fields exist with defaults
        if "self_belief" not in mindset or not mindset["self_belief"]:
            mindset["self_belief"] = default_self_belief
        if "suspicions" not in mindset:
            mindset["suspicions"] = {}
        return mindset


    async def _update_mindset(self, context: SpeechContext) -> None:
        """Internal: Update agent's mindset using LLM inference."""
        try:
            existing_mindset = self._mindset_model_to_dict(self._mindset)
            existing_self_belief = existing_mindset.get(
                "self_belief", {"role": "civilian", "confidence": 0.5}
            )

            # 1. Format the system prompt (instructions)
            system_prompt = format_inference_system_prompt(
                my_word=self._word or context.my_word,
                player_count=len(context.origin_players),
                alive_count=len(context.alive_players),
                spy_count=context.undercover_num,
            )

            # 2. Build the user context (structured, dynamic state)
            user_context = build_inference_user_context(
                context.completed_speeches, context.origin_players, 
                context.alive_players, self._player_id, existing_mindset
            )

            # 3. Create agent with ToolStrategy for structured output
            #response_format = ToolStrategy(schema=PlayerMindsetModel)

            # 4. Invoke agent
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_context),
            ]
            structured_llm = self._llm_client.with_structured_output(PlayerMindsetModel)
            result = await structured_llm.ainvoke(messages)

            new_mindset = self._mindset_model_to_dict(result)
            log_self_belief_update(
                self._player_id,
                existing_self_belief,
                new_mindset.get("self_belief", {"role": "civilian", "confidence": 0.5}),
            )
            self._mindset = new_mindset
            logger.debug("AIAgent %s mindset updated", self._player_id)

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
