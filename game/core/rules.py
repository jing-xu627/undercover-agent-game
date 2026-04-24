"""
Game logic and rules implementation for the "Who Is Spy" game.

This module contains the core game mechanics:
- Role and word assignment
- Vote counting and elimination logic
- Win condition determination

Game Rules:
- Players are assigned roles (civilian or spy) and corresponding words
- Civilians get one word, spies get a related but different word
- Players describe their words in turns, then vote to eliminate suspects
- Game ends when all spies are eliminated or spies outnumber civilians

Key Functions:
- assign_roles_and_words: Random role assignment with word selection
- calculate_eliminated_player: Vote counting with tie-breaking
- determine_winner: Win condition checking based on alive players
"""

import random
from collections import Counter
from typing import List, Dict, Any

from game.common.config import load_config, calculate_spy_count
from game.utils.logger import get_logger
from game.graph.state import (
    GameState,
    alive_players,
    get_valid_votes_for_phase
)
from game.common.schema import PlayerPrivateState
from game.agents.base import PlayerAgent

logger = get_logger(__name__)


def assign_roles_and_words(
    player_agents: List[PlayerAgent],
    word_list: List[tuple[str, str]] = None,
    host_private_state: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """
    Assigns roles (spy/civilian) and words to agent players.
    Returns a dict to be merged into the private state.
    """
    if len(player_agents) < 3:
        raise ValueError("The game requires at least 3 players.")

    # Calculate spy count based on player count
    spy_count = calculate_spy_count(len(player_agents))

    # Select spies
    player_ids = [pa.player_id for pa in player_agents]
    spies = random.sample(player_ids, spy_count)

    # 1. Check if words are already provided in host_private_state (custom words)
    # If not, select from vocabulary
    if (
        host_private_state
        and host_private_state.get("civilian_word")
        and host_private_state.get("spy_word")
    ):
        civilian_word = host_private_state["civilian_word"]
        spy_word = host_private_state["spy_word"]
        logger.info(
            "Using custom words from host_private_state civilian='%s' spy='%s'",
            civilian_word,
            spy_word,
        )
    elif word_list:
        civilian_word, spy_word = random.choice(word_list)
    else:
        cfg = load_config()
        civilian_word, spy_word = random.choice(cfg.vocabulary)

    # 2. Prepare private states
    player_private_states: Dict[str, PlayerPrivateState] = {}
    for pa in player_agents:
        player_private_states[pa.player_id] = {
            "assigned_word": spy_word if pa.player_id in spies else civilian_word,
            "playerMindset": {
                "self_belief": {"role": "civilian", "confidence": 0.5},
                "suspicions": {},
            },
        }

    host_private_state = {
        "player_roles": {p: ("spy" if p in spies else "civilian") for p in player_ids},
        "civilian_word": civilian_word,
        "spy_word": spy_word,
    }

    return {
        "host_private_state": host_private_state,
        "player_private_states": player_private_states,
    }


def calculate_eliminated_player(state: GameState) -> str | None:
    """
    Calculates who is eliminated based on the current votes.
    In case of a tie, randomly select one player to eliminate.
    """
    votes = state.get("current_votes", {})
    current_phase_id = state.get("phase_id")

    valid_votes = get_valid_votes_for_phase(votes, current_phase_id)

    # Extract targets in one line using list comprehension
    vote_targets = [
        getattr(vote, "target", None) or vote.get("target")
        for vote in valid_votes.values()
        if getattr(vote, "target", None) or vote.get("target")
    ]

    if not vote_targets:
        return None

    vote_counts = Counter(vote_targets)
    most_common = vote_counts.most_common(2)

    # Check for unique maximum
    if len(most_common) == 1 or most_common[0][1] > most_common[1][1]:
        return most_common[0][0]

    # Tie case: randomly select one player from the tied players
    max_votes = most_common[0][1]
    tied_players = [
        player for player, count in vote_counts.items() if count == max_votes
    ]

    if tied_players:
        eliminated = random.choice(tied_players)
        logger.info(
            "Tie detected among %s; randomly eliminated %s", tied_players, eliminated
        )
        return eliminated

    return None


def determine_winner(
    state: GameState, host_private_state: Dict[str, Any]
) -> str | None:
    """
    Determines if there is a winner based on the current game state.
    Returns 'civilians', 'spies', or None.
    """
    alive = alive_players(state)
    roles = host_private_state.get("player_roles", {})

    alive_spies = [p for p in alive if roles.get(p) == "spy"]
    alive_civilians = [p for p in alive if roles.get(p) == "civilian"]

    # Civilian victory condition: all spies are eliminated
    if not alive_spies and alive:
        return "civilians"

    # Spy victory condition: number of spies is strictly greater than civilians
    if alive and len(alive_spies) > len(alive_civilians):
        return "spies"

    return None
