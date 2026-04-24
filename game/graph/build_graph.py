"""
LangGraph workflow orchestrator for the "Who Is Spy" game.

This module defines the main state machine that orchestrates the game flow:
- Game setup and role assignment
- Sequential speaking phases
- Concurrent voting phases
- Game state transitions and win condition checking

The workflow is built using LangGraph's StateGraph with conditional routing
between different phases of the game.

Architecture:
- StateGraph manages the overall game state transitions
- Conditional edges route between speaking and voting phases
- Concurrent execution for voting, sequential for speaking
- Private state management for player mindsets and game setup
"""

import asyncio
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from game.utils.logger import get_logger
from game.graph.nodes.master_node import host_setup, host_stage_switch, host_result, host_judge
from game.graph.nodes.vote_node import dispatch_voting_phase
from game.graph.nodes.speech_node import dispatch_speaking_phase
from game.graph.state import GameState, next_alive_player

logger = get_logger(__name__)

def should_continue(state: GameState) -> str:
    """Determine if the game should continue or end.

    This conditional function is used by the host_result node to decide
    whether the game should proceed to another round or end.

    Args:
        state: Current game state

    Returns:
        "end" if there's a winner, "continue" otherwise
    """
    return "end" if state.get("winner") else "continue"
  
# Conditional routing from host_stage_switch
def route_from_stage_with_agents(state: GameState) -> str:
    phase = state.get("game_phase")
    if phase == "speaking":
        return "agent_speaking_dispatch"
    elif phase == "voting":
        return "agent_voting_dispatch"
    else:
        return "host_result"

def build_agent_workflow(checkpointer=None):
    """Build Agent-based workflow supporting both AI and Human players.
    Uses the Agent abstraction layer,
    allowing both AI and Human players to participate in the same game.

    Args:
        checkpointer: Optional checkpointer for state persistence

    Returns:
        Compiled LangGraph application with Agent support
    """

    # Store agents in a way that nodes can access them
    # We'll use a simple global registry for this example
    #_agent_registry.clear()
    #_agent_registry.update(agents)
    workflow = StateGraph(GameState)
    
    workflow.add_node("host_setup", host_setup)
    workflow.add_node("host_stage_switch", host_stage_switch)
    workflow.add_node("host_result", host_result)
    workflow.add_node("host_judge", host_judge)

    workflow.add_node("agent_speaking_dispatch", dispatch_speaking_phase)
    workflow.add_node("agent_voting_dispatch", dispatch_voting_phase)

    # Define routing
    workflow.set_entry_point("host_setup")
    workflow.add_edge("host_setup", "host_stage_switch")

    workflow.add_conditional_edges(
        "host_stage_switch",
        route_from_stage_with_agents,
        {
            "agent_speaking_dispatch": "agent_speaking_dispatch",
            "agent_voting_dispatch": "agent_voting_dispatch",
            "host_result": "host_result",
        },
    )

    # Speaking dispatch returns to stage switch
    workflow.add_edge("agent_speaking_dispatch", "host_stage_switch")

    # Voting dispatch directly goes to result (dispatch_voting_phase already collects all votes)
    workflow.add_edge("agent_voting_dispatch", "host_result")

    # Game end check
    workflow.add_conditional_edges(
        "host_result",
        should_continue,
        {"continue": "host_stage_switch", "end": "host_judge"},
    )

    # Game end notification then end
    workflow.add_edge("host_judge", END)

    memory = checkpointer or MemorySaver()
    app = workflow.compile(checkpointer=memory)
    app = app.with_config({"recursion_limit": 500})

    return app

