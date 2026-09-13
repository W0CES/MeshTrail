"""Supervised MeshTrail service entrypoint."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import signal
from typing import Protocol

from .config import ConfigError, Settings
from .game import TrailStore, fit_utf8
from .meshcore_client import IncomingMessage, MeshCoreClient

logger = logging.getLogger(__name__)


class GameHandler(Protocol):
    def handle(self, sender_id: str, command: str, *, timestamp: int | None = None) -> str | None: ...


class MeshTrailService:
    def __init__(self, settings: Settings, meshcore: MeshCoreClient, game: GameHandler) -> None:
        self.settings = settings
        self.meshcore = meshcore
        self.game = game
        self.stop_event = asyncio.Event()

    async def run(self) -> None:
        self._register_signals()
        await self.meshcore.run(self.handle_message, self.stop_event)
        await self.meshcore.close()

    async def handle_message(self, message: IncomingMessage) -> None:
        if message.txt_type != 0:
            return
        command = message.text.strip()
        if not command:
            return
        if len(command.encode("utf-8")) > self.settings.max_command_bytes:
            await self.meshcore.send_text(
                message.sender_prefix,
                fit_utf8("Command too long. Send HELP.", self.settings.max_reply_bytes),
            )
            return
        sender_id = message.sender_prefix[:6].hex()
        logger.info(
            "Trail command sender=%s command_sha=%s",
            sender_id,
            hashlib.sha256(command.encode()).hexdigest()[:10],
        )
        response = await asyncio.to_thread(
            self.game.handle, sender_id, command, timestamp=message.timestamp
        )
        if response is not None:
            await self.meshcore.send_text(
                message.sender_prefix, fit_utf8(response, self.settings.max_reply_bytes)
            )

    def _register_signals(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.stop_event.set)
            except NotImplementedError:
                signal.signal(sig, lambda *_: self.stop_event.set())


async def _async_main() -> int:
    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    meshcore = MeshCoreClient(host=settings.meshcore_host, port=settings.meshcore_port)
    game = TrailStore(
        settings.database_path,
        duplicate_ttl_seconds=settings.duplicate_ttl_seconds,
        random_seed=settings.random_seed,
    )
    await MeshTrailService(settings, meshcore, game).run()
    return 0


def main() -> int:
    try:
        return asyncio.run(_async_main())
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

