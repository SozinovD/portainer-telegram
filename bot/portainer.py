from __future__ import annotations

import re

import httpx

_ANSI_RE = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")


class PortainerError(Exception):
    pass


def _demux(data: bytes) -> str:
    """Decode docker attach-stream framing: 8-byte header (stream type + size) per chunk."""
    out = bytearray()
    i = 0
    parsed = False
    while i + 8 <= len(data):
        size = int.from_bytes(data[i + 4 : i + 8], "big")
        chunk = data[i + 8 : i + 8 + size]
        if len(chunk) < size:
            break
        out += chunk
        i += 8 + size
        parsed = True
    if not parsed and data:
        # TTY mode: raw output without framing
        out = bytearray(data)
    return out.decode("utf-8", errors="replace")


class PortainerClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-API-Key": api_key},
            timeout=httpx.Timeout(30.0, read=120.0),
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            resp = await self._http.request(method, path, **kwargs)
        except httpx.HTTPError as e:
            raise PortainerError(f"Ошибка сети: {e}") from e
        if resp.status_code in (401, 403):
            raise PortainerError("Ошибка авторизации: проверьте PORTAINER_API_KEY")
        if resp.status_code >= 400:
            raise PortainerError(f"Portainer {resp.status_code}: {resp.text[:300]}")
        return resp

    async def endpoints(self) -> list[dict]:
        return (await self._request("GET", "/api/endpoints")).json()

    async def containers(self, endpoint_id: int) -> list[dict]:
        resp = await self._request(
            "GET",
            f"/api/endpoints/{endpoint_id}/docker/containers/json",
            params={"all": 1},
        )
        return resp.json()

    async def inspect(self, endpoint_id: int, container_id: str) -> dict:
        resp = await self._request(
            "GET", f"/api/endpoints/{endpoint_id}/docker/containers/{container_id}/json"
        )
        return resp.json()

    async def action(self, endpoint_id: int, container_id: str, action: str) -> None:
        await self._request(
            "POST", f"/api/endpoints/{endpoint_id}/docker/containers/{container_id}/{action}"
        )

    async def logs(self, endpoint_id: int, container_id: str, tail: int = 50) -> str:
        resp = await self._request(
            "GET",
            f"/api/endpoints/{endpoint_id}/docker/containers/{container_id}/logs",
            params={"stdout": 1, "stderr": 1, "tail": tail, "timestamps": 0},
        )
        text = _demux(resp.content)
        text = _ANSI_RE.sub(b"", text.encode()).decode("utf-8", errors="replace")
        return text

    async def stats(self, endpoint_id: int, container_id: str) -> dict:
        resp = await self._request(
            "GET",
            f"/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stats",
            params={"stream": "false"},
        )
        return resp.json()
