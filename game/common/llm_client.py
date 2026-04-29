
from typing import Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import threading

load_dotenv()

from game.common.settings import global_config


def create_llm() -> ChatOpenAI:
    cfg = global_config.llm
    return ChatOpenAI(
        api_key=cfg.api_key or None,
        model=cfg.model,
        base_url=cfg.base_url,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
    )


# Module-level singleton storage
_llm_client: Optional[ChatOpenAI] = None
_llm_singleton_lock = threading.Lock()


def get_llm_client() -> ChatOpenAI:
    global _llm_client

    if _llm_client is not None:
        return _llm_client

    with _llm_singleton_lock:
        if _llm_client is None:
            _llm_client = create_llm()
    return _llm_client


def reset_llm_singleton() -> None:
    global _llm_client
    with _llm_singleton_lock:
        _llm_client = None
