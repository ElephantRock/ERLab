"""MCP transports — StdIO and HTTP/SSE."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseTransport(ABC):
    """Abstract transport for MCP JSON-RPC communication."""

    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        ...

    @abstractmethod
    async def send_request(self, method: str, params: dict[str, Any] | None = None) -> dict:
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        ...

    def _next_id(self) -> int:
        self._request_counter = getattr(self, "_request_counter", 0) + 1
        return self._request_counter


class StdIOTransport(BaseTransport):
    """Transport via subprocess stdin/stdout using JSON-RPC 2.0."""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self._command = command
        self._args = args or []
        self._env = env
        self._process: asyncio.subprocess.Process | None = None
        self._request_counter = 0

    async def connect(self) -> None:
        import os

        env = {**os.environ, **(self._env or {})}
        self._process = await asyncio.create_subprocess_exec(
            self._command,
            *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        logger.info("StdIOTransport connected: %s %s", self._command, " ".join(self._args))

    async def disconnect(self) -> None:
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None

    async def send_request(self, method: str, params: dict[str, Any] | None = None) -> dict:
        if not self._process or self._process.returncode is not None:
            raise ConnectionError("StdIO process not running")

        request: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params is not None:
            request["params"] = params

        line = json.dumps(request) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()

        response_line = await self._process.stdout.readline()
        if not response_line:
            raise ConnectionError("StdIO process closed stdout")

        response = json.loads(response_line.decode().strip())

        if "error" in response:
            err = response["error"]
            raise RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}")

        return response.get("result", {})

    @property
    def is_connected(self) -> bool:
        return self._process is not None and self._process.returncode is None


class HTTPTransport(BaseTransport):
    """Transport via HTTP/SSE using JSON-RPC 2.0."""

    def __init__(self, url: str, timeout: float = 30.0) -> None:
        self._url = url
        self._timeout = timeout
        self._request_counter = 0
        self._connected = False
        self._client: Any = None

    async def connect(self) -> None:
        try:
            import httpx

            self._client = httpx.AsyncClient(timeout=self._timeout)
            self._connected = True
            logger.info("HTTPTransport connected to %s", self._url)
        except ImportError:
            raise RuntimeError("httpx required for HTTP MCP transport")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False

    async def send_request(self, method: str, params: dict[str, Any] | None = None) -> dict:
        if not self._client:
            raise ConnectionError("HTTP client not initialized")

        request: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params is not None:
            request["params"] = params

        response = await self._client.post(
            self._url,
            json=request,
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            err = data["error"]
            raise RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}")

        return data.get("result", {})

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None
