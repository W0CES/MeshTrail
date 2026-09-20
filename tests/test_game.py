import sqlite3

import meshtrail_plugin.game as game_module
from meshtrail_plugin.game import (
    HELP_SUMMARY,
    HELP_TOPICS,
    PLAYER_GUIDE_URL,
    PRAIRIE_MESH_OPERATORS,
    TrailStore,
    fit_utf8,
)


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


def test_help_topics_work_before_and_during_a_game(tmp_path):
    game = TrailStore(tmp_path / "trail.db")

    assert "HELP <command>" in game.handle("new-player", "help", timestamp=1)
    assert "BUY FOOD" in game.handle("new-player", "help buy", timestamp=2)
    assert "STRENUOUS" in game.handle("new-player", "HELP PACE", timestamp=3)
    assert "FILLING" in game.handle("new-player", "help rations", timestamp=4)

    game.handle("player", "start", timestamp=1)
    assert "safer than FORD" in game.handle("player", "help caulk", timestamp=2)
    assert "Shortcut: INV" in game.handle("player", "help inv", timestamp=3)
    assert "No help is available" in game.handle("player", "help telegraphy", timestamp=4)


def test_every_help_reply_fits_mesh_packet_budget():
    assert len(HELP_SUMMARY.encode("utf-8")) <= 145
    assert all(len(reply.encode("utf-8")) <= 145 for reply in HELP_TOPICS.values())


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


def test_medicine_can_be_bought_used_and_aids_recovery(tmp_path):
    path = tmp_path / "trail.db"
    game = TrailStore(path)
    game.handle("patient", "start", timestamp=1)
    assert "Medicine 2; cash $370" in game.handle(
        "patient", "buy medicine 2", timestamp=2
    )
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE sessions SET health=70 WHERE sender_id='patient'"
        )

    assert "Health 73; 1 remain" in game.handle("patient", "medicine", timestamp=3)
    rested = game.handle("patient", "rest", timestamp=4)
    assert "health 90" in rested
    assert "Medicine aided recovery" in rested
    with sqlite3.connect(path) as connection:
        medicine, care = connection.execute(
            "SELECT medicine,medicine_care FROM sessions WHERE sender_id='patient'"
        ).fetchone()
    assert medicine == 1
    assert care == 0


def test_medicine_prevents_illness_or_party_can_endure(tmp_path):
    path = tmp_path / "trail.db"
    game = TrailStore(path)
    game.handle("prepared", "start", timestamp=1)
    game.handle("unprepared", "start", timestamp=1)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE sessions SET health=80,medicine=1,"
            "pending_event='illness:dysentery:12' WHERE sender_id='prepared'"
        )
        connection.execute(
            "UPDATE sessions SET health=80,pending_event='illness:dysentery:12' "
            "WHERE sender_id='unprepared'"
        )

    prevented = game.handle("prepared", "medicine", timestamp=2)
    assert "Medicine prevents dysentery" in prevented
    endured = game.handle("unprepared", "endure", timestamp=2)
    assert "health falls by 12 to 68" in endured

    with sqlite3.connect(path) as connection:
        prepared = connection.execute(
            "SELECT health,medicine,pending_event FROM sessions WHERE sender_id='prepared'"
        ).fetchone()
        unprepared = connection.execute(
            "SELECT health,pending_event FROM sessions WHERE sender_id='unprepared'"
        ).fetchone()
    assert prepared == (80, 0, "")
    assert unprepared == (68, "")


def test_trail_traders_offer_food_ammo_and_medicine(tmp_path):
    path = tmp_path / "trail.db"
    game = TrailStore(path, max_active_players=4)
    offers = {
        "food-buyer": ("trade:0:food:100:15", "100 lb food", 1100, 385),
        "ammo-buyer": ("trade:1:ammo:20:8", "20 ammo", 70, 392),
        "medicine-buyer": ("trade:2:medicine:1:10", "1 medicine", 1, 390),
    }
    for sender, (pending, _, _, _) in offers.items():
        game.handle(sender, "start", timestamp=1)
        with sqlite3.connect(path) as connection:
            connection.execute(
                "UPDATE sessions SET pending_event=? WHERE sender_id=?",
                (pending, sender),
            )

    for sender, (_, description, expected_total, expected_money) in offers.items():
        reply = game.handle(sender, "trade", timestamp=2)
        assert description in reply
        item = sender.removesuffix("-buyer")
        with sqlite3.connect(path) as connection:
            total, money, pending = connection.execute(
                f"SELECT {item},money,pending_event FROM sessions WHERE sender_id=?",
                (sender,),
            ).fetchone()
        assert (total, money, pending) == (expected_total, expected_money, "")


def test_trail_trade_can_be_declined(tmp_path):
    path = tmp_path / "trail.db"
    game = TrailStore(path)
    game.handle("walker", "start", timestamp=1)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE sessions SET pending_event='trade:3:food:100:15' "
            "WHERE sender_id='walker'"
        )
    assert "pass Silas Webb's offer" in game.handle("walker", "pass", timestamp=2)
    with sqlite3.connect(path) as connection:
        assert connection.execute(
            "SELECT pending_event FROM sessions WHERE sender_id='walker'"
        ).fetchone()[0] == ""


def test_choice_based_trail_hazards_cost_time_and_supplies(tmp_path):
    path = tmp_path / "trail.db"
    game = TrailStore(path, max_active_players=3, random_seed=1848)
    hazards = {
        "bison": ("hazard:bison", "wait"),
        "storm": ("hazard:storm", "camp"),
        "wagon": ("hazard:breakdown", "spare"),
    }
    for sender, (pending, _) in hazards.items():
        game.handle(sender, "start", timestamp=1)
        with sqlite3.connect(path) as connection:
            connection.execute(
                "UPDATE sessions SET pending_event=? WHERE sender_id=?",
                (pending, sender),
            )

    assert "waits safely" in game.handle("bison", "wait", timestamp=2)
    assert "camps safely" in game.handle("storm", "camp", timestamp=2)
    assert "spare part repairs" in game.handle("wagon", "spare", timestamp=2)

    with sqlite3.connect(path) as connection:
        bison = connection.execute(
            "SELECT day,food,pending_event FROM sessions WHERE sender_id='bison'"
        ).fetchone()
        storm = connection.execute(
            "SELECT day,food,pending_event FROM sessions WHERE sender_id='storm'"
        ).fetchone()
        wagon = connection.execute(
            "SELECT day,food,parts,pending_event FROM sessions WHERE sender_id='wagon'"
        ).fetchone()
    assert bison == (3, 970, "")
    assert storm == (3, 970, "")
    assert wagon == (2, 985, 2, "")

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE sessions SET pending_event='hazard:bison' WHERE sender_id='bison'"
        )
        connection.execute(
            "UPDATE sessions SET pending_event='hazard:storm' WHERE sender_id='storm'"
        )
        connection.execute(
            "UPDATE sessions SET pending_event='hazard:breakdown' WHERE sender_id='wagon'"
        )
    risky_replies = (
        game.handle("bison", "detour", timestamp=3),
        game.handle("storm", "push", timestamp=3),
        game.handle("wagon", "repair", timestamp=3),
    )
    assert all(reply and "Send GO" in reply for reply in risky_replies)
    assert all(len(reply.encode("utf-8")) <= 145 for reply in risky_replies if reply)

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE sessions SET pending_event='hazard:breakdown' WHERE sender_id='wagon'"
        )
    abandoned = game.handle("wagon", "abandon", timestamp=4)
    assert "Supplies are abandoned" in abandoned
    assert len(abandoned.encode("utf-8")) <= 145


def test_breakdown_without_spare_requires_another_choice(tmp_path):
    path = tmp_path / "trail.db"
    game = TrailStore(path)
    game.handle("wagon", "start", timestamp=1)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE sessions SET parts=0,pending_event='hazard:breakdown' "
            "WHERE sender_id='wagon'"
        )

    assert "Choose REPAIR or ABANDON" in game.handle("wagon", "spare", timestamp=2)
    assert "broken wagon" in game.handle("wagon", "status", timestamp=3)


def test_trail_event_chance_increases_westward():
    assert TrailStore._event_chance(0) == 0.42
    assert TrailStore._event_chance(1000) == 0.52
    assert TrailStore._event_chance(2000) == 0.62


def test_rare_jackalope_sighting_lifts_health(tmp_path, monkeypatch):
    class JackalopeRoll:
        @staticmethod
        def randint(low, high):
            return 0 if low <= 0 <= high else low

        @staticmethod
        def random():
            return 0.0

        @staticmethod
        def randrange(_stop):
            return 13 if _stop == 16 else 0

    path = tmp_path / "trail.db"
    game = TrailStore(path)
    game.handle("rabbit", "start", timestamp=1)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE sessions SET distance=130,health=90 WHERE sender_id='rabbit'"
        )
    monkeypatch.setattr(game, "_rng", lambda _sender, _turns, _action: JackalopeRoll())

    reply = game.handle("rabbit", "go", timestamp=2)
    assert "elusive jackalope" in reply
    assert "health 95" in reply


def test_forage_spends_a_day_and_may_find_herbal_medicine(tmp_path):
    path = tmp_path / "trail.db"
    game = TrailStore(path, random_seed=1848)
    game.handle("forager", "start", timestamp=1)
    reply = game.handle("forager", "forage", timestamp=2)
    assert "Foraged 1 day" in reply
    with sqlite3.connect(path) as connection:
        day, food, medicine = connection.execute(
            "SELECT day,food,medicine FROM sessions WHERE sender_id='forager'"
        ).fetchone()
    assert day == 2
    assert food == 985
    assert medicine in {0, 1, 2}


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


def test_community_operator_names_are_available_and_fit_replies():
    added_names = {
        "Yellowcooln",
        "Treehouse〰𑃰𑃰",
        "RightUp",
        "Meaningless",
        "timmo_3.14",
    }
    assert added_names <= set(PRAIRIE_MESH_OPERATORS)
    replies = [
        f"BEACON ACK 5/5 via {operator}. Great Platte River Road is 2000mi west. Cells 100%."
        for operator in PRAIRIE_MESH_OPERATORS
    ]
    assert all(len(reply.encode("utf-8")) <= 145 for reply in replies)


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
