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
PARTY_SIZE = 5
PLAYER_GUIDE_URL = "https://github.com/W0CES/MeshTrail/blob/main/PLAYER_GUIDE.md"
PACE_MILES = {"steady": 95, "strenuous": 120, "grueling": 145}
RATION_FOOD = {"filling": 3, "meager": 2, "bare": 1}
ALIASES = {"travel": "go", "continue": "go", "s": "status", "inv": "supplies", "?": "help"}
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
PRAIRIE_MESH_OPERATORS = (
    "Applesauce",
    "Heartwood Observer",
    "CourtHouse",
    "NADPEATER",
    "Florence OMA",
    "Tammy",
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
            if normalized == "help":
                return "GO, STATUS, SUPPLIES, PING, BEACON, HUNT, REST, PACE, RATIONS, GUIDE, RESET. Rivers: FORD, CAULK, FERRY."
            if normalized == "supplies":
                return f"Food {state['food']}lb; ammo {state['ammo']}; parts {state['parts']}; cash ${state['money']}; cells {state['battery']}%; aerial {state['aerial']}%."
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
                if normalized in {"ford", "caulk", "ferry"}:
                    return self._resolve_river(connection, sender_id, state, normalized, now)
                return "A river blocks the trail. Choose FORD, CAULK, or FERRY."
            if normalized == "rest":
                return self._rest(connection, sender_id, state, now)
            if normalized == "hunt":
                return self._hunt(connection, sender_id, state, now)
            if normalized == "go":
                return self._travel(connection, sender_id, state, now)
            return "Unknown command. Send HELP."

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
            "turns,battery,aerial,money,pending_event,outcome,updated_at) "
            "VALUES (?,1,0,?,?,?,?,?,?,0,100,100,400,'','traveling',?)",
            (sender_id, START_FOOD, START_AMMO, START_PARTS, 100, "steady", "filling", now),
        )

    @staticmethod
    def _status(state: dict[str, object]) -> str:
        if state.get("pending_event"):
            mile = int(str(state["pending_event"]).partition(":")[2])
            name, depth = RIVERS[mile]
            return f"Day {state['day']} at {name}, depth {depth}ft. Choose FORD, CAULK, or FERRY. Cash ${state['money']}."
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
                "turns=turns+1,updated_at=? WHERE sender_id=?",
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

        if food == 0:
            health -= 18
            event = "Food ran out; the party is starving."
        elif rng.random() < 0.42:
            roll = rng.randrange(7)
            if roll == 0:
                health -= 12
                event = "Dysentery strikes the party."
            elif roll == 1:
                if parts:
                    parts -= 1
                    event = "A wagon wheel broke; one spare used."
                else:
                    miles //= 2
                    health -= 8
                    event = "Broken wheel and no spare; progress slowed."
            elif roll == 2:
                lost = min(food, rng.randint(25, 70))
                food -= lost
                event = f"A storm spoiled {lost}lb of food."
            elif roll == 3:
                miles += 20
                event = "Good weather and a firm trail!"
            elif roll == 4:
                found = rng.randint(15, 35)
                food += found
                event = f"A friendly wagon shared {found}lb food."
            elif roll == 5:
                damage = rng.randint(8, 20)
                aerial = max(0, aerial - damage)
                event = f"Lightning damaged the mesh aerial by {damage}%."
            else:
                if battery > 0 and aerial >= 30:
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
        if int(state["distance"]) < 210 <= distance:
            event = (
                "The trail joins Nebraska's broad Platte River, the Great Platte River Road "
                "stretching west."
            )
        crossed_relays = [
            mark for mark in RELAY_MILES if int(state["distance"]) < mark <= distance
        ]
        if crossed_relays:
            battery = 100
            aerial = min(100, aerial + 25)
            if 300 in crossed_relays:
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
        day = int(state["day"]) + days
        outcome = "won" if distance >= TRAIL_END else ("dead" if health <= 0 else "traveling")
        health = max(0, min(100, health))
        connection.execute(
            "UPDATE sessions SET day=?,distance=?,food=?,parts=?,health=?,battery=?,aerial=?,turns=turns+1,"
            "outcome=?,updated_at=? WHERE sender_id=?",
            (day, distance, food, parts, health, battery, aerial, outcome, now, sender_id),
        )
        if outcome == "won":
            return (
                f"Oregon! Willamette Valley reached on day {day}. A white jackrabbit watches "
                f"from the final relay. Health {health}. RESET to replay."
            )
        if outcome == "dead":
            return f"{event} Your party has perished at mile {distance}. RESET to try again."
        return f"{event} Day {day}: {distance}/{TRAIL_END}mi, food {food}lb, health {health}. GO/HUNT/REST."

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
        health = min(100, int(state["health"]) + 14)
        connection.execute(
            "UPDATE sessions SET day=?,food=?,health=?,turns=turns+1,updated_at=? WHERE sender_id=?",
            (day, food, health, now, sender_id),
        )
        return f"Rested 3 days. Day {day}; food {food}lb; health {health}."


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

