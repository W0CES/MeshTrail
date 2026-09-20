# MeshTrail: Beginner's Guide

Welcome to **MeshTrail**, a short, command-driven wagon journey west in 1854. You lead five
travelers from Independence to the Willamette Valley while managing food, health, ammunition,
wagon parts, cash, and a long-range Aether Telegraph.

You play by sending one command at a time in a private MeshCore message. Commands are not case
sensitive, so `go`, `GO`, and `Go` work the same way.

## Your first journey

1. Send `START` to form a new wagon party.
2. Send `STATUS` to see your day, distance, food, health, and next landmark.
3. Send `SUPPLIES` to see food, ammunition, medicine, spare parts, cash, cells, and aerial
   condition.
4. Send `SHOP` to see the Independence outfitter's food, ammunition, and medicine prices.
5. Purchase supplies with commands such as `BUY FOOD 100`, `BUY AMMO 20`, or
   `BUY MEDICINE 1`.
6. Send `GO` to travel west for seven days.
7. Continue checking your supplies and responding to events until you reach Oregon.

Every new party begins with:

- 1,000 lb of food
- 50 units of ammunition
- 3 spare wagon parts
- Health 100
- $400 cash
- Telegraph cells and aerial condition at 100%
- `steady` pace and `filling` rations

Your progress is saved between messages. If a river interrupts travel, the game waits for your
choice; it will not silently move past the crossing.

By default, an inactive journey remains saved for 30 days. The openHop administrator can change
that retention period from the MeshTrail settings page.

## Commands

| Command | What it does |
| --- | --- |
| `START` | Creates your wagon party. Use this at the beginning. |
| `GO` | Travels for seven days. This is the main way to move west. |
| `STATUS` | Shows day, distance, food, health, and the next landmark. |
| `SUPPLIES` | Shows food, ammunition, medicine, spare parts, cash, cells, and aerial condition. |
| `SHOP` | Shows food and ammunition prices at Independence or a fort. |
| `BUY FOOD 100` | Buys 100 lb of food. Food is sold in multiples of 10 lb. |
| `BUY AMMO 20` | Buys 20 ammunition. Ammunition is sold in multiples of 10. |
| `BUY MEDICINE 1` | Buys medicine by the bottle at a trading post. |
| `MEDICINE` | Uses one bottle, restores 3 health, and improves the next rest. |
| `FORAGE` | Spends one day searching for herbal medicine. |
| `TRADE` | Accepts a traveler's offer when you have enough cash. |
| `PASS` | Declines a traveler's offer without spending cash. |
| `PING` | Checks the telegraph and identifies the next mesh relay or landmark. |
| `BEACON` | Uses 5% of your cells to request a trail report. |
| `HUNT` | Uses ammunition and two days to gain food. |
| `REST` | Uses three days and food to recover health. |
| `PACE steady` | Balanced travel: about 95 miles per trip. |
| `PACE strenuous` | Faster travel: about 120 miles per trip, with a small health cost. |
| `PACE grueling` | Fastest travel: about 145 miles per trip, with a larger health cost. |
| `RATIONS filling` | Uses 15 lb of food per day for the five-person party and can restore a little health. |
| `RATIONS meager` | Uses 10 lb of food per day. |
| `RATIONS bare` | Uses 5 lb of food per day, but reduces health. |
| `FORD` | Attempts a river crossing directly. It is quickest but riskier, especially in deep water. |
| `CAULK` | Prepares the wagon and crosses more cautiously. It takes two days. |
| `FERRY` | Pays $25 for a safe, one-day crossing. |
| `HELP` | Shows the in-game command list. |
| `HELP <command>` | Explains one command, including its choices and an example when useful. Try `HELP PACE`, `HELP BUY`, or `HELP RIVER`. |
| `HELP ENCOUNTER` | Explains the choices for bison, prairie storms, and wagon breakdowns. |
| `HELP JACKALOPE` | Describes a rare and mysterious trail sighting. |
| `RESET` | Abandons the current journey and starts a fresh one. |
| `GUIDE` | Returns a link to this beginner guide. This works before starting a journey. |

`SUPPLIES` is also available as `INV`, and `STATUS` as `S`. `GO` also accepts `TRAVEL` or
`CONTINUE`. `?` is a shortcut for `HELP`.

## Buying supplies

Trading posts are available before leaving Independence and when you reach Fort Kearny, Fort
Laramie, Fort Bridger, Fort Hall, or Fort Boise. Send `SHOP` while stopped there to see prices and
your available cash. Food costs $2 per 10 lb, ammunition costs $2 per 10 units, and medicine
costs $15 per bottle.

Purchases do not consume a travel day. Once you send `GO` and leave a trading post, you must wait
until the next fort to buy more supplies. If you cannot afford a purchase, MeshTrail reports its
cost and leaves your inventory unchanged.

Travelers may also offer food, ammunition, or medicine at lower trail prices. Send `TRADE` to
accept an offer or `PASS` to decline it. The journey waits for your answer, so the offer cannot be
lost in a delayed radio exchange.

## Medicine and herbal remedies

Send `FORAGE` to spend one day searching for useful plants. Foraging consumes that day's rations
and may produce one or two bottles of herbal medicine, but sometimes finds nothing useful.

Send `MEDICINE` while injured to consume one bottle and restore 3 health. The treatment also
increases the healing from your next `REST` by about 20%. During certain illness events, the game
asks you to choose `MEDICINE` to prevent the illness or `ENDURE` and accept the health loss. Each
preventive treatment consumes one bottle.

## How to make decisions

### Keep moving, but watch food and health

`GO` consumes seven days of rations. Travel can cause illness, storms, broken wagons, animal
encounters, trader offers, or aerial damage. Trail trouble becomes more likely farther west.

If food reaches zero, the party begins to starve. If health reaches zero, the journey ends.
Use `HUNT` when food is getting low and you have at least 5 ammunition. Use `REST` after a bad
event or when health needs rebuilding, but remember that the party still eats while resting.

### Respond to trail encounters

Some events pause the journey until you choose what to do:

- A **bison herd** can be handled with `WAIT`, which safely costs two days and rations, or
  `DETOUR`, which costs one day but can damage a part or reduce health.
- A **prairie storm** can be handled with `CAMP`, which safely costs two days and rations, or
  `PUSH`, which costs one day but risks health and serious aerial damage.
- A **broken wagon** can be handled with `SPARE`, which uses one part and one day; `REPAIR`,
  which risks extra time and health; or `ABANDON`, which immediately sacrifices food and ammo.

Very rarely, the party may glimpse an elusive jackalope. No choice is required; the mysterious
sighting lifts everyone's spirits and restores a little health.

### Choose a pace and rations

Start with `PACE steady` and `RATIONS filling` while learning the game. When supplies are
tight, `RATIONS meager` or `RATIONS bare` stretches food, but bare rations harm health. When you
need to cover ground quickly, a strenuous or grueling pace saves time at the cost of health.

You can change either setting at any time by sending the command again. The new setting applies
to later travel.

### Treat rivers as planned hazards

The trail stops at the Kansas, Big Blue, South Platte, Green, Snake, and Columbia rivers. When
you receive a message telling you to choose `FORD`, `CAULK`, or `FERRY`, send exactly one of those
commands before sending `GO` again.

- `FORD` is fast and costs no cash, but the risk increases with river depth.
- `CAULK` is a safer wagon crossing and costs two days.
- `FERRY` costs $25, takes one day, and carries the party safely across. If you cannot afford it,
  choose `FORD` or `CAULK` instead.

After crossing, send `GO` to continue. Near mile 210, the trail joins Nebraska's Great Platte
River Road; the South Platte crossing is farther west near mile 475.

## Using the prairie mesh

Your telegraph begins fully charged and in good condition.

- Travel gradually uses cells.
- Storms can damage the aerial.
- `PING` reports current cell and aerial condition and points toward the next relay.
- `BEACON` costs 5% cells and returns a short trail report from another operator.
- Fort relays recharge cells and repair some aerial damage.

If cells are exhausted or the aerial is badly damaged, `BEACON` will not work until you reach a
fort relay. A working telegraph can also receive warnings that reveal a shortcut.

## A simple beginner strategy

1. Start with `steady` pace and `filling` rations.
2. Send `STATUS` and `SUPPLIES` regularly, especially after `GO`.
3. Hunt before food is nearly gone, rather than waiting for starvation.
4. Rest when health is low, not merely because a trip was uneventful.
5. Save cash for river ferries; use `CAULK` when you want to conserve money but avoid the risk of
   a direct ford.
6. Use `PING` to monitor the telegraph and `BEACON` when a route report would help.
7. At every river, answer the crossing prompt first. Then resume with `GO`.

## Winning or starting over

You win by reaching the Willamette Valley at mile 2,000. The game announces the successful
arrival and lets you replay with `RESET`.

If the party perishes, send `RESET` to abandon that run and form a new party. `RESET` also works
if you simply want to try a different strategy, but it permanently replaces the current saved
journey.
