"""Low-level RouterOS API client for MikroTik API ports ``8728`` / ``8729``."""

from __future__ import annotations

import asyncio
import hashlib
import ssl
from dataclasses import dataclass
from typing import Mapping, Sequence

from app.integrations.mikrotik.errors import MikrotikIntegrationError


@dataclass(slots=True)
class RouterOSResponse:
    rows: list[dict[str, str]]
    done: dict[str, str]


def _encode_length(length: int) -> bytes:
    if length < 0:
        raise ValueError("RouterOS word length cannot be negative")
    if length < 0x80:
        return bytes([length])
    if length < 0x4000:
        length |= 0x8000
        return bytes([(length >> 8) & 0xFF, length & 0xFF])
    if length < 0x200000:
        length |= 0xC00000
        return bytes([(length >> 16) & 0xFF, (length >> 8) & 0xFF, length & 0xFF])
    if length < 0x10000000:
        length |= 0xE0000000
        return bytes([(length >> 24) & 0xFF, (length >> 16) & 0xFF, (length >> 8) & 0xFF, length & 0xFF])
    if length < 0x100000000:
        return bytes([0xF0, (length >> 24) & 0xFF, (length >> 16) & 0xFF, (length >> 8) & 0xFF, length & 0xFF])
    raise ValueError("RouterOS word length is too large")


async def _read_length(reader: asyncio.StreamReader) -> int:
    first = (await reader.readexactly(1))[0]
    if first < 0x80:
        return first
    if first < 0xC0:
        second = (await reader.readexactly(1))[0]
        return ((first & 0x3F) << 8) | second
    if first < 0xE0:
        second, third = await reader.readexactly(2)
        return ((first & 0x1F) << 16) | (second << 8) | third
    if first < 0xF0:
        second, third, fourth = await reader.readexactly(3)
        return ((first & 0x0F) << 24) | (second << 16) | (third << 8) | fourth
    if first == 0xF0:
        return int.from_bytes(await reader.readexactly(4), "big")
    raise ValueError(f"Unsupported RouterOS length prefix: 0x{first:02x}")


def _format_value(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _attribute_words(attributes: Mapping[str, object] | None) -> list[str]:
    if not attributes:
        return []
    out: list[str] = []
    for key, value in attributes.items():
        if value is None:
            continue
        out.append(f"={key}={_format_value(value)}")
    return out


def _query_words(queries: Sequence[str] | None) -> list[str]:
    if not queries:
        return []
    out: list[str] = []
    for query in queries:
        out.append(query if query.startswith("?") else f"?{query}")
    return out


def _words_to_dict(words: Sequence[str]) -> dict[str, str]:
    data: dict[str, str] = {}
    for word in words:
        if not word:
            continue
        if word.startswith("="):
            _, key, value = word.split("=", 2)
            data[key] = value
            continue
        if word.startswith(".") and "=" in word:
            key, value = word.split("=", 1)
            data[key] = value
            continue
        data[word] = ""
    return data


class MikroTikClient:
    """Connection handle for a single RouterOS API endpoint."""

    def __init__(
        self,
        host: str,
        username: str = "",
        password: str = "",
        port: int = 8728,
        *,
        use_tls: bool = False,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.use_tls = use_tls

    async def call(
        self,
        command: str,
        *,
        attributes: Mapping[str, object] | None = None,
        queries: Sequence[str] | None = None,
    ) -> RouterOSResponse:
        return (await self.call_many([(command, attributes, queries)]))[0]

    async def call_many(
        self,
        commands: Sequence[tuple[str, Mapping[str, object] | None, Sequence[str] | None]],
    ) -> list[RouterOSResponse]:
        reader, writer = await self._open_connection()
        try:
            try:
                await self._login_modern(reader, writer)
            except MikrotikIntegrationError as exc:
                if exc.code != "auth":
                    raise
                await self._close_connection(writer)
                reader, writer = await self._open_connection()
                await self._login_legacy(reader, writer)

            responses: list[RouterOSResponse] = []
            for command, attributes, queries in commands:
                await self._write_sentence(
                    writer,
                    [command, *_attribute_words(attributes), *_query_words(queries)],
                )
                responses.append(await self._read_response(reader))
            return responses
        finally:
            await self._close_connection(writer)

    async def _open_connection(self) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        ssl_context: ssl.SSLContext | None = None
        if self.use_tls:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        return await asyncio.open_connection(self.host, self.port, ssl=ssl_context)

    async def _close_connection(self, writer: asyncio.StreamWriter) -> None:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            return

    async def _login_modern(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await self._write_sentence(
            writer,
            [
                "/login",
                f"=name={self.username}",
                f"=password={self.password}",
            ],
        )
        await self._read_response(reader)

    async def _login_legacy(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await self._write_sentence(writer, ["/login"])
        challenge = await self._read_response(reader)
        token = challenge.done.get("ret")
        if not token:
            raise MikrotikIntegrationError(
                "RouterOS legacy login challenge was not returned",
                code="auth",
                retryable=False,
            )
        digest = hashlib.md5(b"\x00" + self.password.encode("utf-8") + bytes.fromhex(token)).hexdigest()
        await self._write_sentence(
            writer,
            [
                "/login",
                f"=name={self.username}",
                f"=response=00{digest}",
            ],
        )
        await self._read_response(reader)

    async def _write_sentence(self, writer: asyncio.StreamWriter, words: Sequence[str]) -> None:
        for word in words:
            data = word.encode("utf-8")
            writer.write(_encode_length(len(data)))
            writer.write(data)
        writer.write(b"\x00")
        await writer.drain()

    async def _read_response(self, reader: asyncio.StreamReader) -> RouterOSResponse:
        rows: list[dict[str, str]] = []
        done: dict[str, str] = {}
        while True:
            words = await self._read_sentence(reader)
            if not words:
                continue
            kind = words[0]
            payload = _words_to_dict(words[1:])
            if kind == "!re":
                rows.append(payload)
                continue
            if kind == "!done":
                done = payload
                return RouterOSResponse(rows=rows, done=done)
            if kind in {"!trap", "!fatal"}:
                msg = payload.get("message") or payload.get("category") or "RouterOS command failed"
                lower = msg.lower()
                code = "routeros_trap"
                retryable = False
                if "log in" in lower or "login" in lower:
                    code = "auth"
                elif "timeout" in lower:
                    code = "timeout"
                    retryable = True
                elif kind == "!fatal":
                    code = "routeros_fatal"
                raise MikrotikIntegrationError(msg, code=code, retryable=retryable)

    async def _read_sentence(self, reader: asyncio.StreamReader) -> list[str]:
        words: list[str] = []
        while True:
            length = await _read_length(reader)
            if length == 0:
                return words
            word = await reader.readexactly(length)
            words.append(word.decode("utf-8", errors="replace"))
