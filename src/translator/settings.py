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
    # #region agent log
    import json
    log_path = "/Users/enrico/workspace/translator/.cursor/debug.log"
    try:
        api_key_raw = os.getenv("ANTHROPIC_API_KEY", "")
        api_key_info = {
            "exists": api_key_raw != "",
            "length": len(api_key_raw) if api_key_raw else 0,
            "first_3_chars": api_key_raw[:3] if len(api_key_raw) >= 3 else "",
            "last_3_chars": api_key_raw[-3:] if len(api_key_raw) >= 3 else "",
            "has_whitespace_start": api_key_raw.startswith((" ", "\n", "\t")) if api_key_raw else False,
            "has_whitespace_end": api_key_raw.endswith((" ", "\n", "\t")) if api_key_raw else False,
        }
        with open(log_path, "a") as f:
            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "A,B,C,D", "location": "settings.py:23", "message": "ANTHROPIC_API_KEY env var check", "data": api_key_info, "timestamp": __import__("time").time() * 1000}) + "\n")
    except Exception:
        pass
    # #endregion
    api_key = api_key_raw.strip() if api_key_raw else ""  # Strip whitespace
    data_root = Path(os.getenv("DATA_ROOT", "./data")).resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    # #region agent log
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps({"sessionId": "debug-session", "runId": "run1", "hypothesisId": "C", "location": "settings.py:26", "message": "API key after strip", "data": {"length": len(api_key), "first_3": api_key[:3] if len(api_key) >= 3 else "", "last_3": api_key[-3:] if len(api_key) >= 3 else ""}, "timestamp": __import__("time").time() * 1000}) + "\n")
    except Exception:
        pass
    # #endregion
    return Settings(
        anthropic_api_key=api_key,
        default_source_lang=os.getenv("DEFAULT_SOURCE_LANG", "fr"),
        default_target_lang=os.getenv("DEFAULT_TARGET_LANG", "en"),
        data_root=data_root,
    )

