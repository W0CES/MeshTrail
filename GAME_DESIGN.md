# MeshTrail design direction

## The premise

MeshTrail takes place in 1854, the first year of Nebraska Territory, but in a lightly alternate
history. A few westbound wagon
parties have been issued experimental **Long-Range (LoRa) Aether Telegraphs**: brass-and-wood
wireless sets powered by galvanic cells. Forts maintain crude relay masts, forming a sparse
"prairie mesh" across the trail.

The anachronism is intentional and contained. Everything around the device remains grounded in
the period: travel speed, diseases, rivers, forts, weather, food, ammunition, wagon repairs,
and the danger of the crossing. Characters describe the mesh in period-flavored language rather
than speaking like modern network engineers.

## Design pillars

1. **1850 first.** The journey should feel historical even when the mesh telegraph appears.
2. **Radio-native play.** Commands are tiny, responses fit one LoRa message, and delayed or
   duplicated delivery cannot corrupt a game.
3. **The mesh matters.** Cells, aerial condition, relay stations, beacons, and received trail
   warnings affect decisions instead of appearing only as jokes.
4. **Shared frontier.** Later releases can let parties exchange short telegrams, cache supplies,
   report hazards, and leave grave-marker messages for future travelers.

## Vocabulary

| MeshCore concept | In-world name |
| --- | --- |
| Node / sender ID | Telegraph set or wagon mark |
| Repeater | Fort relay mast |
| Direct message | Private telegram |
| Packet | Telegraph slip or burst |
| Hop count | Number of relay masts |
| Signal quality | Aether strength |
| Battery | Galvanic cells |
| Antenna | Aerial wire |

## Initial radio mechanics

- Every new party starts with full galvanic cells and an intact aerial.
- Travel drains cells; storms may damage the aerial.
- `RADIO` reports equipment condition and the next relay.
- `BEACON` spends cell power to request a short route report.
- Crossing a fort relay recharges cells and repairs some aerial damage.
- A working set can receive warnings that avoid hazards or reveal shortcuts.

## Trail decisions

Travel stops at major rivers instead of resolving them as passive random text. The player chooses
to `FORD`, `CAULK`, or pay for a `FERRY`; the decision remains saved until answered. This same
pending-decision system will later support trail forks, severe weather, illness treatment, and
requests for aid over the prairie mesh.

The Platte is handled as a Nebraska journey in its own right. Parties first join the broad
**Great Platte River Road** near Fort Kearny and follow its south bank west. Farther on they must
choose how to cross the **South Platte**, then climb California Hill toward the North Platte
route. This avoids presenting the Platte as one generic river crossing.

Future mechanics should include asynchronous telegrams between active parties, fort bulletin
boards, player-submitted hazard reports with expiration, and a leaderboard presented as a relay
operator's westbound registry.

## The openHop rabbit

The openHop rabbit mascot becomes a piece of prairie-mesh folklore. Every issued Aether Telegraph
bears a small rabbit seal stamped into its brass case. A mysterious white jackrabbit may also be
seen beneath relay masts at important moments—most notably at South Pass and at the final relay in
the Willamette Valley. Operators consider it a sign that a message has found a clear path.

The rabbit should remain unexplained. It is not a talking character or a modern logo dropped into
the setting; it is a recurring visual motif and a quiet reward for players who know openHop.

## Nebraska Mesh Easter egg

The first Great Plains relay is maintained by the fictional **Nebraska Mesh Telegraph
Cooperative**, a volunteer group based around Fort Kearny. When a party arrives, its operators
recharge the galvanic cells and repeat their motto: "Keep the territory connected, one relay at
a time."

The Fort Kearny station is staffed by two recurring operators:

- **DOS_**, the meticulous station keeper who repairs sets, records passing wagon marks, and
  insists that every telegraph slip be logged correctly.
- **Nightcrawler**, the night-shift signal watcher who catches faint long-distance bursts and
  passes late warnings to travelers before they leave camp.

Their names are presented without explanation. Nebraska Mesh members will recognize the tribute;
other players will simply meet two distinctive frontier telegraph operators. Later Nebraska
events can let each character deliver different warnings, rumors, repair help, or optional tasks.

Other public Nebraska Mesh node names appear more lightly as distant signatures returned by
`BEACON`. The initial rotation is **Applesauce**, **Heartwood Observer**, **CourtHouse**,
**NADPEATER**, **Florence OMA**, and **Tammy**. They are treated as telegraph handles rather than
fully defined characters, leaving room for their real operators to suggest better cameos later.

This is a quiet homage to the real volunteer-run Nebraska Mesh community and its mission to keep
Nebraska connected one node at a time. It should appear as local color, not an advertisement or
modern organization transported wholesale into the story. Fort Kearny, the Platte River,
Chimney Rock, Scotts Bluff, and other Nebraska trail locations should receive especially rich
events as the game grows.
