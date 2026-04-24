
from game.agents.base import PlayerAgent
from game.utils.logger import get_logger

logger = get_logger(__name__)

# Multi-game agent registry: game_id -> {player_id -> PlayerAgent}
_agent_registry: dict[str, dict[str, PlayerAgent]] = {}


def get_agent_registry(game_id: str) -> dict[str, PlayerAgent]:
    """Get or create agent registry for a specific game."""
    if game_id not in _agent_registry:
        _agent_registry[game_id] = {}
    return _agent_registry[game_id]


def set_game_agents(game_id: str, agents: list[PlayerAgent]) -> None:
    """Register agents for a game."""
    _agent_registry[game_id] = {agent.player_id: agent for agent in agents}
    logger.info(f"Registered {len(agents)} agents for game {game_id}")


def get_game_agents(game_id: str) -> list[PlayerAgent]:
    """Get all agents for a game."""
    registry = get_agent_registry(game_id)
    return list(registry.values())


def clear_game_agents(game_id: str) -> None:
    """Clear agents for a game (cleanup after game ends)."""
    if game_id in _agent_registry:
        del _agent_registry[game_id]
        logger.info(f"Cleared agents for game {game_id}")


