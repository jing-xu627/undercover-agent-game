
from game.core.rules import assign_roles_and_words, calculate_eliminated_player, determine_winner
from game.graph.state import GameState, next_alive_player, generate_phase_id
from game.agents.human_agent import HumanAgent, get_human_agent_manager
from game.agents.base import PlayerAgent, GameEvent
from typing import List, Dict
from game.common.config import load_config
from game.utils.logger import get_logger
from datetime import datetime, timezone
from game.core.agent_factory import get_game_agents


logger = get_logger(__name__)

async def host_setup(state: GameState) -> dict:
    """Host setup that also assigns roles to agents."""

    host_private_state = state.get("host_private_state", {})
    game_id = state.get("game_id", "")

    agents = get_game_agents(game_id)
    assignments = assign_roles_and_words(
        player_agents=agents,
        word_list=load_config().vocabulary,
        host_private_state=host_private_state,
    )

    # Assign to agents (async to notify human players)
    await assign_roles_to_agents(agents, assignments)

    return {
        **assignments,
        "game_phase": "speaking",
        "current_round": 1,
    }

async def assign_roles_to_agents(
    agents: List[PlayerAgent],
    assignments: Dict[str, Any],
) -> None:
    """
    Assign roles and words to agents.

    Args:
        agents: List of PlayerAgent instances
        assignments: Contains host_private_state and player_private_states
    """

    manager = get_human_agent_manager()
    host_private_state = assignments.get("host_private_state", {})
    player_private_states = assignments.get("player_private_states", {})
    player_roles = host_private_state.get("player_roles", {})

    for agent in agents:
        player_id = agent.player_id
        player_state = player_private_states.get(player_id, {})
        word = player_state.get("assigned_word", "")
        role = player_roles.get(player_id, "civilian")

        agent.assign_role_and_word(role, word)
        logger.debug("Assigned %s as %s with word %s", player_id, role, word)

        # Notify human agents of their role
        if isinstance(agent, HumanAgent):
            await manager.notify_role_reveal(player_id, role, word)



async def host_result(state: GameState) -> dict:
    """
    Host result that calculates elimination after voting.
    This is called after voting phase to determine who is eliminated.
    """
    logger.info("Current round %d votes: %s", 
        state.get("current_round", 0), state.get("current_votes", {})
    )
    eliminated_player = calculate_eliminated_player(state)

    logger.info(
        "Host round %d voted out player: %s",
        state.get("current_round", 0),
        eliminated_player,
    )
    
    # Create temp state to check for winner after elimination
    temp_state = state.copy()
    if eliminated_player:
        temp_state["eliminated_players"] = state.get("eliminated_players", []) + [eliminated_player]

    host_private_state = state.get("host_private_state", {})
    winner = determine_winner(temp_state, host_private_state)

    if winner:
        logger.info("Winner determined: %s", winner)
        return {
            "game_phase": "result",
            "winner": winner,
            "eliminated_players": [eliminated_player] if eliminated_player else [],
        }

    # No winner, continue to next round
    logger.info("No winner; advancing to round %d", state.get("current_round", 0) + 1)
    updates = {
        "game_phase": "speaking",
        "current_round": state.get("current_round", 0) + 1,
        "current_votes": {},
        "phase_id": generate_phase_id(state),
    }
    if eliminated_player:
        updates["eliminated_players"] = state.get("eliminated_players", []) + [eliminated_player]
        # Notify agents of elimination
        game_id = state.get("game_id", "")
        agents = get_game_agents(game_id)
        await notify_elimination(agents, eliminated_player)

    return updates


async def notify_elimination(agents: List[PlayerAgent], eliminated_player: str) -> None:
    """Notify all alive agents about player elimination and update eliminated player status."""

    event = GameEvent(
        type="elimination",
        timestamp=datetime.now(timezone.utc),
        data={"eliminated_player": eliminated_player}
    )

    for agent in agents:
        # Set eliminated player's is_alive to False
        if agent.player_id == eliminated_player:
            agent.is_alive = False
            continue
        if agent.is_alive and agent.player_id != eliminated_player:
            try:
                await agent.observe(event)
            except Exception as exc:
                logger.warning("Failed to notify agent %s of elimination: %s", agent.player_id, exc)


async def host_judge(state: GameState) -> dict:
    """Host result that notifies agents of game end."""
    winner = state.get("winner")
    game_id = state.get("game_id", "")
    agents = get_game_agents(game_id)
    if winner:
        await notify_game_end(agents, winner, state)
    return {}

async def host_stage_switch(state: GameState) -> dict:
    """Switch phase and notify agents of new round."""
    phase = state.get("game_phase")
    game_id = state.get("game_id", "")
    agents = get_game_agents(game_id)
    current_round = state.get("current_round", 0)

    if phase == "setup":
        # First transition: setup -> speaking (round 1)
        return {"game_phase": "speaking", "current_round": 1}
    elif phase == "speaking":
        # Check if all alive players have spoken this round
        if next_alive_player(state) is None:
            # Speaking done -> move to voting
            return {"game_phase": "voting", "phase_id": generate_phase_id(state)}
        # Still have players who need to speak - let router go to agent_speaking_dispatch
        return {}
    elif phase == "voting":
        # Check if game already ended (should not reach here, but handle gracefully)
        if state.get("winner"):
            return {"game_phase": "result"}
        # Voting done -> notify and move to next round speaking
        # Note: current_round is already incremented by host_result
        await notify_new_round(agents, current_round)
        return {"game_phase": "speaking", "phase_id": generate_phase_id(state)}

    return {}


async def notify_new_round(
    agents: List[PlayerAgent],
    round_number: int,
) -> None:
    """Notify all agents about new round."""
    event = GameEvent(
        type="new_round",
        timestamp=datetime.now(timezone.utc),
        data={"round": round_number}
    )
    
    for agent in agents:
        if agent.is_alive:
            try:
                await agent.observe(event)
            except Exception as exc:
                logger.warning("Failed to notify agent %s of new round: %s", agent.player_id, exc)


async def notify_game_end(
    agents: List[PlayerAgent],
    winner: str,
    state: GameState,
) -> None:
    """Notify all agents about game end."""
    host_private_state = state.get("host_private_state", {})
    player_roles = host_private_state.get("player_roles", {})
    spy_word = host_private_state.get("spy_word")
    civilian_word = host_private_state.get("civilian_word")

    # Find spy player
    spy_player = None
    for player_id, role in player_roles.items():
        if role == "spy":
            spy_player = player_id
            break

    event = GameEvent(
        type="game_end",
        timestamp=datetime.now(timezone.utc),
        data={
            "winner": winner,
            "spy_player": spy_player,
            "spy_word": spy_word,
            "civilian_word": civilian_word,
            "final_state": {
                "eliminated": state.get("eliminated_players", []),
                "alive": [p for p in state["players"] if p not in state.get("eliminated_players", [])],
            }
        }
    )
    
    for agent in agents:
        try:
            await agent.observe(event)
        except Exception as exc:
            logger.warning("Failed to notify agent %s of game end: %s", agent.player_id, exc)
