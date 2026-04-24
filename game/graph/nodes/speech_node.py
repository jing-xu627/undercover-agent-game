import asyncio
from datetime import datetime
from typing import Any, Dict, List, TYPE_CHECKING

from game.agents.base import PlayerAgent, SpeechContext, GameEvent
from game.utils.logger import get_logger
from game.graph.state import GameState, Speech, create_speech_record
from game.metrics import GameMetrics
from game.core.agent_factory import get_game_agents
from game.common.constant import GamePhase

if TYPE_CHECKING:
    from game.metrics import GameMetrics

logger = get_logger(__name__)

async def dispatch_speaking_phase(state: GameState) -> Dict[str, Any]:
    """
    Dispatch speaking phase to all alive agents.
    
    collects speeches from ALL alive agents concurrently. 
    The order of speeches in the result reflects the order
    they were received (not turn order).
    """
    if state["game_phase"] != GamePhase.SPEAKING:
        return {}

    current_round = state["current_round"]
    game_id = state.get("game_id", "")

    agents = get_game_agents(game_id)
    alive_ids = [agent.player_id for agent in agents if agent.is_alive]
    
    logger.info(f"Dispatching speaking phase for round {current_round}" +
                    f"alive player num: {len(alive_ids)}")
    
    # Build context for each agent
    async def collect_speech_from_agent(agent: PlayerAgent) -> tuple[str, str, Dict]:
        """Collect speech from a single agent. Returns (player_id, speech, mindset)."""
        context = SpeechContext(
            player_id=agent.player_id,
            my_word=agent.word or "",
            current_round=current_round,
            completed_speeches=state.get("completed_speeches", []),
            alive_players=alive_ids,
            self_belief=agent.mindset.get("self_belief", {}),
            suspicions=agent.mindset.get("suspicions", {}),
            undercover_num=state.get("undercover_num", 1),
        )
        
        try:
            speech_text = await agent.speak(context)
            return agent.player_id, speech_text, agent.mindset
        except Exception as exc:
            logger.error("Agent %s failed to speak: %s", agent.player_id, exc)
            # Fallback speech
            return agent.player_id, f"I'm not sure about the word.", agent.mindset
    
    # Collect all speeches concurrently
    alive_agents = [agent for agent in agents if agent.is_alive]
    tasks = [collect_speech_from_agent(agent) for agent in alive_agents]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    speeches: List[Speech] = []
    player_private_states: Dict[str, Dict] = {}
    
    agents_id_map = {agent.player_id: agent for agent in agents}
    for result in results:
        if isinstance(result, Exception):
            logger.error("Speech collection error: %s", result)
            continue
            
        player_id, speech_text, mindset = result
        
        # Create speech record
        speech_record = create_speech_record(
            state=state,
            player_id=player_id,
            content=speech_text,
        )
        speeches.append(speech_record)
        
        # Save mindset to private state
        player_private_states[player_id] = {
            "mindset": mindset,
            "word": agents_id_map[player_id].word,
            "role": agents_id_map[player_id].role,
        }
        
        # Record metrics
        metrics = GameMetrics()
        if metrics.enabled:
            metrics.on_speech(
                game_id=state.get("game_id"),
                round_number=current_round,
                player_id=player_id,
                content=speech_text,
            )
            metrics.on_player_mindset_update(
                game_id=state.get("game_id"),
                round_number=current_round,
                phase="speaking",
                player_id=player_id,
                mindset=mindset,
            )
        
        logger.info("Collected speech from %s: %s", player_id, speech_text[:50])
    
    # Broadcast events to all agents (so they know what others said)
    for speech in speeches:
        event = GameEvent(
            type="speech",
            timestamp=datetime.now(),
            data={
                "player_id": speech["player_id"],
                "content": speech["content"],
                "round": current_round,
            }
        )
        for agent in alive_agents:
            try:
                await agent.observe(event)
            except Exception as exc:
                logger.warning("Failed to notify agent %s: %s", agent.player_id, exc)
    
    return {
        "completed_speeches": speeches,
        "player_private_states": player_private_states,
    }

