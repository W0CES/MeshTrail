"""Deterministic, SQLite-backed trail simulation."""

from __future__ import annotations

import hashlib
import random
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path

TRAIL_END = 2000
START_FOOD = 1000
START_AMMO = 50
START_PARTS = 3
START_MEDICINE = 0
PARTY_SIZE = 5
FOOD_LOT_SIZE = 10
FOOD_LOT_PRICE = 2
AMMO_LOT_SIZE = 10
AMMO_LOT_PRICE = 2
MEDICINE_PRICE = 15
PLAYER_GUIDE_URL = "https://github.com/W0CES/MeshTrail/blob/main/PLAYER_GUIDE.md"
PACE_MILES = {"steady": 95, "strenuous": 120, "grueling": 145}
RATION_FOOD = {"filling": 3, "meager": 2, "bare": 1}
ALIASES = {"travel": "go", "continue": "go", "s": "status", "inv": "supplies", "?": "help"}
HELP_ALIASES = {
    "travel": "go",
    "continue": "go",
    "s": "status",
    "inv": "supplies",
    "radio": "ping",
    "rivers": "river",
    "offers": "trade",
    "new": "reset",
    "/reset": "reset",
    "/new": "reset",
    "?": "help",
    "encounters": "encounter",
    "hazard": "encounter",
    "hazards": "encounter",
}
HELP_SUMMARY = (
    "Send HELP <command>. START GO STATUS SUPPLIES SHOP BUY PING BEACON HUNT FORAGE "
    "REST MEDICINE PACE RATIONS GUIDE RESET RIVER TRADE ENCOUNTER."
)
HELP_TOPICS = {
    "help": "HELP lists commands. Send HELP followed by a command for its use, choices, and an example. Example: HELP PACE.",
    "start": "START forms a five-person wagon party at Independence. To replace an existing journey and begin again, use RESET.",
    "go": "GO travels one turn using your PACE and RATIONS. It may reach a landmark or trigger a river, illness, or trader. Also: TRAVEL, CONTINUE.",
    "status": "STATUS shows the day, miles traveled, food, health, and next landmark or pending choice. Shortcut: S.",
    "supplies": "SUPPLIES shows food, ammo, medicine, parts, cash, telegraph cells, and aerial condition. Shortcut: INV.",
    "shop": "SHOP lists prices and cash at Independence or a fort. Elsewhere it tells you where the nearest buying opportunities are.",
    "buy": "At a post use BUY FOOD <10-5000>, BUY AMMO <10-500>, or BUY MEDICINE <1-20>. Food and ammo use multiples of 10.",
    "ping": "PING checks telegraph cells, aerial condition, current location, and distance to the next mesh relay.",
    "beacon": "BEACON sends a trail report through the LoRa Aether Telegraph. It uses 5% of the telegraph cells.",
    "hunt": "HUNT spends 5 ammo and 2 days to gain food. The party also eats its selected RATIONS during those days.",
    "forage": "FORAGE spends 1 day and that day's rations searching for herbal medicine. You may find 0, 1, or 2 bottles.",
    "rest": "REST spends 3 days and food to recover health. Recently used MEDICINE improves recovery by about 20%.",
    "medicine": "MEDICINE uses 1 bottle to restore 3 health and improve the next REST. During an illness choice, it prevents the illness.",
    "pace": "PACE sets travel: STEADY (~95mi), STRENUOUS (~120mi, small health cost), or GRUELING (~145mi, larger cost). Example: PACE STEADY.",
    "rations": "RATIONS sets daily food per traveler: FILLING 3lb (may heal), MEAGER 2lb, or BARE 1lb (hurts health). Example: RATIONS MEAGER.",
    "guide": "GUIDE returns a link to the complete beginner's Player Guide. It works before or during a journey.",
    "reset": "RESET permanently replaces your current journey with a new wagon party at Independence. Aliases: NEW, /RESET, /NEW.",
    "river": "At a river choose FORD, CAULK, or FERRY. Ask HELP FORD, HELP CAULK, or HELP FERRY to compare the choices.",
    "ford": "FORD crosses a waiting river in 1 day for free. Success depends on depth; failure can cost food and health.",
    "caulk": "CAULK crosses a waiting river in 2 days for free. It is safer than FORD, but failure can still cost food and health.",
    "ferry": "FERRY crosses a waiting river safely in 1 day for $25. If you lack $25, choose FORD or CAULK.",
    "trade": "When a traveler makes an offer, TRADE buys the offered food, ammo, or medicine. Send PASS to decline it.",
    "pass": "PASS declines a waiting traveler's offer without spending cash. You can then send GO to continue.",
    "endure": "During an illness choice, ENDURE saves medicine but accepts the stated health loss. MEDICINE prevents it instead.",
    "encounter": "Trail hazards pause travel for a choice. Bison: WAIT/DETOUR. Storm: CAMP/PUSH. Broken wagon: SPARE/REPAIR/ABANDON.",
    "wait": "WAIT lets a bison herd pass safely. It costs 2 days and the party's selected rations.",
    "detour": "DETOUR spends 1 day going around a bison herd. A rough detour may damage a spare part or cost health.",
    "camp": "CAMP waits out a prairie storm safely. It costs 2 days and rations, with possible light aerial wear.",
    "push": "PUSH travels through a prairie storm in 1 day. It may avoid delay, but risks health and serious aerial damage.",
    "spare": "SPARE uses 1 wagon part and 1 day to fix a breakdown safely. If no parts remain, choose REPAIR or ABANDON.",
    "repair": "REPAIR attempts a wagon fix without a spare. It costs at least 2 days; failure costs another day and some health.",
    "abandon": "ABANDON resolves a broken wagon immediately by discarding some food and ammunition to salvage the wagon.",
    "jackalope": "The elusive JACKALOPE is a rare trail sighting. It requires no choice and lifts the party's spirits and health.",
}
LANDMARKS = (
    (0, "Independence"),
    (210, "Great Platte River Road"),
    (300, "Fort Kearny relay"),
    (475, "South Platte crossing"),
    (550, "Chimney Rock"),
    (650, "Fort Laramie relay"),
    (950, "Independence Rock"),
    (1050, "South Pass relay"),
    (1200, "Fort Bridger"),
    (1350, "Fort Hall relay"),
    (1650, "Fort Boise relay"),
    (1900, "The Dalles relay"),
    (2000, "Willamette Valley"),
)
RELAY_MILES = {300, 650, 1050, 1350, 1650, 1900}
TRADING_POSTS = {
    0: "Independence",
    300: "Fort Kearny",
    650: "Fort Laramie",
    1200: "Fort Bridger",
    1350: "Fort Hall",
    1650: "Fort Boise",
}
PRAIRIE_MESH_OPERATORS = (
    "Applesauce",
    "Heartwood Observer",
    "CourtHouse",
    "NADPEATER",
    "Florence OMA",
    "Tammy",
    "Yellowcooln",
    "Treehouse〰𑃰𑃰",
    "RightUp",
    "Meaningless",
    "timmo_3.14",
)
PRAIRIE_TRADERS = (
    "Ada Mercer",
    "Elias Reed",
    "Mara Pike",
    "Silas Webb",
)
RIVERS = {
    55: ("Kansas River", 3),
    125: ("Big Blue River", 2),
    475: ("South Platte River", 3),
    1150: ("Green River", 4),
    1500: ("Snake River", 5),
    1900: ("Columbia River", 6),
}


class TrailStore:
    """Own all game state; one durable session per six-byte sender prefix."""

    def __init__(
        self,
        database_path: Path | str,
        *,
        duplicate_ttl_seconds: int = 600,
        max_active_players: int = 3,
        active_player_timeout_seconds: int = 900,
        save_retention_seconds: int = 30 * 86400,
        random_seed: int = 1848,
    ) -> None:
        self.database_path = Path(database_path)
        self.duplicate_ttl_seconds = duplicate_ttl_seconds
        self.max_active_players = max_active_players
        self.active_player_timeout_seconds = active_player_timeout_seconds
        self.save_retention_seconds = save_retention_seconds
        self.random_seed = random_seed
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    sender_id TEXT PRIMARY KEY,
                    day INTEGER NOT NULL,
                    distance INTEGER NOT NULL,
                    food INTEGER NOT NULL,
                    ammo INTEGER NOT NULL,
                    parts INTEGER NOT NULL,
                    health INTEGER NOT NULL,
                    pace TEXT NOT NULL,
                    rations TEXT NOT NULL,
                    turns INTEGER NOT NULL,
                    battery INTEGER NOT NULL,
                    aerial INTEGER NOT NULL,
                    money INTEGER NOT NULL DEFAULT 400,
                    medicine INTEGER NOT NULL DEFAULT 0,
                    medicine_care INTEGER NOT NULL DEFAULT 0,
                    shop_location INTEGER NOT NULL DEFAULT -1,
                    pending_event TEXT NOT NULL DEFAULT '',
                    outcome TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS processed_messages (
                    dedupe_key TEXT PRIMARY KEY,
                    processed_at INTEGER NOT NULL
                );
                """
            )
            columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(sessions)")
            }
            if "money" not in columns:
                connection.execute(
                    "ALTER TABLE sessions ADD COLUMN money INTEGER NOT NULL DEFAULT 400"
                )
            if "pending_event" not in columns:
                connection.execute(
                    "ALTER TABLE sessions ADD COLUMN pending_event TEXT NOT NULL DEFAULT ''"
                )
            if "shop_location" not in columns:
                connection.execute(
                    "ALTER TABLE sessions ADD COLUMN shop_location INTEGER NOT NULL DEFAULT -1"
                )
            if "medicine" not in columns:
                connection.execute(
                    "ALTER TABLE sessions ADD COLUMN medicine INTEGER NOT NULL DEFAULT 0"
                )
            if "medicine_care" not in columns:
                connection.execute(
                    "ALTER TABLE sessions ADD COLUMN medicine_care INTEGER NOT NULL DEFAULT 0"
                )

    def handle(self, sender_id: str, command: str, *, timestamp: int | None = None) -> str | None:
        normalized = " ".join(command.strip().lower().split())
        normalized = ALIASES.get(normalized, normalized)
        now = int(time.time())
        digest = hashlib.sha256(normalized.encode()).hexdigest()[:20]
        dedupe_key = f"{sender_id}:{int(timestamp or 0)}:{digest}"

        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM processed_messages WHERE processed_at < ?",
                (now - self.duplicate_ttl_seconds,),
            )
            connection.execute(
                "DELETE FROM sessions WHERE updated_at < ?",
                (now - self.save_retention_seconds,),
            )
            try:
                connection.execute(
                    "INSERT INTO processed_messages VALUES (?, ?)", (dedupe_key, now)
                )
            except sqlite3.IntegrityError:
                return None

            row = connection.execute(
                "SELECT * FROM sessions WHERE sender_id=?", (sender_id,)
            ).fetchone()
            if normalized in {"reset", "new", "/reset", "/new"}:
                connection.execute("DELETE FROM sessions WHERE sender_id=?", (sender_id,))
                row = None
                normalized = "start"
            if normalized == "guide":
                return f"MeshTrail beginner guide: {PLAYER_GUIDE_URL}"
            if normalized == "help" or normalized.startswith("help "):
                return self._help(normalized)
            if row is None:
                if normalized not in {"", "start"}:
                    return "MESH TRAIL: Send START to form a wagon party. HELP lists commands."
                if not self._claim_active_slot(connection, sender_id, now):
                    return self._busy_message()
                self._create_session(connection, sender_id, now)
                return (
                    "MESH TRAIL, 1854. Independence. 5 travelers. Your LoRa Aether Telegraph "
                    "bears a rabbit seal. GO west; PING checks the mesh. New here? GUIDE."
                )

            if not self._claim_active_slot(connection, sender_id, now):
                return self._busy_message()
            connection.execute(
                "UPDATE sessions SET updated_at=? WHERE sender_id=?", (now, sender_id)
            )
            state = dict(row)
            if normalized in {"", "start", "status"}:
                return self._status(state)
            if normalized == "supplies":
                return (
                    f"Food {state['food']}lb; ammo {state['ammo']}; medicine "
                    f"{state['medicine']}; parts {state['parts']}; cash ${state['money']}; "
                    f"cells {state['battery']}%; aerial {state['aerial']}%."
                )
            if normalized in {"ping", "radio"}:
                return self._radio_status(state)
            if normalized == "beacon":
                return self._beacon(connection, sender_id, state, now)
            if normalized.startswith("pace "):
                return self._set_choice(connection, sender_id, state, normalized, "pace", PACE_MILES, now)
            if normalized.startswith("rations "):
                return self._set_choice(
                    connection, sender_id, state, normalized, "rations", RATION_FOOD, now
                )
            if state["outcome"] != "traveling":
                return self._finished(state)
            if state["pending_event"]:
                pending = str(state["pending_event"])
                if pending.startswith("river:"):
                    if normalized in {"ford", "caulk", "ferry"}:
                        return self._resolve_river(connection, sender_id, state, normalized, now)
                    return "A river blocks the trail. Choose FORD, CAULK, or FERRY."
                if pending.startswith("illness:"):
                    if normalized in {"medicine", "endure"}:
                        return self._resolve_illness(
                            connection, sender_id, state, normalized, now
                        )
                    return "Illness threatens the party. Use MEDICINE to prevent it, or ENDURE."
                if pending.startswith("trade:"):
                    if normalized in {"trade", "pass"}:
                        return self._resolve_trade(connection, sender_id, state, normalized, now)
                    return "A trail trader waits for your answer. Send TRADE or PASS."
                if pending.startswith("hazard:"):
                    choices = {
                        "bison": {"wait", "detour"},
                        "storm": {"camp", "push"},
                        "breakdown": {"spare", "repair", "abandon"},
                    }
                    hazard = pending.partition(":")[2]
                    if normalized in choices.get(hazard, set()):
                        return self._resolve_hazard(
                            connection, sender_id, state, hazard, normalized, now
                        )
                    prompts = {
                        "bison": "A bison herd blocks the trail. Choose WAIT or DETOUR.",
                        "storm": "A prairie storm bears down. Choose CAMP or PUSH.",
                        "breakdown": "The wagon is broken. Choose SPARE, REPAIR, or ABANDON.",
                    }
                    return prompts.get(hazard, "The trail hazard is unclear. Send STATUS.")
            if normalized == "shop":
                return self._shop(state)
            if normalized.startswith("buy "):
                return self._buy(connection, sender_id, state, normalized, now)
            if normalized == "medicine":
                return self._use_medicine(connection, sender_id, state, now)
            if normalized == "forage":
                return self._forage(connection, sender_id, state, now)
            if normalized == "rest":
                return self._rest(connection, sender_id, state, now)
            if normalized == "hunt":
                return self._hunt(connection, sender_id, state, now)
            if normalized == "go":
                return self._travel(connection, sender_id, state, now)
            return "Unknown command. Send HELP."

    @staticmethod
    def _help(command: str) -> str:
        if command == "help":
            return HELP_SUMMARY
        topic = command.partition(" ")[2].split()[0]
        topic = HELP_ALIASES.get(topic, topic)
        return HELP_TOPICS.get(
            topic,
            f"No help is available for {topic.upper()}. Send HELP for the command list.",
        )

    def _claim_active_slot(
        self, connection: sqlite3.Connection, sender_id: str, now: int
    ) -> bool:
        cutoff = now - self.active_player_timeout_seconds
        row = connection.execute(
            "SELECT updated_at FROM sessions WHERE sender_id=?", (sender_id,)
        ).fetchone()
        if row is not None and int(row["updated_at"]) >= cutoff:
            return True
        active_count = connection.execute(
            "SELECT COUNT(*) FROM sessions WHERE updated_at>=?", (cutoff,)
        ).fetchone()[0]
        return int(active_count) < self.max_active_players

    def _busy_message(self) -> str:
        minutes = max(1, self.active_player_timeout_seconds // 60)
        return (
            f"MeshTrail is busy ({self.max_active_players}/{self.max_active_players} wagon parties). "
            f"Try again after an idle slot expires in {minutes} minute"
            f"{'s' if minutes != 1 else ''}; saved journeys are safe."
        )

    @staticmethod
    def _create_session(connection: sqlite3.Connection, sender_id: str, now: int) -> None:
        connection.execute(
            "INSERT INTO sessions(sender_id,day,distance,food,ammo,parts,health,pace,rations,"
            "turns,battery,aerial,money,medicine,medicine_care,shop_location,pending_event,"
            "outcome,updated_at) VALUES (?,1,0,?,?,?,?,?,?,0,100,100,400,?,0,0,'','traveling',?)",
            (
                sender_id,
                START_FOOD,
                START_AMMO,
                START_PARTS,
                100,
                "steady",
                "filling",
                START_MEDICINE,
                now,
            ),
        )

    @staticmethod
    def _status(state: dict[str, object]) -> str:
        if state.get("pending_event"):
            pending = str(state["pending_event"])
            if pending.startswith("river:"):
                mile = int(pending.partition(":")[2])
                name, depth = RIVERS[mile]
                return (
                    f"Day {state['day']} at {name}, depth {depth}ft. Choose FORD, CAULK, "
                    f"or FERRY. Cash ${state['money']}."
                )
            if pending.startswith("illness:"):
                return (
                    f"Day {state['day']}: illness threatens. Medicine {state['medicine']}. "
                    "Use MEDICINE or ENDURE."
                )
            if pending.startswith("trade:"):
                _, trader_index, item, amount, price = pending.split(":")
                trader = PRAIRIE_TRADERS[int(trader_index)]
                return (
                    f"Day {state['day']}: {trader} offers {amount} {item} for ${price}. "
                    "TRADE or PASS."
                )
            if pending == "hazard:bison":
                return f"Day {state['day']}: a bison herd blocks the trail. Choose WAIT or DETOUR."
            if pending == "hazard:storm":
                return f"Day {state['day']}: prairie storm approaching. Choose CAMP or PUSH."
            if pending == "hazard:breakdown":
                return (
                    f"Day {state['day']}: broken wagon; {state['parts']} spare parts. "
                    "Choose SPARE, REPAIR, or ABANDON."
                )
        next_name, remaining = TrailStore._next_landmark(int(state["distance"]))
        return (
            f"Day {state['day']} | {state['distance']}/{TRAIL_END}mi | food {state['food']}lb | "
            f"health {state['health']} | next: {next_name} {remaining}mi. GO/HUNT/REST."
        )

    @staticmethod
    def _next_landmark(distance: int) -> tuple[str, int]:
        for miles, name in LANDMARKS:
            if miles > distance:
                return name, miles - distance
        return "Willamette Valley", 0

    @staticmethod
    def _radio_status(state: dict[str, object]) -> str:
        next_name, remaining = TrailStore._next_landmark(int(state["distance"]))
        if int(state["battery"]) <= 0:
            return "LoRa Aether Telegraph: cells exhausted. Reach a fort relay to recharge."
        return (
            f"LoRa Aether Telegraph: cells {state['battery']}%, aerial {state['aerial']}%. "
            f"Next mesh relay: {next_name}, {remaining}mi. BEACON sends a trail ping."
        )

    @staticmethod
    def _shop(state: dict[str, object]) -> str:
        location = int(state["shop_location"])
        if location not in TRADING_POSTS:
            return (
                "No trading post here. Supplies are sold at Independence and forts along "
                "the trail."
            )
        return (
            f"{TRADING_POSTS[location]} post: food {FOOD_LOT_SIZE}lb/${FOOD_LOT_PRICE}; "
            f"ammo {AMMO_LOT_SIZE}/${AMMO_LOT_PRICE}; medicine 1/${MEDICINE_PRICE}. "
            f"Cash ${state['money']}. BUY FOOD 100, BUY AMMO 20, or BUY MEDICINE 1."
        )

    @staticmethod
    def _buy(
        connection: sqlite3.Connection,
        sender_id: str,
        state: dict[str, object],
        command: str,
        now: int,
    ) -> str:
        location = int(state["shop_location"])
        if location not in TRADING_POSTS:
            return "No trading post here. Buy supplies at Independence or a fort."
        words = command.split()
        if len(words) != 3 or words[1] not in {"food", "ammo", "medicine"}:
            return "Buy with BUY FOOD n, BUY AMMO n, or BUY MEDICINE n."
        try:
            amount = int(words[2])
        except ValueError:
            return "Purchase amount must be a whole number."
        item = words[1]
        if item == "medicine":
            minimum, maximum, lot_size, lot_price = 1, 20, 1, MEDICINE_PRICE
        elif item == "food":
            minimum, maximum, lot_size, lot_price = 10, 5000, FOOD_LOT_SIZE, FOOD_LOT_PRICE
        else:
            minimum, maximum, lot_size, lot_price = 10, 500, AMMO_LOT_SIZE, AMMO_LOT_PRICE
        if amount < minimum or amount > maximum or amount % lot_size:
            if item == "medicine":
                return "Buy 1-20 medicine bottles at a time."
            return f"Buy 10-{maximum} {item} in multiples of 10."
        cost = amount // lot_size * lot_price
        money = int(state["money"])
        if cost > money:
            return f"That costs ${cost}; you have ${money}. Send SHOP for prices."
        new_total = int(state[item]) + amount
        connection.execute(
            f"UPDATE sessions SET {item}=?,money=?,updated_at=? WHERE sender_id=?",
            (new_total, money - cost, now, sender_id),
        )
        unit = "lb food" if item == "food" else item
        return f"Bought {amount} {unit} for ${cost}. {item.title()} {new_total}; cash ${money-cost}."

    @staticmethod
    def _use_medicine(
        connection: sqlite3.Connection,
        sender_id: str,
        state: dict[str, object],
        now: int,
    ) -> str:
        medicine = int(state["medicine"])
        health = int(state["health"])
        if medicine < 1:
            return "No medicine remains. Buy it at a trading post, trade, or FORAGE."
        if health >= 100:
            return "The party is already at full health; medicine was not used."
        health = min(100, health + 3)
        connection.execute(
            "UPDATE sessions SET medicine=?,medicine_care=1,health=?,updated_at=? "
            "WHERE sender_id=?",
            (medicine - 1, health, now, sender_id),
        )
        return (
            f"Used 1 medicine. Health {health}; {medicine-1} remain. "
            "The next REST recovers 20% faster."
        )

    def _forage(
        self,
        connection: sqlite3.Connection,
        sender_id: str,
        state: dict[str, object],
        now: int,
    ) -> str:
        rng = self._rng(sender_id, int(state["turns"]), "forage")
        food = max(0, int(state["food"]) - PARTY_SIZE * RATION_FOOD[str(state["rations"])])
        found = rng.choices((0, 1, 2), weights=(4, 5, 1), k=1)[0]
        medicine = int(state["medicine"]) + found
        day = int(state["day"]) + 1
        connection.execute(
            "UPDATE sessions SET day=?,food=?,medicine=?,turns=turns+1,updated_at=? "
            "WHERE sender_id=?",
            (day, food, medicine, now, sender_id),
        )
        if found:
            return (
                f"Foraged 1 day and prepared {found} herbal medicine. "
                f"Medicine {medicine}; food {food}lb."
            )
        return f"Foraged 1 day but found no useful herbs. Medicine {medicine}; food {food}lb."

    @staticmethod
    def _finished(state: dict[str, object]) -> str:
        if state["outcome"] == "won":
            return f"Oregon! You reached the Willamette Valley on day {state['day']}. Send RESET to ride again."
        return f"Your journey ended on day {state['day']} at mile {state['distance']}. Send RESET to try again."

    @staticmethod
    def _set_choice(
        connection: sqlite3.Connection,
        sender_id: str,
        state: dict[str, object],
        command: str,
        field: str,
        choices: dict[str, int],
        now: int,
    ) -> str:
        choice = command.partition(" ")[2]
        if choice not in choices:
            return f"Choose {field}: {', '.join(choices)}."
        connection.execute(
            f"UPDATE sessions SET {field}=?, updated_at=? WHERE sender_id=?",
            (choice, now, sender_id),
        )
        return f"{field.title()} set to {choice}. " + TrailStore._status({**state, field: choice})

    def _rng(self, sender_id: str, turns: int, action: str) -> random.Random:
        material = f"{self.random_seed}:{sender_id}:{turns}:{action}".encode()
        return random.Random(int.from_bytes(hashlib.sha256(material).digest()[:8], "big"))

    @staticmethod
    def _event_chance(distance: int) -> float:
        """Raise the chance of trail trouble from 42% to 62% as Oregon nears."""
        return 0.42 + 0.20 * min(TRAIL_END, max(0, distance)) / TRAIL_END

    def _travel(
        self, connection: sqlite3.Connection, sender_id: str, state: dict[str, object], now: int
    ) -> str:
        rng = self._rng(sender_id, int(state["turns"]), "go")
        days = 7
        miles = PACE_MILES[str(state["pace"])] + rng.randint(-12, 12)
        river = next(
            (
                (mark, *RIVERS[mark])
                for mark in sorted(RIVERS)
                if int(state["distance"]) < mark <= int(state["distance"]) + miles
            ),
            None,
        )
        if river is not None:
            mile, name, depth = river
            approach_days = 2
            food = max(
                0,
                int(state["food"])
                - PARTY_SIZE * RATION_FOOD[str(state["rations"])] * approach_days,
            )
            battery = max(0, int(state["battery"]) - 2)
            connection.execute(
                "UPDATE sessions SET day=day+?,distance=?,food=?,battery=?,pending_event=?,"
                "shop_location=-1,turns=turns+1,updated_at=? WHERE sender_id=?",
                (approach_days, mile, food, battery, f"river:{mile}", now, sender_id),
            )
            return f"{name}, depth {depth}ft. The trail ends at the bank. Choose FORD, CAULK, or FERRY ($25)."
        food_used = PARTY_SIZE * RATION_FOOD[str(state["rations"])] * days
        food = max(0, int(state["food"]) - food_used)
        health = int(state["health"])
        parts = int(state["parts"])
        battery = max(0, int(state["battery"]) - rng.randint(3, 7))
        aerial = int(state["aerial"])
        event = "Clear trail."
        pending_event = ""
        preserve_event = False

        if food == 0:
            health -= 18
            event = "Food ran out; the party is starving."
        elif rng.random() < self._event_chance(int(state["distance"])):
            roll = rng.randrange(7)
            jackalope_roll = self._rng(
                sender_id, int(state["turns"]), "jackalope-sighting"
            ).randrange(16)
            if jackalope_roll == 13:
                health = min(100, health + 3)
                preserve_event = True
                event = (
                    "An elusive jackalope watches from a ridge, then bounds west. "
                    "Spirits rise; health +3."
                )
            elif roll == 0:
                pending_event = "illness:dysentery:12"
                event = "Dysentery threatens. MEDICINE prevents it; ENDURE loses 12 health."
            elif roll == 1:
                pending_event = "hazard:breakdown"
                event = "A wagon wheel splinters. Choose SPARE, REPAIR, or ABANDON."
            elif roll == 2:
                pending_event = "hazard:storm"
                event = "A prairie storm bears down. Choose CAMP or PUSH."
            elif roll == 3:
                miles += 20
                event = "Good weather and a firm trail!"
            elif roll == 4:
                offers = (
                    ("food", 100, 15),
                    ("ammo", 20, 8),
                    ("medicine", 1, 10),
                )
                item, amount, price = rng.choice(offers)
                trader_index = rng.randrange(len(PRAIRIE_TRADERS))
                trader = PRAIRIE_TRADERS[trader_index]
                pending_event = f"trade:{trader_index}:{item}:{amount}:{price}"
                event = f"{trader} offers {amount} {item} for ${price}. TRADE or PASS."
            elif roll == 5:
                damage = rng.randint(8, 20)
                aerial = max(0, aerial - damage)
                event = f"Lightning damaged the mesh aerial by {damage}%."
            else:
                bison_roll = self._rng(
                    sender_id, int(state["turns"]), "bison-herd"
                ).random()
                if bison_roll < 0.5:
                    pending_event = "hazard:bison"
                    event = "A great bison herd blocks the trail. Choose WAIT or DETOUR."
                elif battery > 0 and aerial >= 30:
                    miles += 15
                    battery = max(0, battery - 3)
                    event = "A relay packet warned of a washout; your party found a shortcut."
                else:
                    event = "Static from a distant relay fades into the prairie."

        if state["pace"] == "strenuous":
            health -= 3
        elif state["pace"] == "grueling":
            health -= 7
        if state["rations"] == "bare":
            health -= 4
        elif state["rations"] == "filling":
            health = min(100, health + 2)

        distance = min(TRAIL_END, int(state["distance"]) + max(0, miles))
        if not pending_event and not preserve_event and int(state["distance"]) < 210 <= distance:
            event = (
                "The trail joins Nebraska's broad Platte River, the Great Platte River Road "
                "stretching west."
            )
        crossed_relays = [
            mark for mark in RELAY_MILES if int(state["distance"]) < mark <= distance
        ]
        crossed_posts = [
            mark for mark in TRADING_POSTS if int(state["distance"]) < mark <= distance
        ]
        if crossed_relays:
            battery = 100
            aerial = min(100, aerial + 25)
            if pending_event or preserve_event:
                pass
            elif 300 in crossed_relays:
                event = (
                    "Fort Kearny: Nebraska Mesh operators DOS_ and Nightcrawler service your set. "
                    "'One relay at a time.'"
                )
            elif 1050 in crossed_relays:
                event = (
                    "A white jackrabbit waits beneath the South Pass relay, then hops west as "
                    "your packet clears."
                )
            else:
                event += " Fort relay: cells charged and aerial serviced."
        shop_location = max(crossed_posts) if crossed_posts else -1
        if preserve_event:
            pass
        elif shop_location == 300:
            pending_event = ""
            event = (
                "Fort Kearny: SHOP open. Nebraska Mesh operators DOS_ and Nightcrawler "
                "service your set."
            )
        elif shop_location >= 0:
            pending_event = ""
            event = f"{TRADING_POSTS[shop_location]}: trading post open. Send SHOP."
        elif pending_event:
            pass
        day = int(state["day"]) + days
        outcome = "won" if distance >= TRAIL_END else ("dead" if health <= 0 else "traveling")
        health = max(0, min(100, health))
        connection.execute(
            "UPDATE sessions SET day=?,distance=?,food=?,parts=?,health=?,battery=?,aerial=?,"
            "shop_location=?,pending_event=?,turns=turns+1,"
            "outcome=?,updated_at=? WHERE sender_id=?",
            (
                day,
                distance,
                food,
                parts,
                health,
                battery,
                aerial,
                shop_location,
                pending_event,
                outcome,
                now,
                sender_id,
            ),
        )
        if outcome == "won":
            return (
                f"Oregon! Willamette Valley reached on day {day}. A white jackrabbit watches "
                f"from the final relay. Health {health}. RESET to replay."
            )
        if outcome == "dead":
            return f"{event} Your party has perished at mile {distance}. RESET to try again."
        if pending_event:
            return f"{event} Day {day}; {distance}/{TRAIL_END}mi."
        return f"{event} Day {day}: {distance}/{TRAIL_END}mi, food {food}lb, health {health}. GO/HUNT/REST."

    def _resolve_hazard(
        self,
        connection: sqlite3.Connection,
        sender_id: str,
        state: dict[str, object],
        hazard: str,
        choice: str,
        now: int,
    ) -> str:
        rng = self._rng(sender_id, int(state["turns"]), f"hazard:{hazard}:{choice}")
        days = 0
        food = int(state["food"])
        ammo = int(state["ammo"])
        parts = int(state["parts"])
        health = int(state["health"])
        aerial = int(state["aerial"])

        if hazard == "bison":
            if choice == "wait":
                days = 2
                result = "The party waits safely for the bison herd to pass."
            else:
                days = 1
                if rng.random() < 0.68:
                    result = "The wagon finds a rough but safe detour around the bison herd."
                elif parts:
                    parts -= 1
                    result = "The detour breaks a wagon fitting; 1 spare part is used."
                else:
                    health -= 8
                    result = "With no spare part, the rough detour costs 8 health."
        elif hazard == "storm":
            if choice == "camp":
                days = 2
                wear = rng.randint(0, 4)
                aerial = max(0, aerial - wear)
                result = "The party camps safely until the prairie storm passes."
                if wear:
                    result += f" Aerial wear {wear}%."
            else:
                days = 1
                if rng.random() < 0.55:
                    damage = rng.randint(8, 14)
                    aerial_damage = rng.randint(10, 25)
                    health -= damage
                    aerial = max(0, aerial - aerial_damage)
                    result = (
                        f"The storm batters the wagon: health -{damage}; "
                        f"aerial -{aerial_damage}%."
                    )
                else:
                    result = "The wagon pushes through the storm without serious damage."
        elif hazard == "breakdown":
            if choice == "spare":
                if parts < 1:
                    return "No spare parts remain. Choose REPAIR or ABANDON."
                days = 1
                parts -= 1
                result = "A spare part repairs the wagon safely."
            elif choice == "repair":
                days = 2
                if rng.random() < 0.65:
                    result = "The party repairs the wagon without using a spare part."
                else:
                    days = 3
                    health -= 6
                    result = "The improvised repair slips; another day passes and health falls by 6."
            else:
                lost_food = min(food, rng.randint(120, 220))
                lost_ammo = min(ammo, rng.randint(10, 25))
                food -= lost_food
                ammo -= lost_ammo
                result = (
                    f"Supplies are abandoned to salvage the wagon: {lost_food}lb food and "
                    f"{lost_ammo} ammo lost."
                )
        else:
            return "The trail hazard cannot be resolved. Send STATUS."

        food_needed = PARTY_SIZE * RATION_FOOD[str(state["rations"])] * days
        if food < food_needed:
            food = 0
            health -= 8
            result += " Food runs out; health falls by 8."
        else:
            food -= food_needed
        health = max(0, min(100, health))
        outcome = "dead" if health <= 0 else "traveling"
        day = int(state["day"]) + days
        connection.execute(
            "UPDATE sessions SET day=?,food=?,ammo=?,parts=?,health=?,aerial=?,"
            "pending_event='',turns=turns+1,outcome=?,updated_at=? WHERE sender_id=?",
            (day, food, ammo, parts, health, aerial, outcome, now, sender_id),
        )
        if outcome == "dead":
            return result + " Your party has perished. RESET to try again."
        return result + f" Day {day}; food {food}lb; health {health}. Send GO."

    def _resolve_river(
        self,
        connection: sqlite3.Connection,
        sender_id: str,
        state: dict[str, object],
        choice: str,
        now: int,
    ) -> str:
        mile = int(str(state["pending_event"]).partition(":")[2])
        name, depth = RIVERS[mile]
        money = int(state["money"])
        health = int(state["health"])
        food = int(state["food"])
        rng = self._rng(sender_id, int(state["turns"]), f"river:{mile}:{choice}")

        if choice == "ferry":
            if money < 25:
                return "You cannot afford the $25 ferry. Choose FORD or CAULK."
            money -= 25
            days = 1
            result = f"The ferry carries everyone safely across {name}."
        else:
            days = 2 if choice == "caulk" else 1
            chance = 0.82 if choice == "caulk" else max(0.2, 0.82 - depth * 0.1)
            if rng.random() <= chance:
                verb = "floats" if choice == "caulk" else "fords"
                result = f"The wagon {verb} {name} safely."
            else:
                lost = min(food, rng.randint(35, 90))
                food -= lost
                health = max(0, health - rng.randint(6, 16))
                result = f"The wagon floods in {name}: {lost}lb food lost; health {health}."

        if mile == 475:
            result += " California Hill rises ahead toward the North Platte."

        outcome = "dead" if health <= 0 else "traveling"
        connection.execute(
            "UPDATE sessions SET day=day+?,food=?,health=?,money=?,pending_event='',"
            "turns=turns+1,outcome=?,updated_at=? WHERE sender_id=?",
            (days, food, health, money, outcome, now, sender_id),
        )
        if outcome == "dead":
            return result + " Your party has perished. RESET to try again."
        return result + f" Day {int(state['day']) + days}. Send GO to continue west."

    @staticmethod
    def _resolve_illness(
        connection: sqlite3.Connection,
        sender_id: str,
        state: dict[str, object],
        choice: str,
        now: int,
    ) -> str:
        _, illness, damage_text = str(state["pending_event"]).split(":")
        damage = int(damage_text)
        medicine = int(state["medicine"])
        health = int(state["health"])
        if choice == "medicine":
            if medicine < 1:
                return f"No medicine remains. ENDURE the {illness} or find supplies first."
            medicine -= 1
            result = f"Medicine prevents {illness}; 1 bottle used. Health {health}."
        else:
            health = max(0, health - damage)
            result = f"The party endures {illness}; health falls by {damage} to {health}."
        outcome = "dead" if health <= 0 else "traveling"
        connection.execute(
            "UPDATE sessions SET medicine=?,health=?,pending_event='',outcome=?,updated_at=? "
            "WHERE sender_id=?",
            (medicine, health, outcome, now, sender_id),
        )
        if outcome == "dead":
            return result + " Your party has perished. RESET to try again."
        return result + " Send GO to continue west."

    @staticmethod
    def _resolve_trade(
        connection: sqlite3.Connection,
        sender_id: str,
        state: dict[str, object],
        choice: str,
        now: int,
    ) -> str:
        _, trader_index, item, amount_text, price_text = str(state["pending_event"]).split(":")
        trader = PRAIRIE_TRADERS[int(trader_index)]
        amount = int(amount_text)
        price = int(price_text)
        if item not in {"food", "ammo", "medicine"}:
            connection.execute(
                "UPDATE sessions SET pending_event='',updated_at=? WHERE sender_id=?",
                (now, sender_id),
            )
            return "The trader's offer was unreadable and has been cleared. Send GO."
        if choice == "pass":
            connection.execute(
                "UPDATE sessions SET pending_event='',updated_at=? WHERE sender_id=?",
                (now, sender_id),
            )
            return f"You pass {trader}'s offer. Send GO to continue west."
        money = int(state["money"])
        if money < price:
            return f"{trader} asks ${price}; you have ${money}. Send PASS."
        new_total = int(state[item]) + amount
        connection.execute(
            f"UPDATE sessions SET {item}=?,money=?,pending_event='',updated_at=? "
            "WHERE sender_id=?",
            (new_total, money - price, now, sender_id),
        )
        unit = "lb food" if item == "food" else item
        return (
            f"Traded ${price} to {trader} for {amount} {unit}. "
            f"Cash ${money-price}. Send GO."
        )

    def _beacon(
        self, connection: sqlite3.Connection, sender_id: str, state: dict[str, object], now: int
    ) -> str:
        battery = int(state["battery"])
        aerial = int(state["aerial"])
        if battery < 5:
            return "The telegraph cells are too weak to send. Reach a fort relay."
        if aerial < 20:
            return "The aerial is too damaged to raise a relay. A fort can repair it."
        rng = self._rng(sender_id, int(state["turns"]), "beacon")
        next_name, remaining = self._next_landmark(int(state["distance"]))
        quality = max(1, min(5, (aerial + rng.randint(-20, 20)) // 20))
        operator = rng.choice(PRAIRIE_MESH_OPERATORS)
        connection.execute(
            "UPDATE sessions SET battery=?,turns=turns+1,updated_at=? WHERE sender_id=?",
            (battery - 5, now, sender_id),
        )
        return (
            f"BEACON ACK {quality}/5 via {operator}. {next_name} is {remaining}mi west. "
            f"Cells {battery-5}%."
        )

    def _hunt(
        self, connection: sqlite3.Connection, sender_id: str, state: dict[str, object], now: int
    ) -> str:
        ammo = int(state["ammo"])
        if ammo < 5:
            return "Not enough ammunition to hunt."
        rng = self._rng(sender_id, int(state["turns"]), "hunt")
        used = rng.randint(5, min(12, ammo))
        gained = rng.randint(25, 130)
        day = int(state["day"]) + 2
        food = int(state["food"]) + gained
        connection.execute(
            "UPDATE sessions SET day=?,food=?,ammo=?,turns=turns+1,updated_at=? WHERE sender_id=?",
            (day, food, ammo - used, now, sender_id),
        )
        return f"Hunt: gained {gained}lb food, used {used} ammo and 2 days. Food {food}lb; ammo {ammo-used}."

    @staticmethod
    def _rest(
        connection: sqlite3.Connection,
        sender_id: str,
        state: dict[str, object],
        now: int,
    ) -> str:
        day = int(state["day"]) + 3
        food = max(0, int(state["food"]) - PARTY_SIZE * 2 * 3)
        medicine_aided = bool(state["medicine_care"])
        recovery = 17 if medicine_aided else 14
        health = min(100, int(state["health"]) + recovery)
        connection.execute(
            "UPDATE sessions SET day=?,food=?,health=?,medicine_care=0,turns=turns+1,"
            "updated_at=? WHERE sender_id=?",
            (day, food, health, now, sender_id),
        )
        aid = " Medicine aided recovery." if medicine_aided else ""
        return f"Rested 3 days. Day {day}; food {food}lb; health {health}.{aid}"


def fit_utf8(text: str, max_bytes: int) -> str:
    """Return valid UTF-8 no larger than max_bytes."""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    suffix = "..."
    clipped = encoded[: max(0, max_bytes - len(suffix))]
    while clipped:
        try:
            return clipped.decode("utf-8").rstrip() + suffix
        except UnicodeDecodeError:
            clipped = clipped[:-1]
    return suffix[:max_bytes]
