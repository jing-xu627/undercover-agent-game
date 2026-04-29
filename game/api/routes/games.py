"""
Game management endpoints.
"""

from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from game.core.game_manager import GameSession, get_game_manager, run_game
from game.graph.build_graph import build_agent_workflow
from langgraph.checkpoint.memory import MemorySaver
from game.common.config import load_config, calculate_spy_count
from game.utils.logger import get_logger
from game.core.agent_factory import create_agents_from_config
from game.common.constant import PlayerRole


logger = get_logger(__name__)


router = APIRouter(prefix="/games", tags=["games"])


class CreateGameRequest(BaseModel):
    player_count: int = 4
    human_player_ids: Optional[List[str]] = None


@router.post("/create")
async def create_game(request: CreateGameRequest):
    """
    Create a new game.
    
    Args:
        player_count: Total number of players
        human_player_ids: List of player IDs that are human
    
    Returns:
        Game ID and player assignments
    """
    if request.human_player_ids and len(request.human_player_ids) > 1:
        raise HTTPException(status_code=400, detail="Only one human player is allowed")
    if request.player_count < 3:
        raise HTTPException(status_code=400, detail="Player count must be at least 3")
    cfg = load_config()
    player_names = cfg.player_names_pool

    # Generate player names
    if request.human_player_ids:
        ai_count = request.player_count - len(request.human_player_ids)
        if ai_count < 0:
            raise HTTPException(status_code=400, detail="Human player count cannot exceed total player count")
        all_players = list(request.human_player_ids) + player_names[:ai_count]
    else:
        all_players = player_names[:request.player_count]
    
    game_id = f"game-{uuid4().hex[:8]}"

    # Build workflow
    workflow = build_agent_workflow()

    # Create agents (AI and Human)
    agents = create_agents_from_config(
        player_ids=all_players,
        human_player_ids=request.human_player_ids or [],
    )
    
    # Create session
    session = GameSession(
        game_id=game_id,
        players=all_players,
        human_player_ids=request.human_player_ids or [],
        agents=list(agents.values()),
        undercover_num=calculate_spy_count(request.player_count),
        workflow=workflow,
        checkpointer=MemorySaver(),
    )
    
    get_game_manager().add_game(session)
    
    return {
        "game_id": game_id,
        "players": all_players,
        "human_players": request.human_player_ids or [],
        "ai_players": [p for p in all_players if p not in (request.human_player_ids or [])],
        "status": "waiting",
    }


@router.post("/{game_id}/start")
async def start_game(game_id: str, background_tasks: BackgroundTasks):
    logger.info(f"[START_GAME] Request received for {game_id}")
    session = get_game_manager().get_game(game_id)

    if not session:
        logger.error(f"[START_GAME] Game not found: {game_id}")
        raise HTTPException(status_code=404, detail="Game not found")

    if session.status == "running":
        raise HTTPException(status_code=400, detail="Game already running")

    if session.status == "finished":
        raise HTTPException(status_code=400, detail="Game already finished")

    background_tasks.add_task(run_game, session)
    session.status = "running"

    return {
        "game_id": game_id,
        "status": session.status,
        "message": "Game started",
    }


@router.get("/{game_id}")
async def get_game(game_id: str):
    """Get game info."""
    session = get_game_manager().get_game(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    game_info = {}
    state = session.state
    if state:
        human_player_id = list(session.human_player_ids)[0]

        your_word = None
        if human_player_id and "player_private_states" in state:
            player_private_states = state["player_private_states"]
            if human_player_id in player_private_states:
                your_word = player_private_states[human_player_id].get("assigned_word", None)

        game_info = {
            "current_round": state.get("current_round", 0),
            "game_phase": state.get("game_phase", "setup"),
            "phase_id": state.get("phase_id", ""),
            "completed_speeches": state.get("completed_speeches", []),
            "eliminated_players": state.get("eliminated_players", []),
            "current_votes": state.get("current_votes", {}),
            "your_word": your_word
        }
    return {
        "game_id": game_id,
        "status": session.status,
        "error_message": session.error_message,
        "game_info": game_info,
        "players": session.players,
        "human_players": list(session.human_player_ids),
    }

@router.get("/")
async def list_games():
    """List all games."""
    games = get_game_manager().list_games()
    return {
        "games": [
            {
                "game_id": g.game_id,
                "status": g.status,
                "error_message": g.error_message,
                "players": g.players,
                "human_count": len(g.human_player_ids),
                "created_at": g.created_at.isoformat(),
            }
            for g in games
        ]
    }


@router.delete("/{game_id}")
async def delete_game(game_id: str):
    """Delete a game."""
    manager = get_game_manager()
    if not manager.get_game(game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    
    manager.remove_game(game_id)
    return {"message": "Game deleted"}

@router.get("/{game_id}/final_result")
async def game_final_result(game_id: str):
    """Get final result of a game."""
    session = get_game_manager().get_game(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")
    if session.status != "finished":
        raise HTTPException(status_code=400, detail="Game not finished")
    
    game_state = session.state
    spies = []
    host_private_state = game_state["host_private_state"]
    for player_id, player_role in host_private_state["player_roles"].items():
        if player_role == PlayerRole.SPY:
            spies.append(player_id)

    return {
        "game_id": game_id,
        "winner": game_state["winner"],
        "civilian_word": host_private_state["civilian_word"],
        "spy_word": host_private_state["spy_word"],
        "spies": spies,
    }

