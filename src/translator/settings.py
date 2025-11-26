from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class Settings:
    anthropic_api_key: str
    default_source_lang: str
    default_target_lang: str
    data_root: Path


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    data_root = Path(os.getenv("DATA_ROOT", "./data")).resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    return Settings(
        anthropic_api_key=api_key,
        default_source_lang=os.getenv("DEFAULT_SOURCE_LANG", "fr"),
        default_target_lang=os.getenv("DEFAULT_TARGET_LANG", "en"),
        data_root=data_root,
    )

