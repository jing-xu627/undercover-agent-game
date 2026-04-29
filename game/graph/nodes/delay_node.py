import asyncio
from typing import Any, Dict

from game.graph.state import GameState
from game.utils.logger import get_logger

logger = get_logger(__name__)

DISPLAY_SECONDS = 30  # 投票结果展示时长（秒）


async def display_delay(state: GameState) -> Dict[str, Any]:
    """
    Delay node: pause before host_judge so that
    the frontend has time to display voting results.
    """
    current_round = state.get("current_round", 0)
    logger.info(
        "Display delay: waiting %ds for round %d",
        DISPLAY_SECONDS, current_round,
    )
    await asyncio.sleep(DISPLAY_SECONDS)
    return {}
