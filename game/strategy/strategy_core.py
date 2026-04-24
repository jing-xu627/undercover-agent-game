"""
Core strategy coordination for LLM-powered game intelligence.

Coordinates prompt building, context construction, and LLM interaction
for player mindset updates and speech generation.
"""

import asyncio
import inspect
from typing import Any, List, Dict, Sequence, cast
from venv import logger

from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from game.agent_tools.vote_tools import vote_tools
from game.agent_tools.speech_tools import speech_planning_tools
from game.graph.state import (
    GameState,
    alive_players,
)
from game.common.schema import PlayerMindset, SelfBelief, Speech
from game.strategy.builders.context_builder import (
    build_inference_user_context,
    build_speech_user_context,
    build_vote_user_context,
)
from game.strategy.utils.logging_utils import log_self_belief_update
from game.strategy.llm_schemas import (
    PlayerMindsetModel,
    SelfBeliefModel,
    VoteDecisionModel,
)
from game.strategy.builders.prompt_builder import (
    format_inference_system_prompt,
    format_speech_system_prompt,
    format_vote_system_prompt,
)
from game.strategy.utils.text_utils import sanitize_speech_output


async def _invoke_async(target: Any, *args: Any, **kwargs: Any) -> Any:
    """Awaitably invoke LangChain runnables, falling back to sync methods."""
    ainvoke = getattr(target, "ainvoke", None)
    if callable(ainvoke):
        result = ainvoke(*args, **kwargs)
        return await result if inspect.isawaitable(result) else result

    invoke = getattr(target, "invoke", None)
    if callable(invoke):
        return await asyncio.to_thread(invoke, *args, **kwargs)

    raise AttributeError(f"Object {target!r} has neither ainvoke nor invoke.")


async def llm_generate_speech(
    llm_client: Any,
    my_word: str,
    self_belief: SelfBelief,
    suspicions: Dict[str, Any],
    completed_speeches: Sequence[Speech],
    me: str,
    alive: List[str],
    current_round: int,
    speech_plan: Dict[str, Any] | None = None,
) -> str:
    """
    Use LLM to generate a strategic speech based on current beliefs.

    Args:
        llm_client: Language model client
        my_word: Player's assigned word
        self_belief: Current belief about own role
        suspicions: Suspicions about other players (unused but kept for API compatibility)
        completed_speeches: History of all speeches
        me: Current player's ID
        alive: Currently alive player IDs
        current_round: Current game round number
        speech_plan: Optional structured plan produced by plan_speech tool

    Returns:
        Generated speech as a single-line string
    """
    system_prompt = format_speech_system_prompt(my_word, self_belief)
    user_context = build_speech_user_context(
        self_belief,
        completed_speeches,
        me,
        alive,
        current_round,
        speech_plan=speech_plan,
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_context),
    ]

    response = await _invoke_async(llm_client, messages)

    raw_text = response.content if hasattr(response, "content") else response
    return sanitize_speech_output(raw_text)


def plan_player_speech(
    state: GameState,
    me: str,
    current_mindset: PlayerMindset,
) -> Dict[str, Any]:
    """
    Produce a structured speech plan using the planning tool.

    This helper lets callers experiment with planning without yet wiring the
    result into the speech generation prompt/agent.
    """
    planner_tools = speech_planning_tools(
        state,
        me,
        mindset_overrides={me: current_mindset},
    )
    planner = planner_tools[0]
    return planner.func()


async def llm_decide_vote(
    llm_client: Any,
    state: GameState,
    me: str,
    my_word: str,
    current_mindset: PlayerMindset,
) -> str:
    """
    Use LLM with voting tools to decide which player to vote for.

    Args:
        llm_client: Language model client
        state: Current shared game state
        me: Current player's ID
        my_word: Player's assigned word
        current_mindset: Player's latest mindset state

    Returns:
        Player ID selected as the vote target
    """
    # Pass the freshly inferred mindset so vote heuristics reflect the latest suspicions.
    tools = vote_tools(
        state,
        me,
        mindset_overrides={me: current_mindset},
    )
    response_format = ToolStrategy(
        schema=VoteDecisionModel,
        tool_message_content="Vote decision captured.",
    )

    agent = create_agent(
        model=llm_client,
        tools=tools,
        response_format=response_format,
    )

    alive_now = alive_players(state)
    system_prompt = format_vote_system_prompt(
        my_word=my_word,
        alive_count=len(alive_now),
        current_round=state.get("current_round", 0),
    )
    vote_context = build_vote_user_context(
        alive=alive_now,
        me=me,
        current_mindset=current_mindset,
        current_round=state.get("current_round", 0),
    )

    try:
        result = await _invoke_async(
            agent,
            {
                "messages": [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=vote_context),
                ]
            },
        )
        structured = result.get("structured_response")
        if structured:
            if not isinstance(structured, VoteDecisionModel):
                structured = VoteDecisionModel.model_validate(structured)
            return structured.target
    except Exception as exc:
        logger.exception("LLM vote decision failed: %s", exc)

    # Fallback: choose the first other alive player or self if alone
    alternatives = [pid for pid in alive_now if pid != me]
    if alternatives:
        return alternatives[0]
    return me
