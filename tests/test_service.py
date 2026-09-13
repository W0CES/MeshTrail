from pathlib import Path

import pytest

from meshtrail_plugin.config import Settings
from meshtrail_plugin.game import TrailStore
from meshtrail_plugin.meshcore_client import IncomingMessage
from meshtrail_plugin.service import MeshTrailService


class FakeMeshCore:
    def __init__(self):
        self.sent = []

    async def send_text(self, recipient, text):
        self.sent.append((recipient, text))
        return True


@pytest.mark.asyncio
async def test_service_replies_within_budget(tmp_path):
    settings = Settings("127.0.0.1", 5002, Path(tmp_path / "db"), 80, 80, 600, 1848, "INFO")
    meshcore = FakeMeshCore()
    service = MeshTrailService(settings, meshcore, TrailStore(settings.database_path))
    message = IncomingMessage(b"\x01\x02\x03\x04\x05\x06", "start", 1, 0, 0, None)
    await service.handle_message(message)
    assert len(meshcore.sent) == 1
    assert len(meshcore.sent[0][1].encode()) <= 80


@pytest.mark.asyncio
async def test_service_ignores_non_plain_messages(tmp_path):
    settings = Settings("127.0.0.1", 5002, Path(tmp_path / "db"), 145, 80, 600, 1848, "INFO")
    meshcore = FakeMeshCore()
    service = MeshTrailService(settings, meshcore, TrailStore(settings.database_path))
    message = IncomingMessage(b"\x01\x02\x03\x04\x05\x06", "start", 1, 1, 0, None)
    await service.handle_message(message)
    assert meshcore.sent == []

