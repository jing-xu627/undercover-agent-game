"""
WebSocket handler for human player connections.
"""

import json
from uuid import uuid4
from typing import Any, Dict

from fastapi import WebSocket, WebSocketDisconnect

from game.core.game_manager import get_game_manager
from game.agents.human_agent import HumanAgent, get_human_agent_manager
from game.utils.logger import get_logger

logger = get_logger(__name__)

_manager = get_human_agent_manager()


async def player_websocket(websocket: WebSocket, game_id: str, player_id: str):
    """
    WebSocket endpoint for human players.
    
    URL: /ws/play/{game_id}/{player_id}
    """
    await websocket.accept()
    websocket_id = f"{game_id}:{player_id}:{uuid4().hex[:6]}"
    
    # Validate game
    session = get_game_manager().get_game(game_id)
    if not session:
        await websocket.send_json({
            "type": "error",
            "message": f"Game {game_id} not found"
        })
        await websocket.close()
        return
    
    if player_id not in session.human_player_ids:
        await websocket.send_json({
            "type": "error",
            "message": f"Player {player_id} is not a human player"
        })
        await websocket.close()
        return
    
    # Get or create agent
    agent = _manager.get_agent(player_id)
    if agent is None:
        agent = HumanAgent(
            player_id=player_id,
            name=player_id,
            manager=_manager,
        )
        _manager.register_agent(agent)
        session.agents[player_id] = agent
    
    _manager.connect_websocket(websocket_id, websocket, player_id)
    
    await websocket.send_json({
        "type": "connected",
        "game_id": game_id,
        "player_id": player_id,
        "message": "Connected to game",
    })
    
    logger.info("Player %s connected to game %s", player_id, game_id)
    
    try:
        while True:
            message = await websocket.receive_text()
            try:
                data = json.loads(message)
                await _handle_message(player_id, data, websocket)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })
    except WebSocketDisconnect:
        logger.info("Player %s disconnected from game %s", player_id, game_id)
        _manager.disconnect_websocket(websocket_id)
    except Exception as exc:
        logger.error("WebSocket error for %s: %s", player_id, exc)
        _manager.disconnect_websocket(websocket_id)


async def _handle_message(
    player_id: str,
    data: Dict[str, Any],
    websocket: WebSocket
) -> None:
    """Handle message from player."""
    msg_type = data.get("type")
    
    if msg_type == "speak":
        content = data.get("content", "").strip()
        if not content:
            await websocket.send_json({
                "type": "error",
                "message": "Speech content cannot be empty"
            })
            return
        
        success = await _manager.handle_human_input(player_id, content)
        await websocket.send_json({
            "type": "ack",
            "action": "speak",
            "status": "accepted" if success else "rejected"
        })
        
    elif msg_type == "vote":
        target = data.get("target", "").strip()
        if not target:
            await websocket.send_json({
                "type": "error",
                "message": "Vote target cannot be empty"
            })
            return
        
        success = await _manager.handle_human_input(player_id, target)
        await websocket.send_json({
            "type": "ack",
            "action": "vote",
            "status": "accepted" if success else "rejected"
        })
        
    elif msg_type == "ping":
        await websocket.send_json({"type": "pong"})
        
    else:
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown message type: {msg_type}"
        })
