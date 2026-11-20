from __future__ import annotations

import os
from dataclasses import dataclass


def _parse_chat_ids(raw: str) -> tuple[int, ...]:
    return tuple(int(x) for x in raw.replace(" ", "").split(",") if x)


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    portainer_url: str
    portainer_api_key: str
    allowed_chat_ids: tuple[int, ...]
    default_endpoint_id: int | None

    @classmethod
    def from_env(cls) -> Config:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

        api_key = os.environ.get("PORTAINER_API_KEY", "")
        if not api_key:
            raise RuntimeError("PORTAINER_API_KEY is not set")

        url = os.environ.get("PORTAINER_URL", "http://host.docker.internal:9000").rstrip("/")

        endpoint_raw = os.environ.get("PORTAINER_ENDPOINT_ID", "").strip()

        return cls(
            telegram_bot_token=token,
            portainer_url=url,
            portainer_api_key=api_key,
            allowed_chat_ids=_parse_chat_ids(os.environ.get("ALLOWED_CHAT_IDS", "")),
            default_endpoint_id=int(endpoint_raw) if endpoint_raw else None,
        )
