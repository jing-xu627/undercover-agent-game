
from typing import Dict, List

from game.utils.logger import get_logger
from game.agents.human_agent import PlayerAgent, HumanAgent, get_human_agent_manager
from game.agents.ai_agent import AIAgent
from game.tools.llm import get_llm_client

logger = get_logger(__name__)

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


async def assign_roles_to_agents(
    agents: Dict[str, PlayerAgent],
    assignments: Dict[str, Dict[str, str]],
) -> None:
    """
    Assign roles and words to agents.
    
    Args:
        agents: Dictionary of PlayerAgent instances
        assignments: Mapping from player_id to {role, word}
    """
    
    manager = get_human_agent_manager()
    
    for player_id, agent in agents.items():
        if player_id in assignments:
            role = assignments[player_id]["role"]
            word = assignments[player_id]["word"]
            agent.assign_role_and_word(role, word)
            logger.debug("Assigned %s as %s with word %s", player_id, role, word)
            
            # Notify human agents of their role
            if isinstance(agent, HumanAgent):
                await manager.notify_role_reveal(player_id, role, word)
