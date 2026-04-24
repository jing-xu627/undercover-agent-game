"""
WebSocket server for human player integration.

Provides WebSocket endpoints for human players to connect and interact with the game.
"""

import asyncio
import json
import uuid
from typing import Any, Dict, Optional

from game.agents.human_agent import get_human_agent_manager
from game.utils.logger import get_logger
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = get_logger(__name__)

class WebSocketGameServer:
    """
    WebSocket server for human player connections.
    
    Manages WebSocket connections and bridges them to HumanAgent instances.
    """
    
    def __init__(self):
        self.app: Optional[Any] = None
        self._manager = get_human_agent_manager()
        
        if HAS_FASTAPI:
            self.app = FastAPI(title="Game WebSocket Server")
            self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Setup WebSocket routes."""
        if not self.app:
            return
        
        @self.app.websocket("/ws/play/{player_id}")
        async def websocket_endpoint(websocket: WebSocket, player_id: str):
            """Main WebSocket endpoint for players."""
            await self._handle_player_connection(websocket, player_id)
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "ok", "websocket_ready": True}
    
    async def _handle_player_connection(self, websocket: WebSocket, player_id: str) -> None:
        """Handle a player WebSocket connection."""
        websocket_id = str(uuid.uuid4())
        
        await websocket.accept()
        logger.info("WebSocket connection accepted for player %s (ws_id: %s)", 
                   player_id, websocket_id)
        
        # Check if agent exists
        agent = self._manager.get_agent(player_id)
        if agent is None:
            await websocket.send_json({
                "type": "error",
                "message": f"No game found for player {player_id}"
            })
            await websocket.close()
            return
        
        # Connect WebSocket to agent
        self._manager.connect_websocket(websocket_id, websocket, player_id)
        
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "player_id": player_id,
            "message": "Connected to game. Waiting for your turn..."
        })
        
        try:
            while True:
                # Wait for messages from client
                message = await websocket.receive_text()
                
                try:
                    data = json.loads(message)
                    await self._handle_client_message(player_id, data, websocket)
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON"
                    })
                    
        except WebSocketDisconnect:
            logger.info("Player %s disconnected", player_id)
            self._manager.disconnect_websocket(websocket_id)
        except Exception as exc:
            logger.error("WebSocket error for player %s: %s", player_id, exc)
            self._manager.disconnect_websocket(websocket_id)
    
    async def _handle_client_message(
        self, 
        player_id: str, 
        data: Dict[str, Any],
        websocket: WebSocket
    ) -> None:
        """Handle a message from the client."""
        msg_type = data.get("type")
        
        if msg_type == "speak":
            # Player is submitting a speech
            speech_text = data.get("content", "").strip()
            if not speech_text:
                await websocket.send_json({
                    "type": "error",
                    "message": "Speech content cannot be empty"
                })
                return
            
            # Forward to agent
            success = self._manager.handle_human_input(player_id, speech_text)
            if success:
                await websocket.send_json({
                    "type": "ack",
                    "action": "speak",
                    "status": "accepted"
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "No pending speech action found"
                })
                
        elif msg_type == "vote":
            # Player is submitting a vote
            target_id = data.get("target", "").strip()
            if not target_id:
                await websocket.send_json({
                    "type": "error",
                    "message": "Vote target cannot be empty"
                })
                return
            
            # Forward to agent
            success = self._manager.handle_human_input(player_id, target_id)
            if success:
                await websocket.send_json({
                    "type": "ack",
                    "action": "vote",
                    "status": "accepted"
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": "No pending vote action found"
                })
                
        elif msg_type == "ping":
            # Keep-alive ping
            await websocket.send_json({"type": "pong"})
            
        else:
            await websocket.send_json({
                "type": "error",
                "message": f"Unknown message type: {msg_type}"
            })


def create_websocket_server() -> Optional[WebSocketGameServer]:
    """Create and return a WebSocket server instance."""
    if not HAS_FASTAPI:
        logger.error("FastAPI not available, cannot create WebSocket server")
        return None
    return WebSocketGameServer()


# Standalone server runner (for testing)
if __name__ == "__main__":
    if HAS_FASTAPI:
        import uvicorn
        server = create_websocket_server()
        if server and server.app:
            uvicorn.run(server.app, host="0.0.0.0", port=8125)
    else:
        print("FastAPI required for standalone server")
