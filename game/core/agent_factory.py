
from game.agents.base import PlayerAgent
from game.utils.logger import get_logger
from game.agents.human_agent import HumanAgent, get_human_agent_manager
from game.agents.ai_agent import AIAgent
from game.common.llm_client import get_llm_client

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


def create_agents_from_config(
    player_ids: List[str],
    human_player_ids: List[str] = None,
) -> Dict[str, PlayerAgent]:
    """
    Create PlayerAgent instances from configuration.
    
    Args:
        player_ids: List of all player IDs
        human_player_ids: Optional list of player IDs that are human
        
    Returns:
        Dictionary mapping player_id to PlayerAgent
    """
    
    agents: Dict[str, PlayerAgent] = {}
    human_ids = set(human_player_ids or [])
    
    manager = get_human_agent_manager()
    
    llm_client = get_llm_client()
    for player_id in player_ids:
        if player_id in human_ids:
            # Create human agent
            agent = HumanAgent(
                player_id=player_id,
                name=player_id,
                manager=manager,
            )
            manager.register_agent(agent)
            logger.info("Created HumanAgent for %s", player_id)
        else:
            # Create AI agent
            agent = AIAgent(
                player_id=player_id,
                name=player_id,
                llm_client=llm_client,
            )
            logger.info("Created AIAgent for %s", player_id)
        
        agents[player_id] = agent
    
    return agents


