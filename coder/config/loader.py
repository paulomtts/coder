# coder/config/loader.py
import os
from dataclasses import dataclass, field

import yaml
from dotenv import load_dotenv

from coder.shared.constants import (
    DEFAULT_COMPACTION_THRESHOLD,
    DEFAULT_HISTORY_LIMIT,
    DEFAULT_KEEP_RECENT_TOKENS,
)


@dataclass
class SessionConfig:
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    history_limit: int = DEFAULT_HISTORY_LIMIT
    compaction_threshold: float = DEFAULT_COMPACTION_THRESHOLD
    keep_recent_tokens: int = DEFAULT_KEEP_RECENT_TOKENS
    cwd: str = field(default_factory=os.getcwd)

    @classmethod
    def from_env(cls) -> "SessionConfig":
        return cls(
            model=os.environ.get("LLM_MODEL", ""),
            api_key=os.environ.get("LLM_API_KEY", ""),
            base_url=os.environ.get("LLM_BASE_URL", ""),
        )


def load_config(cwd: str | None = None) -> SessionConfig:
    target_cwd = cwd or os.getcwd()
    dotenv_path = os.path.join(target_cwd, ".env")
    load_dotenv(dotenv_path)

    config = SessionConfig.from_env()
    config.cwd = target_cwd
    config_path = os.path.join(config.cwd, ".coder", "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}
        if "history_limit" in data:
            config.history_limit = data["history_limit"]
        if "compaction_threshold" in data:
            config.compaction_threshold = data["compaction_threshold"]
        if "keep_recent_tokens" in data:
            config.keep_recent_tokens = data["keep_recent_tokens"]
        if "model" in data:
            config.model = data["model"]
        if "api_key" in data:
            config.api_key = data["api_key"]
        if "base_url" in data:
            config.base_url = data["base_url"]
    return config
