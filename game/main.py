
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from game.core.game_manager import get_game_manager
from game.api.routes.health import router as health_router
from game.api.routes.games import router as games_router
from game.api.routes.threads import router as threads_router
from game.api.websocket.handler import player_websocket
from game.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting server...")
    
    # Load dependencies
    #deps = build_dependencies()
    #logger.info("Dependencies loaded. Config: %s players", deps.config.player_count)
    
    yield
    
    # Shutdown
    logger.info("Shutting down server...")
    get_game_manager().clear()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="Undercover Game API",
        description="Multi-agent social deduction game with human player support",
        version="0.2.0",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(health_router)
    app.include_router(games_router)
    app.include_router(threads_router)
    
    # WebSocket endpoint
    
    @app.websocket("/ws/play/{game_id}/{player_id}")
    async def websocket_endpoint(websocket: WebSocket, game_id: str, player_id: str):
        await player_websocket(websocket, game_id, player_id)
    
    return app
