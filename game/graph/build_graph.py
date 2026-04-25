"""
LangGraph workflow orchestrator.

This module defines the main state machine that orchestrates the game flow:
- Game setup and role assignment
- speaking phases
- voting phases
- Game state transitions and win condition checking

The workflow is built using LangGraph's StateGraph with conditional routing
between different phases of the game.

Architecture:
- StateGraph manages the overall game state transitions
- Conditional edges route between speaking and voting phases
- Concurrent execution for voting, sequential for speaking
- Private state management for player mindsets and game setup
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from game.utils.logger import get_logger
from game.graph.nodes.master_node import host_setup, host_judge, game_over
from game.graph.nodes.vote_node import collect_voting_phase
from game.graph.nodes.speech_node import collect_speeches_phase
from game.graph.state import GameState

logger = get_logger(__name__)

def continue_next_round(state: GameState) -> str:
    winner = state.get("winner")
    if winner:
        return "end"
    else:
        return "next_round"

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
    workflow.add_node("agents_speaking", collect_speeches_phase)
    workflow.add_node("agents_voting", collect_voting_phase)
    workflow.add_node("host_judge", host_judge)
    workflow.add_node("game_over", game_over)

    # Define routing
    workflow.set_entry_point("host_setup")
    workflow.add_edge("host_setup", "agents_speaking")
    workflow.add_edge("agents_speaking", "agents_voting")
    workflow.add_edge("agents_voting", "host_judge")

    # Game end check
    workflow.add_conditional_edges(
        "host_judge",
        continue_next_round,
        {
            "next_round": "agents_speaking", 
            "end": "game_over"
        },
    )
    workflow.add_edge("game_over", END)

    memory = checkpointer or MemorySaver()
    app = workflow.compile(checkpointer=memory)
    app = app.with_config({"recursion_limit": 500})

    return app

