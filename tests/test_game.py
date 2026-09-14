import sqlite3

import meshtrail_plugin.game as game_module
from meshtrail_plugin.game import PLAYER_GUIDE_URL, PRAIRIE_MESH_OPERATORS, TrailStore, fit_utf8


def test_new_player_and_persistent_progress(tmp_path):
    game = TrailStore(tmp_path / "trail.db", random_seed=1848)
    opening = game.handle("aabbcc", "START", timestamp=1)
    assert "Independence" in opening
    assert "rabbit seal" in opening
    assert "GUIDE" in opening
    assert len(opening.encode("utf-8")) <= 145
    reply = game.handle("aabbcc", "GO", timestamp=2)
    assert "Kansas River" in reply
    assert "FERRY" in game.handle("aabbcc", "STATUS", timestamp=3)
    assert "safely across" in game.handle("aabbcc", "FERRY", timestamp=4)
    assert "55/2000mi" in game.handle("aabbcc", "STATUS", timestamp=5)


def test_players_are_isolated(tmp_path):
    game = TrailStore(tmp_path / "trail.db")
    game.handle("player1", "start", timestamp=1)
    game.handle("player1", "go", timestamp=2)
    game.handle("player2", "start", timestamp=1)
    assert "0/2000mi" in game.handle("player2", "status", timestamp=2)


def test_active_player_limit_expires_without_losing_saves(tmp_path, monkeypatch):
    now = 10_000
    monkeypatch.setattr(game_module.time, "time", lambda: now)
    game = TrailStore(
        tmp_path / "trail.db", max_active_players=2, active_player_timeout_seconds=900
    )
    game.handle("player1", "start", timestamp=1)
    game.handle("player1", "go", timestamp=2)
    game.handle("player2", "start", timestamp=1)

    busy = game.handle("player3", "start", timestamp=1)
    assert "busy (2/2 wagon parties)" in busy

    now += 901
    opening = game.handle("player3", "start", timestamp=2)
    assert "Independence" in opening
    game.handle("player4", "start", timestamp=1)

    busy_return = game.handle("player1", "status", timestamp=3)
    assert "busy (2/2 wagon parties)" in busy_return

    now += 901
    restored = game.handle("player1", "status", timestamp=4)
    assert "Kansas River" in restored


def test_guide_is_available_without_starting_a_game(tmp_path):
    game = TrailStore(tmp_path / "trail.db")
    reply = game.handle("new-player", "guide", timestamp=1)
    assert PLAYER_GUIDE_URL in reply
    assert len(reply.encode("utf-8")) <= 145


def test_inactive_saves_expire_after_retention_period(tmp_path, monkeypatch):
    now = 10_000
    monkeypatch.setattr(game_module.time, "time", lambda: now)
    game = TrailStore(tmp_path / "trail.db", save_retention_seconds=30 * 86400)
    game.handle("old-party", "start", timestamp=1)
    game.handle("old-party", "go", timestamp=2)

    now += 30 * 86400 + 1
    expired = game.handle("old-party", "status", timestamp=3)
    assert "Send START" in expired


def test_duplicate_ping_message_is_ignored(tmp_path):
    game = TrailStore(tmp_path / "trail.db")
    game.handle("player", "start", timestamp=1)
    first = game.handle("player", "go", timestamp=2)
    duplicate = game.handle("player", "go", timestamp=2)
    assert first is not None
    assert duplicate is None


def test_strategy_commands(tmp_path):
    game = TrailStore(tmp_path / "trail.db")
    game.handle("player", "start", timestamp=1)
    assert "strenuous" in game.handle("player", "pace strenuous", timestamp=2)
    assert "bare" in game.handle("player", "rations bare", timestamp=3)
    assert "gained" in game.handle("player", "hunt", timestamp=4)
    assert "Rested" in game.handle("player", "rest", timestamp=5)


def test_trading_post_at_independence(tmp_path):
    game = TrailStore(tmp_path / "trail.db")
    game.handle("buyer", "start", timestamp=1)
    assert "food 10lb/$2" in game.handle("buyer", "shop", timestamp=2)
    assert "Food 1100; cash $380" in game.handle("buyer", "buy food 100", timestamp=3)
    assert "Ammo 70; cash $376" in game.handle("buyer", "buy ammo 20", timestamp=4)


def test_trading_requires_a_post_and_enough_cash(tmp_path):
    path = tmp_path / "trail.db"
    game = TrailStore(path)
    game.handle("buyer", "start", timestamp=1)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE sessions SET money=1 WHERE sender_id='buyer'")
    assert "costs $2" in game.handle("buyer", "buy food 10", timestamp=2)
    game.handle("buyer", "go", timestamp=3)
    game.handle("buyer", "caulk", timestamp=4)
    assert "No trading post here" in game.handle("buyer", "shop", timestamp=5)


def test_fort_bridger_opens_a_trading_post(tmp_path):
    path = tmp_path / "trail.db"
    game = TrailStore(path, random_seed=1848)
    game.handle("buyer", "start", timestamp=1)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE sessions SET distance=1170 WHERE sender_id='buyer'")
    assert "Fort Bridger: trading post open" in game.handle("buyer", "go", timestamp=2)
    assert "Fort Bridger post" in game.handle("buyer", "shop", timestamp=3)


def test_mesh_telegraph_commands_use_cells(tmp_path):
    game = TrailStore(tmp_path / "trail.db")
    game.handle("player", "start", timestamp=1)
    assert "LoRa Aether Telegraph" in game.handle("player", "ping", timestamp=2)
    beacon = game.handle("player", "beacon", timestamp=3)
    assert "BEACON ACK" in beacon
    assert any(operator in beacon for operator in PRAIRIE_MESH_OPERATORS)
    assert "cells 95%" in game.handle("player", "ping", timestamp=4)


def test_fort_kearny_contains_nebraska_mesh_easter_egg(tmp_path):
    game = TrailStore(tmp_path / "trail.db", random_seed=1848)
    game.handle("local", "start", timestamp=1)
    replies = []
    timestamp = 2
    for _ in range(12):
        reply = game.handle("local", "go", timestamp=timestamp)
        timestamp += 1
        replies.append(reply)
        if reply and "Choose FORD" in reply:
            replies.append(game.handle("local", "ferry", timestamp=timestamp))
            timestamp += 1
        if any(item and "Nebraska Mesh" in item for item in replies):
            break
    fort_reply = next(reply for reply in replies if reply and "Nebraska Mesh" in reply)
    assert "DOS_" in fort_reply
    assert "Nightcrawler" in fort_reply


def test_platte_route_and_south_platte_crossing(tmp_path):
    path = tmp_path / "trail.db"
    game = TrailStore(path, random_seed=1848)
    game.handle("platte", "start", timestamp=1)
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE sessions SET distance=180 WHERE sender_id='platte'")
    assert "Great Platte River Road" in game.handle("platte", "go", timestamp=2)

    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE sessions SET distance=430 WHERE sender_id='platte'")
    crossing = game.handle("platte", "go", timestamp=3)
    assert "South Platte River" in crossing
    assert "FORD" in crossing


def test_reset_starts_fresh(tmp_path):
    game = TrailStore(tmp_path / "trail.db")
    game.handle("player", "start", timestamp=1)
    game.handle("player", "go", timestamp=2)
    assert "Independence" in game.handle("player", "reset", timestamp=3)
    assert "0/2000mi" in game.handle("player", "status", timestamp=4)


def test_fit_utf8_obeys_packet_budget():
    result = fit_utf8("prairie " * 100, 145)
    assert len(result.encode("utf-8")) <= 145
    assert result.endswith("...")

