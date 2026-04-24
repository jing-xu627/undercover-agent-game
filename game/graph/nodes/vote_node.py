import asyncio
from datetime import datetime
from typing import Any, Dict

from game.agents.base import PlayerAgent, VoteContext, GameEvent
from game.utils.logger import get_logger
from game.graph.state import GameState, Vote
from game.common.constant import GamePhase
import random
from game.core.agent_factory import get_game_agents

logger = get_logger(__name__)


async def dispatch_voting_phase(state: GameState) -> Dict[str, Any]:
    """
    Dispatch voting phase to all alive agents.
    
    Collects votes from all alive agents concurrently.
    
    """
    if state["game_phase"] != GamePhase.VOTING:
        return {}
    
    current_round = state["current_round"]
    game_id = state.get("game_id", "")
    agents = get_game_agents(game_id)
    alive = [agent.player_id for agent in agents if agent.is_alive]
    
    logger.info("Dispatching voting phase for round %d", current_round)
    
    async def collect_vote_from_agent(agent: PlayerAgent) -> tuple[str, str]:
        """Collect vote from a single agent. Returns (player_id, vote_target)."""
        context = VoteContext(
            player_id=agent.player_id,
            current_round=current_round,
            alive_players=alive,
            self_belief=agent.mindset.get("self_belief", {}),
            suspicions=agent.mindset.get("suspicions", {}),
            game_history=[],  # Could be populated from state
        )
        
        try:
            vote_target = await agent.vote(context)
            
            # Validate vote
            if vote_target not in alive:
                logger.warning("Agent %s voted for invalid target %s, randomizing",
                             agent.player_id, vote_target)
                
                valid_targets = [p for p in alive if p != agent.player_id]
                vote_target = random.choice(valid_targets) if valid_targets else alive[0]
            
            return agent.player_id, vote_target
            
        except Exception as exc:
            logger.error("Agent %s failed to vote: %s", agent.player_id, exc)
            # Random fallback
            valid_targets = [p for p in alive if p != agent.player_id]
            vote_target = random.choice(valid_targets) if valid_targets else alive[0]
            return agent.player_id, vote_target
    
    # Collect all votes concurrently
    alive_agents = [agent for agent in agents if agent.is_alive]
    tasks = [collect_vote_from_agent(agent) for agent in alive_agents]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    votes: Dict[str, Vote] = {}
    for result in results:
        if isinstance(result, Exception):
            logger.error("Vote collection error: %s", result)
            continue
            
        player_id, vote_target = result
        
        vote = Vote(
            target=vote_target,
            ts=int(datetime.now().timestamp() * 1000),
            phase_id=state.get("phase_id", ""),
        )
        votes[player_id] = vote
        
        logger.info("Collected vote from %s -> %s", player_id, vote_target)
    
    # Broadcast vote reveal event
    if votes:
        event = GameEvent(
            type="vote_reveal",
            timestamp=datetime.now(),
            data={
                "votes": [{"voter": pid, "target": v["target"]} for pid, v in votes.items()],
                "round": current_round,
            }
        )
        for agent in alive_agents:
            try:
                await agent.observe(event)
            except Exception as exc:
                logger.warning("Failed to notify agent %s: %s", agent.player_id, exc)
    
    return {"current_votes": votes}

