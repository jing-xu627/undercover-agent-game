"""
Threads API for LangGraph SDK compatibility.
Provides thread management endpoints that mirror LangGraph Server API.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from game.core.game_manager import get_game_manager

router = APIRouter(prefix="/threads", tags=["threads"])


class ThreadMetadata(BaseModel):
    """Thread metadata"""
    name: Optional[str] = None
    description: Optional[str] = None


class ThreadCreateRequest(BaseModel):
    """Request to create a new thread"""
    thread_id: Optional[str] = None
    metadata: Optional[ThreadMetadata] = None


class ThreadResponse(BaseModel):
    """Thread response"""
    thread_id: str
    created_at: str
    updated_at: str
    metadata: dict = Field(default_factory=dict)
    status: str = "active"


# In-memory thread storage (replace with persistent storage in production)
_threads: dict[str, ThreadResponse] = {}

# Thread to game mapping
_thread_game_map: dict[str, str] = {}


@router.post("/")
async def create_thread(request: ThreadCreateRequest) -> ThreadResponse:
    """
    Create a new thread (LangGraph SDK compatible).

    This endpoint mimics LangGraph Server's threads.create() API.
    """
    thread_id = request.thread_id or f"thread-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    # Check if metadata contains game_id
    metadata = request.metadata.model_dump() if request.metadata else {}
    game_id = metadata.get("game_id")

    thread = ThreadResponse(
        thread_id=thread_id,
        created_at=now,
        updated_at=now,
        metadata=metadata,
        status="active"
    )

    _threads[thread_id] = thread
    if game_id:
        _thread_game_map[thread_id] = game_id

    return thread


@router.get("/{thread_id}")
async def get_thread(thread_id: str) -> ThreadResponse:
    """Get thread by ID"""
    if thread_id not in _threads:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    return _threads[thread_id]


@router.delete("/{thread_id}")
async def delete_thread(thread_id: str):
    """Delete a thread"""
    if thread_id not in _threads:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
    del _threads[thread_id]
    return {"message": f"Thread {thread_id} deleted"}


class RunCreateRequest(BaseModel):
    """Request to create a new run"""
    assistant_id: Optional[str] = None
    input: Optional[dict] = None
    config: Optional[dict] = None


class RunResponse(BaseModel):
    """Run response"""
    run_id: str
    thread_id: str
    status: str
    created_at: str


@router.post("/{thread_id}/runs")
async def create_run(thread_id: str, request: RunCreateRequest) -> RunResponse:
    """Create a new run in a thread (LangGraph SDK compatible)"""
    if thread_id not in _threads:
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    run_id = f"run-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()

    # Store the run (in production, use persistent storage)
    if not hasattr(_threads[thread_id], 'runs'):
        _threads[thread_id].runs = {}

    run = RunResponse(
        run_id=run_id,
        thread_id=thread_id,
        status="pending",
        created_at=now,
    )
    _threads[thread_id].runs[run_id] = run

    return run


@router.post("/{thread_id}/runs/stream")
async def stream_run(thread_id: str, request: RunCreateRequest):
    """Stream a run in a thread (LangGraph SDK compatible)"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"=== STREAM REQUEST for thread {thread_id} ===")
    logger.info(f"Request input: {request.input}")

    if thread_id not in _threads:
        logger.error(f"Thread {thread_id} not found")
        raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")

    run_id = f"run-{uuid4().hex[:12]}"

    # Get game_id from thread metadata or mapping
    thread = _threads[thread_id]
    game_id = thread.metadata.get("game_id") or _thread_game_map.get(thread_id)

    # If input contains game_id, use it and store mapping
    if request.input and request.input.get("game_id"):
        game_id = request.input.get("game_id")
        _thread_game_map[thread_id] = game_id
        thread.metadata["game_id"] = game_id

    logger.info(f"Game ID: {game_id}")

    async def event_stream():
        logger.info(f"Stream started for run {run_id}, game {game_id}")
        # Send run start event (NDJSON format for LangGraph SDK)
        yield json.dumps({'event': 'metadata', 'data': {'run_id': run_id, 'thread_id': thread_id}}) + "\n"
        await asyncio.sleep(0.1)

        if game_id:
            # Stream actual game state
            game_manager = get_game_manager()
            last_state = None
            max_iterations = 600  # 5 minutes max (500ms * 600)
            iteration = 0

            for _ in range(max_iterations):
                iteration += 1
                session = game_manager.get_game(game_id)
                if not session:
                    logger.warning(f"Game {game_id} not found in iteration {iteration}")
                    yield json.dumps({'event': 'values', 'data': {'error': 'Game not found'}}) + "\n"
                    break

                # Get current game state
                state = session.state
                status = session.status
                players = session.players

                if iteration % 10 == 0:  # Log every 10th iteration
                    logger.info(f"Iteration {iteration}: status={status}, players={len(players) if players else 0}, has_state={state is not None}")

                if state and state != last_state:
                    # Send state update - LangGraph SDK expects 'values' event with full state
                    logger.info(f"State changed, sending update: phase={state.get('game_phase')}, players={len(state.get('players', []))}")
                    yield json.dumps({'event': 'values', 'data': state}) + "\n"
                    last_state = state

                # Check if game finished
                if status in ("finished", "error"):
                    logger.info(f"Game {game_id} finished with status: {status}")
                    if state:
                        yield json.dumps({'event': 'values', 'data': state}) + "\n"
                    break

                # If no state yet but players exist, send initial setup info
                if not state and players:
                    initial_state = {
                        "game_id": game_id,
                        "players": players,
                        "game_phase": "setup",
                        "current_round": 0,
                        "completed_speeches": [],
                        "votes": [],
                        "eliminated_players": [],
                        "winner": None,
                        "host_private_state": request.input.get("host_private_state", {}) if request.input else {},
                        "player_private_states": {}
                    }
                    logger.info(f"Sending initial state with {len(players)} players")
                    yield json.dumps({'event': 'values', 'data': initial_state}) + "\n"

                await asyncio.sleep(0.5)  # Poll every 500ms
        else:
            # No game linked, send error
            logger.error("No game_id provided")
            yield json.dumps({'event': 'values', 'data': {'error': 'No game linked to thread'}}) + "\n"

        logger.info(f"Stream ended for run {run_id}")
        # Send end event
        yield json.dumps({'event': 'end', 'data': {'run_id': run_id}}) + "\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
