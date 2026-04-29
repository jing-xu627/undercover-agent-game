
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class LLMConfig:
    llm_provider: str = "openai"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    
    temperature: float = 0.7
    max_tokens: int = 500


@dataclass
class GameConfig:
    default_player_count: int = 6
    min_players: int = 4
    max_players: int = 8
    undercover_num: int = 1


class Config:
    
    def __init__(self):
        self.llm = self._load_llm_config()
        self.game = self._load_game_config()
    
    def _load_llm_config(self) -> LLMConfig:
        api_key = os.getenv("OPENAI_API_KEY", "")
        model = os.getenv("OPENAI_MODEL", "gpt-4")
        base_url = os.getenv("OPENAI_BASE_URL")
        
        return LLMConfig(
            api_key=api_key,
            model=model,
            base_url=base_url,
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "500")),
        )
    
    def _load_game_config(self) -> GameConfig:
        return GameConfig(
            default_player_count=int(os.getenv("GAME_DEFAULT_PLAYERS", "5")),
            min_players=int(os.getenv("GAME_MIN_PLAYERS", "3")),
            max_players=int(os.getenv("GAME_MAX_PLAYERS", "8")),
            undercover_num=int(os.getenv("GAME_UNDERCOVER_NUM", "1")),
        )
    
    def validate(self) -> list[str]:
        errors = []
        
        if not self.llm.api_key:
            errors.append("未设置 LLM API 密钥")
        
        if not self.llm.model:
            errors.append("未设置模型名称")
        
        return errors


# global config
global_config = Config()
