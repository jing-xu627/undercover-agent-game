
from datetime import datetime
from typing import Any, Dict, List

from game.agents.base import PlayerAgent, SpeechContext, GameEvent
from game.utils.logger import get_logger
from game.graph.state import GameState, Speech, create_speech_record, generate_phase_id
from game.core.agent_factory import get_game_agents
from game.common.constant import GamePhase

logger = get_logger(__name__)

async def collect_speeches_phase(state: GameState) -> Dict[str, Any]:
    """
    Collect speeches from ALL alive agents sequentially. 
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
            origin_players=state.get("players", []),
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
    
    player_private_states = state["player_private_states"]
    speeches: List[Speech] = []

    # Collect speeches sequentially (one by one)
    alive_agents = [agent for agent in agents if agent.is_alive]
    for agent in alive_agents:
        result = await collect_speech_from_agent(agent)
        player_id, speech_text, mindset = result

        # Save mindset to private state
        player_private_states[player_id]["mindset"] = mindset
        
        # Create speech record
        speech_record = create_speech_record(
            state=state,
            player_id=player_id,
            content=speech_text,
        )
        speeches.append(speech_record)

        event = GameEvent(
            type="speech",
            timestamp=datetime.now(),
            data={
                "player_id": player_id,
                "content": speech_text,
                "round": current_round,
            }
        )
        for agent in alive_agents:
            try:
                if agent.player_id != player_id:
                    await agent.observe(event)
            except Exception as exc:
                logger.warning("Failed to notify agent %s: %s", agent.player_id, exc)
    
    return {
        "completed_speeches": speeches,
        "player_private_states": player_private_states,
        "game_phase": GamePhase.VOTING,
        "phase_id": generate_phase_id(current_round, GamePhase.VOTING),
    }

