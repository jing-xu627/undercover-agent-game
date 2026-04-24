"""
Health check and root endpoints.
"""

from datetime import datetime

from fastapi import APIRouter

from game.core.game_manager import get_game_manager

router = APIRouter()


@router.get("/")
async def root():
    """Server info."""
    return {
        "service": "Undercover Game Server",
        "version": "0.2.0",
        "features": ["ai_agents", "human_players", "websocket"],
    }


@router.get("/health")
async def health():
    """Health check."""
    manager = get_game_manager()
    return {
        "status": "ok",
        "active_games": len(manager.list_games()),
        "timestamp": datetime.now().isoformat(),
    }
