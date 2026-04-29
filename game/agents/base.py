"""
Abstract base class for Player Agents.

Defines the common interface that both AI and Human players must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Sequence
from pydantic import BaseModel

from game.common.schema import Speech


class AgentType(Enum):
    """Type of player agent."""
    AI = "ai"
    HUMAN = "human"


@dataclass
class SpeechContext:
    """Context provided to agent when generating speech."""
    player_id: str
    my_word: str
    current_round: int
    completed_speeches: Sequence[Speech]
    alive_players: List[str]
    origin_players: List[str]
    self_belief: Dict[str, Any]  # Agent's belief about own role
    suspicions: Dict[str, Any]    # Agent's suspicions about others
    speech_plan: Optional[Dict[str, Any]] = None
    undercover_num: int = 1


@dataclass
class VoteContext:
    """Context provided to agent when voting."""
    player_id: str
    current_round: int
    alive_players: List[str]
    self_belief: Dict[str, Any]
    suspicions: Dict[str, Any]
    game_history: List[Dict[str, Any]]  # Previous rounds data


class GameEvent(BaseModel):
    """Event broadcast to all agents during gameplay."""
    type: Literal["speech", "vote_reveal", "elimination", "new_round", "game_end"]
    timestamp: datetime
    data: Dict[str, Any]


class PlayerAgent(ABC):
    """
    Abstract base class for all player agents (AI and Human).
    
    Each agent maintains its own internal state (mindset, memory) and
    communicates with the game engine through the standardized interface.
    """

    def __init__(self, player_id: str, name: str):
        self._player_id = player_id
        self._name = name
        self._alive = True
        self._word: Optional[str] = None
        self._role: Optional[str] = None  # "civilian" or "spy"
        self._mindset: Dict[str, Any] = {}

    @property
    def player_id(self) -> str:
        return self._player_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_alive(self) -> bool:
        return self._alive

    @is_alive.setter
    def is_alive(self, value: bool):
        self._alive = value

    @property
    def word(self) -> Optional[str]:
        return self._word

    @word.setter
    def word(self, value: str):
        self._word = value

    @property
    def role(self) -> Optional[str]:
        return self._role

    @role.setter
    def role(self, value: str):
        self._role = value

    @property
    def mindset(self) -> Dict[str, Any]:
        return self._mindset

    @mindset.setter
    def mindset(self, value: Dict[str, Any]):
        self._mindset = value

    @property
    @abstractmethod
    def agent_type(self) -> AgentType:
        """Return the type of this agent."""
        pass

    @abstractmethod
    async def speak(self, context: SpeechContext) -> str:
        """
        Generate a speech for the current round.
        
        Args:
            context: Context containing game state information
            
        Returns:
            The speech text (single line, no emojis)
        """
        pass

    @abstractmethod
    async def vote(self, context: VoteContext) -> str:
        """
        Vote for a player to eliminate.
        
        Args:
            context: Context containing voting information
            
        Returns:
            The player_id to vote for
        """
        pass

    @abstractmethod
    async def observe(self, event: GameEvent) -> None:
        """
        Receive and process a game event.
        
        This allows agents to update their internal state based on
        what happens in the game.
        
        Args:
            event: The game event to observe
        """
        pass

    def assign_role_and_word(self, role: str, word: str) -> None:
        """Called by the game host to assign role and word."""
        self._role = role
        self._word = word

    def get_mindset_for_serialization(self) -> Dict[str, Any]:
        """Get mindset state for saving to game state."""
        return {
            "self_belief": self._mindset.get("self_belief", {}),
            "suspicions": self._mindset.get("suspicions", {}),
            "reasoning_history": self._mindset.get("reasoning_history", []),
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self._player_id}, name={self._name}, type={self.agent_type.value})"
