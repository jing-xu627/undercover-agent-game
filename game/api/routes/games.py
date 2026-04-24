"""
Game management endpoints.
"""

from typing import List, Optional, Any, Dict
from uuid import uuid4
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from game.core.game_manager import GameSession, get_game_manager, run_game
from game.graph.build_graph import build_agent_workflow
from langgraph.checkpoint.memory import MemorySaver
from game.common.config import load_config, calculate_spy_count
from game.utils.logger import get_logger
from game.agents.host_agent import create_agents_from_config


logger = get_logger(__name__)


def serialize_value(value: Any) -> Any:
    """Recursively serialize value to JSON-compatible format."""
    if isinstance(value, BaseModel):
        return value.model_dump()
    elif isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [serialize_value(item) for item in value]
    elif isinstance(value, set):
        return list(value)
    return value


def serialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize game state to JSON-compatible dict."""
    if not state:
        return {}
    result = {}
    for key, value in state.items():
        if key == "agents":
            continue
        result[key] = serialize_value(value)
    return result

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
    """Get game state."""
    session = get_game_manager().get_game(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="Game not found")

    return {
        "game_id": game_id,
        "status": session.status,
        "error_message": session.error_message,
        "current_state": serialize_state(session.state),
        "winner": session.winner,
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
