"""
Human Player Agent with WebSocket integration.

This agent waits for human input via WebSocket connection and relays
it back to the game engine.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

from game.agents.base import AgentType, GameEvent, PlayerAgent, SpeechContext, VoteContext
from game.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PendingAction:
    """Represents a pending action waiting for human input."""
    action_type: str  # "speak" or "vote"
    context: Any
    future: asyncio.Future = field(default_factory=lambda: asyncio.get_event_loop().create_future())
    timeout_seconds: float = 300.0  # 5 minute default timeout
    created_at: datetime = field(default_factory=datetime.now)


class HumanAgent(PlayerAgent):
    """
    Human-controlled player agent.
    
    This agent acts as a bridge between the game engine and a human player
    connected via WebSocket. When the game requests an action (speak/vote),
    the agent:
    1. Stores the pending action
    2. Notifies the WebSocket handler to send prompt to frontend
    3. Waits for human response (with timeout)
    4. Returns the response to the game engine
    """

    def __init__(
        self,
        player_id: str,
        name: str,
        manager: "HumanAgentManager",
    ):
        super().__init__(player_id, name)
        self._manager = manager
        self._pending_action: Optional[PendingAction] = None
        self._websocket_id: Optional[str] = None
        self._connected = False
        self._action_timeout = 300.0  # 5 minutes

    @property
    def agent_type(self) -> AgentType:
        return AgentType.HUMAN

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def websocket_id(self) -> Optional[str]:
        return self._websocket_id

    def connect(self, websocket_id: str) -> None:
        """Called when WebSocket connection is established."""
        self._websocket_id = websocket_id
        self._connected = True
        logger.info("HumanAgent %s connected via WebSocket %s", self._player_id, websocket_id)

    def disconnect(self) -> None:
        """Called when WebSocket connection is closed."""
        self._connected = False
        logger.info("HumanAgent %s disconnected", self._player_id)

    async def speak(self, context: SpeechContext) -> str:
        """
        Wait for human player to provide speech.
        
        Creates a pending action and waits for human input via WebSocket.
        """
        logger.info("HumanAgent %s speak() called, connected=%s (round %d)", 
                     self._player_id, self._connected, context.current_round)
        
        # Check if connected - if not, return default immediately without blocking
        if not self._connected:
            logger.warning("HumanAgent %s not connected, using default speech", self._player_id)
            return self._get_default_speech(context)

        # Create pending action
        action = PendingAction(
            action_type="speak",
            context=context,
            timeout_seconds=self._action_timeout,
        )
        self._pending_action = action

        # Notify manager to send prompt to frontend
        await self._manager.notify_speak_prompt(self._player_id, context)

        try:
            # Wait for human input with timeout
            result = await asyncio.wait_for(action.future, timeout=action.timeout_seconds)
            speech = str(result).strip()
            
            # Validate speech
            if not speech:
                logger.warning("HumanAgent %s provided empty speech, using default", self._player_id)
                return self._get_default_speech(context)
            
            logger.info("HumanAgent %s speech received: %s", self._player_id, speech[:50])
            return speech
            
        except asyncio.TimeoutError:
            logger.warning("HumanAgent %s speech timeout, using default", self._player_id)
            return self._get_default_speech(context)
        finally:
            self._pending_action = None

    async def vote(self, context: VoteContext) -> str:
        """
        Wait for human player to provide vote.
        
        Creates a pending action and waits for human input via WebSocket.
        """
        logger.info("HumanAgent %s waiting for vote input (round %d)",
                     self._player_id, context.current_round)

        if not self._connected:
            logger.warning("HumanAgent %s not connected, using random vote", self._player_id)
            return self._get_random_vote(context)

        # Create pending action
        action = PendingAction(
            action_type="vote",
            context=context,
            timeout_seconds=self._action_timeout,
        )
        self._pending_action = action

        # Notify manager to send prompt to frontend
        await self._manager.notify_vote_prompt(self._player_id, context)

        try:
            # Wait for human input with timeout
            result = await asyncio.wait_for(action.future, timeout=action.timeout_seconds)
            vote_target = str(result).strip()
            
            # Validate vote
            if vote_target not in context.alive_players:
                logger.warning("HumanAgent %s voted for invalid target %s", 
                             self._player_id, vote_target)
                return self._get_random_vote(context)
            
            logger.info("HumanAgent %s vote received: %s", self._player_id, vote_target)
            return vote_target
            
        except asyncio.TimeoutError:
            logger.warning("HumanAgent %s vote timeout, using random vote", self._player_id)
            return self._get_random_vote(context)
        finally:
            self._pending_action = None

    async def observe(self, event: GameEvent) -> None:
        """
        Broadcast events to human player via WebSocket.
        
        This keeps the human informed of game progress.
        """
        if self._connected:
            await self._manager.send_event_to_human(self._player_id, event)

    def receive_input(self, input_data: str) -> bool:
        """
        Called by WebSocket handler when human provides input.
        
        Args:
            input_data: The speech text or vote target
            
        Returns:
            True if input was accepted, False if no pending action
        """
        if self._pending_action is None:
            logger.warning("HumanAgent %s received input but no pending action", self._player_id)
            return False
        
        if self._pending_action.future.done():
            logger.warning("HumanAgent %s received input but future already done", self._player_id)
            return False
        
        self._pending_action.future.set_result(input_data)
        return True

    def _get_default_speech(self, context: SpeechContext) -> str:
        """Generate a default speech when human doesn't respond in time."""
        word = self._word or "something"
        return f"I think the word relates to {word}."

    def _get_random_vote(self, context: VoteContext) -> str:
        """Generate a random valid vote when human doesn't respond in time."""
        import random
        other_players = [p for p in context.alive_players if p != self._player_id]
        if other_players:
            return random.choice(other_players)
        return context.alive_players[0] if context.alive_players else self._player_id


class HumanAgentManager:
    """
    Manages all human agents and their WebSocket connections.
    
    This is a singleton-like manager that coordinates between:
    - WebSocket connections from frontend
    - HumanAgent instances in the game
    """

    _instance: Optional["HumanAgentManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agents: Dict[str, HumanAgent] = {}
            cls._instance._websockets: Dict[str, Any] = {}  # websocket_id -> websocket
        return cls._instance

    def register_agent(self, agent: HumanAgent) -> None:
        """Register a human agent with the manager."""
        self._agents[agent.player_id] = agent
        logger.info("HumanAgent %s registered with manager", agent.player_id)

    def unregister_agent(self, player_id: str) -> None:
        """Unregister a human agent."""
        if player_id in self._agents:
            del self._agents[player_id]
            logger.info("HumanAgent %s unregistered from manager", player_id)

    def get_agent(self, player_id: str) -> Optional[HumanAgent]:
        """Get a registered human agent by player_id."""
        return self._agents.get(player_id)

    def connect_websocket(self, websocket_id: str, websocket: Any, player_id: str) -> bool:
        """
        Associate a WebSocket connection with a human agent.
        
        Args:
            websocket_id: Unique identifier for this connection
            websocket: The WebSocket object
            player_id: The player_id of the human agent
            
        Returns:
            True if connection successful
        """
        agent = self._agents.get(player_id)
        if agent is None:
            logger.error("Cannot connect WebSocket: no agent found for %s", player_id)
            return False
        
        self._websockets[websocket_id] = websocket
        agent.connect(websocket_id)
        return True

    def disconnect_websocket(self, websocket_id: str) -> None:
        """Handle WebSocket disconnection."""
        if websocket_id in self._websockets:
            del self._websockets[websocket_id]
        
        # Find and disconnect the associated agent
        for agent in self._agents.values():
            if agent.websocket_id == websocket_id:
                agent.disconnect()
                break

    async def notify_speak_prompt(self, player_id: str, context: SpeechContext) -> None:
        """Send speech prompt to human player via WebSocket."""
        websocket = self._get_websocket_for_player(player_id)
        if websocket is None:
            return
        
        message = {
            "type": "prompt_speak",
            "player_id": player_id,
            "round": context.current_round,
            "my_word": context.my_word,
            "alive_players": context.alive_players,
            "completed_speeches": [
                {"player": s.get("player_id"), "content": s.get("content")}
                for s in context.completed_speeches
            ],
            "timeout_seconds": 300,
        }
        
        try:
            await websocket.send_json(message)
        except Exception as exc:
            logger.error("Failed to send speak prompt to %s: %s", player_id, exc)

    async def notify_vote_prompt(self, player_id: str, context: VoteContext) -> None:
        """Send vote prompt to human player via WebSocket."""
        websocket = self._get_websocket_for_player(player_id)
        if websocket is None:
            return
        
        message = {
            "type": "prompt_vote",
            "player_id": player_id,
            "round": context.current_round,
            "alive_players": context.alive_players,
            "suspicions": context.suspicions,
            "timeout_seconds": 300,
        }
        
        try:
            await websocket.send_json(message)
        except Exception as exc:
            logger.error("Failed to send vote prompt to %s: %s", player_id, exc)

    async def send_event_to_human(self, player_id: str, event: GameEvent) -> None:
        """Send a game event to human player."""
        websocket = self._get_websocket_for_player(player_id)
        if websocket is None:
            return
        
        message = {
            "type": "game_event",
            "event_type": event.type,
            "timestamp": event.timestamp.isoformat(),
            "data": event.data,
        }
        
        try:
            await websocket.send_json(message)
        except Exception as exc:
            logger.error("Failed to send event to %s: %s", player_id, exc)

    async def handle_human_input(self, player_id: str, input_data: str) -> bool:
        """
        Handle input received from human player via WebSocket.
        
        Args:
            player_id: The player who sent the input
            input_data: The speech or vote
            
        Returns:
            True if input was accepted
        """
        agent = self._agents.get(player_id)
        if agent is None:
            logger.error("Received input for unknown player %s", player_id)
            return False
        
        return agent.receive_input(input_data)

    def _get_websocket_for_player(self, player_id: str) -> Optional[Any]:
        """Get WebSocket object for a player."""
        agent = self._agents.get(player_id)
        if agent is None or agent.websocket_id is None:
            return None
        return self._websockets.get(agent.websocket_id)


def get_human_agent_manager() -> HumanAgentManager:
    """Get the singleton HumanAgentManager instance."""
    return HumanAgentManager()
