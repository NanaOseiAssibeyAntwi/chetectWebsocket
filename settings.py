from __future__ import annotations

import os
from dataclasses import dataclass


def _get_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def _get_list(name: str, default: str = "*") -> list[str]:
    raw_value = os.getenv(name, default).strip()
    if not raw_value:
        return ["*"]
    return [item.strip() for item in raw_value.split(",") if item.strip()] or ["*"]


@dataclass(frozen=True)
class Settings:
    model_api_base_url: str = os.getenv("MODEL_API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    allowed_origins: list[str] = None
    auto_create_model_session: bool = _get_bool("AUTO_CREATE_MODEL_SESSION", True)
    model_api_timeout_seconds: float = _get_float("MODEL_API_TIMEOUT_SECONDS", 120.0)
    max_payload_bytes: int = _get_int("MAX_PAYLOAD_BYTES", 8 * 1024 * 1024)
    default_inference_max_width: int = _get_int("DEFAULT_INFERENCE_MAX_WIDTH", 480)
    default_sample_every_n_frames: int = _get_int("DEFAULT_SAMPLE_EVERY_N_FRAMES", 10)
    default_max_frames: int = _get_int("DEFAULT_MAX_FRAMES", 20)
    default_max_alerts: int = _get_int("DEFAULT_MAX_ALERTS", 3)
    default_video_response_mode: str = os.getenv("DEFAULT_VIDEO_RESPONSE_MODE", "summary").strip().lower()

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_origins", _get_list("ALLOWED_ORIGINS"))
        if self.default_video_response_mode not in {"summary", "full"}:
            object.__setattr__(self, "default_video_response_mode", "summary")


settings = Settings()

