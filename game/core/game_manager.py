from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from game.agents.base import PlayerAgent
from game.graph.state import GameState
from langchain_core.runnables import RunnableConfig
from game.utils.logger import get_logger
from game.core.agent_factory import set_game_agents, clear_game_agents

logger = get_logger(__name__)


class GameSession:
    """Represents an active game session."""
    
    def __init__(
        self,
        game_id: str,
        players: List[str],
        human_player_ids: List[str],
        workflow: Any,
        checkpointer: Any,
        agents:List[PlayerAgent],
        undercover_num: int,
    ):
        self.game_id = game_id
        self.players = players
        self.human_player_ids: Set[str] = set(human_player_ids)
        self.workflow = workflow
        self.checkpointer = checkpointer
        self.state: Optional[GameState] = None
        self.status = "waiting"  # waiting, running, finished, error
        self.error_message: Optional[str] = None
        self.created_at = datetime.now()
        self.winner: Optional[str] = None
        self.agents = agents
        self.undercover_num = undercover_num


class GameManager:
    """Singleton game manager."""
    
    _instance: Optional["GameManager"] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._games: Dict[str, GameSession] = {}
        return cls._instance
    
    def get_game(self, game_id: str) -> Optional[GameSession]:
        return self._games.get(game_id)
    
    def add_game(self, session: GameSession) -> None:
        self._games[session.game_id] = session
    
    def remove_game(self, game_id: str) -> None:
        if game_id in self._games:
            del self._games[game_id]
    
    def list_games(self) -> List[GameSession]:
        return list(self._games.values())
    
    def clear(self) -> None:
        self._games.clear()


def get_game_manager() -> GameManager:
    return GameManager()

async def run_game(session: GameSession) -> None:
    """Run a game session to completion."""

    logger.info("\n\n🎮 === RUN_GAME STARTED for %s === 🎮\n", session.game_id)
    try:
        # Register agents to multi-game registry
        set_game_agents(session.game_id, session.agents)

        initial_state: GameState = {
            "game_id": session.game_id,
            "players": session.players,
            "game_phase": "setup",
            "current_round": 0,
            "completed_speeches": [],
            "votes": [],
            "eliminated_players": [],
            "winner": None,
            "host_private_state": {},
            "player_private_states": {},
            "undercover_num": session.undercover_num,
            "phase_id": "",
            "current_votes": {},
        }

        # Set initial state immediately so stream can see it
        session.state = initial_state
        logger.info("Initial state set: phase=setup, players=%d", len(session.players))

        config = RunnableConfig(configurable={"thread_id": session.game_id})
        logger.info("Starting workflow astream...")

        try:
            async for step in session.workflow.astream(initial_state, config=config):
                
                # LangGraph astream yields {node_name: state_update_dict} format
                # Check if it's a node result dict by looking at keys
                known_nodes = {"host_setup", "host_stage_switch", "host_result", "host_judge",
                                "agent_speaking_dispatch", "agent_voting_dispatch", 
                                "check_votes_and_transition"}

                # Check if state_update is a node result dict (keys are node names)
                node_result_keys = [k for k in step.keys()
                                    if k not in ("__start__",) and isinstance(step[k], dict)]

                if node_result_keys:
                    for node_name in node_result_keys:
                        node_output = step[node_name]
                        if session.state is None:
                            session.state = {}
                        session.state.update(node_output)
                        phase = session.state.get("game_phase")
                        speeches = len(session.state.get("completed_speeches", []))
                        winner = session.state.get("winner")
                        logger.info("State update from %s: phase=%s, speeches=%d, winner=%s", node_name, phase, speeches, winner)

        except Exception as stream_error:
            logger.error("Game %s astream error: %s", session.game_id, stream_error, exc_info=True)
            raise  # Re-raise to be caught by outer except

        session.winner = session.state.get("winner")
        session.status = "finished"

        # Cleanup agent registry
        clear_game_agents(session.game_id)

        logger.info("=== RUN_GAME FINISHED for %s. Winner: %s ===", session.game_id, session.winner)

    except Exception as exc:
        error_msg = str(exc)
        logger.error("Game %s error: %s", session.game_id, exc, exc_info=True)
        session.status = "error"
        session.error_message = error_msg
        # Cleanup on error too
        clear_game_agents(session.game_id)
