# Attendance, Daily Quest and Daily Roll

## Idle footer / Refresh blinking fix (2026-10-17)

Automatic polling now retains the last confirmed footer text and button
appearance instead of flashing "Waiting for the server..." and disabled controls
for each short reply. Hover appearance is also retained. Explicit clicks still
show loading feedback; a background request taking at least one second becomes
visibly pending. The single-request guard, 10-second timeout recovery, ordinary
3-second refresh and pending-reroll 200-ms refresh are unchanged.

The 100-ms timer now redraws for Roll animation/reveals or a changed countdown
minute. Idle ticks and stationary-cursor callbacks no longer request repeated
full-window redraws. Replies and real input changes continue updating the UI.
The earlier footer-opacity correction remains in place.

Restart this WARP and repatch a clean client with **Attendance, Daily Quest and
Daily Roll**. This follow-up is client-only: no server rebuild or SQL update is
needed for the blinking fix. Staging is `Outputs/daily-idle-flicker-20261017`.
The native before-fix test reproduced both repeated idle redraws and changed
footer/Refresh pixels during automatic polls. The new check compares these
regions across pending and completed polls and covers loading/error recovery.
Daily Rewards reroll, footer opacity and six-result Roll checks cover the timer
and rendering dependencies. No unrelated feature suites or live data are used.

## Reroll latency, footer and account-bound rewards (2026-10-17)

Pending paid rerolls now refresh every **200 ms after the previous reply**,
instead of waiting for the ordinary 3-second refresh. The quest changes on the
first reply confirming the payment. This removes the fixed 3-second UI delay;
network and server/database processing time still applies. Only one request may
be in flight, and polling sends read-only Refresh commands, never another charge.
Normal refresh remains 3 seconds; response timeout/recovery remains 10 seconds.
The footer also restores opacity after native text rendering, preserving its
text and background while preventing the bottom-left game-background flicker.
Both UI fixes need a restarted WARP and a clean repatch of
**Attendance, Daily Quest and Daily Roll**. They retain wire version 5.

The matching server change makes **all Attendance, Daily Quest and Daily Roll
reward items account-bound**, including rentals and older uncollected Daily
Rewards mail. It does not convert items already collected into inventories.
This part requires rebuilding/restarting **char-server**; no additional SQL
migration is needed beyond the current Daily Rewards installation. See
`D:/AAARAGNAROK/Ragnarok/doc/daily-rewards.md` for binding and deployment details.

Focused native x86 timing/footer checks and fresh production mail-loader tests
against an owned SQL fixture are under `Outputs/daily-reroll-latency-20261017`.
Installed game EXEs and player data were not changed. Live game acceptance is
still required after repatching and deploying the rebuilt server.

## Current: Daily Quest re-rolls (2026-10-16, DRUI v5)

Five **Re-Roll** buttons sit below the quest status buttons. Uses are shared
across the account's five quests, default 3 per server-local day. The UI shows
the next shared price (10,000z / 25,000z / 50,000z) and uses remaining. Exhausted
buttons show **Limit reached**, without an additional "Resets at midnight"
label. The overall reset timer remains. Claimed quests and unaffordable or
pending purchases cannot be clicked. The server owns all decisions and charges.

Server configuration: `npc/custom/Ragnarok/Main/daily_rewards.txt`:

```text
.QuestRerollLimit = 3;
setarray .QuestRerollCost[0],10000,25000,50000;
```

This release requires `sql-files/upgrades/2026-10-16--daily-quest-rerolls.sql`
and rebuilding/restarting **map-server and char-server together**. Rebuild the
map-server-generator too if used. The SQL widens saved state to 416 bytes and
adds durable reroll receipts; old account progress is preserved. Do not apply
the older 412-byte state migration afterward. Full server details are in
`D:/AAARAGNAROK/Ragnarok/doc/daily-rewards.md`.

Restart this WARP copy and repatch a clean 2025-07-16 client with
**Attendance, Daily Quest and Daily Roll**. Payload version 5 uses a 9440-byte
snapshot, appending 20 bytes to v4. The 32-byte request and old snapshot prefixes
remain stable. Initial Open advertises DRU5 with protocol 4; an older v3 server
can negotiate through the timeout Refresh fallback. Re-roll buttons appear only
with a v5 reply. Existing six-item Roll and attendance rendering is preserved.

Staging: `Outputs/daily-quest-reroll-20261016`. The isolated EXE there contains
only DailyRewardsUI for offline testing, not the user's full patch selection.
`tools/test_daily_rewards_reroll.py` executes its native receive/draw/input paths
with real fonts and synthetic item/monster artwork. It checks shared counters,
prices, disabled states, pending refresh, stale claim tokens and older snapshots.
Daily Rewards compatibility and six-result checks also apply to this runtime.
Live gameplay acceptance remains separate; installed client/server files and
player data were not modified. Unrelated feature suites were not rerun.

The release notes below are historical; the deployment requirements above
supersede their statements about which servers/schema must be updated.

Select **Attendance, Daily Quest and Daily Roll** (`DailyRewardsUI`) in WARP.
Target: **2025-07-16 Ragexe**, with the matching rAthena changes in
`D:/AAARAGNAROK/Ragnarok`. Repatch the clean source EXE; do not patch an already
patched executable. Restart WARP to load the new patch entry.

This replaces the action of the existing **Attendance** menu button. It works
through the same command in Classic and New menu layouts. Keep Attendance
visible in your menu configuration. The original calendar icon is reused;
there is no extra menu button or separate Battle Pass tab.

## Six-result Roll and shared quest rewards (2026-10-16)

The current DRUI v4 client displays six Roll cards and supports 1..6 rewards
from one daily claim. The server also assigns 1..6 weighted rewards to each
Daily Quest using the same Roll item IDs, quantities and High/Mid/Low weights.
The configured pools contain 320 monsters, 295 collection items and 46 usable
items; PvP requires a random 1..3 kills. Targets, counts and quest rewards remain
fixed for that account/day. Existing assignments update on the next daily
assignment, without clearing progress.

For this update, apply server migration
`sql-files/upgrades/2026-10-16--daily-rewards-six-rolls.sql`, rebuild/restart
map-server (and map-server-generator if used), and load the updated NPC. The
migration widens saved state from 404 to 412 bytes without replacing existing
data. The reader preserves old attendance, quests and Roll results. Restart
the current WARP checkout and repatch a clean source EXE with DailyRewardsUI.
No new char-server change is needed for this update; the previous attendance
rental-mail update has its own char-server and SQL requirements.

Protocol v4 is 9420 bytes: the unchanged v3 catalog followed by one 56-byte Item
for the sixth result. Open/Refresh advertises DRU2 in slot and DRU4 (`0x34555244`)
in date. Claims carry the real date and negotiated version. The runtime retains
v1/v2/v3 server compatibility (five Roll cards with an old server). Old clients
on the new server can use attendance/quests, but must update to start a Roll.
Six results still use the existing RODEX delivery, split into two mails.

`tools/test_daily_rewards_six.py` checks the emitted native client for all six
counts, the sixth tooltip/right-click, animation/skip, malformed replies and
legacy compatibility. `tools/test_daily_rewards_ui.py` checks the rest of this
same window. Passing evidence and screenshots are in
`Outputs/daily-quest-pools-20261016`; fonts are real and artwork is a test
placeholder. No installed client was replaced. Unrelated gameplay suites were
not rerun. The paired server guide is `D:/AAARAGNAROK/Ragnarok/doc/daily-rewards.md`.

## Features

- Attendance: 28 days, seven days per page, up to six items per day in a compact
  two-column, three-row Battle Pass-style grid. Available days have a green
  outline and label; claimed days have faded icons and the blue diagonal
  CLAIMED stamp. Select the available day, then use **Claim Reward** below.
  One claim per account per server calendar day; future days remain locked.
  The next unclaimed day is available regardless of missed logins.
- Daily Quest: five entries randomly drawn without replacement each day from
  the configurable task list. Supports any-monster kills, a randomly chosen
  specific monster, inventory item collection, usable-item activation, and PvP
  kills. Each mission row shows its monster/item/PvP image, progress count and
  bar, action button, and up to six rewards in a compact two-column, three-row
  grid with quantities underneath. Claimed rewards receive the same stamp.
- Daily Roll: one free roll per account per day. The server draws a uniform
  count from one to six, then draws each reward from a weighted pool. Repeats
  are allowed. Gacha-style horizontal cards reveal the server's result one at a
  time; unused slots say “No reward.” **Motion: On/Off** and **Skip Reveal** only
  change the animation, never the server's awards. Possible Rewards uses six
  cards per page (three columns by two rows), with automatic page counts and
  disabled arrows at the ends.
- The approved three-tab layout keeps Daily Roll beside Attendance and Daily
  Quest under the existing Attendance menu button. Daily Roll has six numbered
  cards (four above, two below), mystery placeholders before rolling, and gold
  stars on revealed rewards. The daily status shows Ready, Rolling or Claimed.
  The reveal starts when the server response arrives, including on a slow
  connection. Motion Off keeps waiting cards static and shows results immediately.
- Hover any quest objective portrait for its target and **Required: count**.
  Any-monster quests show **ANY**; PvP shows **PvP Player**. Hunt, collection and
  use-item tooltips show the target name from the existing server title.
  Attendance/quest rewards, roll results and the possible-reward pool show the
  item name and **Quantity: count**. Tooltips match the supplied native style:
  pale yellow `#FFFFDE`, border `#8C847B`, and dark text `#292929`.
  Only one tooltip is displayed, clamped inside the window. Monster/PvP hover
  never opens an item description; item icons keep their existing right-click action.
- Right-click an item for the native item description. Use the title-bar
  X or Attendance menu button to close. The window can be dragged by its title.

The native window is 920 x 720; use a client resolution of at least 1024 x 768.
UI chrome is drawn by the client, and item icons come from the existing item
resources in your data/GRF. No additional UI Lua or texture files are required.
Adding menu tabs to this client is implemented in the native frame payload,
rather than through unsupported Lua window definitions.

## Server installation

1. Review `npc/custom/Ragnarok/Main/daily_rewards.txt`. It contains the configured
   28 attendance days, Daily Quest targets and shared 20-entry weighted pool.
2. Apply `sql-files/daily_rewards.sql` to the character database used by both
   map and char servers. It adds four independent InnoDB tables. The existing
   mail and mail-attachment tables must also use InnoDB. Do not truncate the
   claim/outbox tables during a daily reset.
3. Build the matching `map-server`, `map-server-generator` and `char-server`.
   The NPC is already registered in `npc/Ragnarok.conf` in this checkout.
4. Set `feature.attendance: off` in your deployment's battle feature override
   (normally `conf/import/battle_conf.txt`). This disables the stock login popup
   and stock claim system. The patched Attendance menu action uses DRUI and
   remains available. Keep the Attendance icon visible in WARP's menu settings.
5. Deploy the paired server/client build during your normal maintenance window.
   Restart map and char servers so the tracking hooks and mail worker are active.
   Test with a test account before enabling the example rewards for everyone.

The integration uses native rAthena source in this repository. It is not a
drop-in Hercules NPC: a Hercules port needs matching event, registry, packet,
SQL and mail integration.

## Configuration

All gameplay settings live in `npc/custom/Ragnarok/Main/daily_rewards.txt`, NPC name
`DailyRewardsConfig`. `.Enabled = 0` disables this feature. Keep `.Version = 1`.

| Setting | Meaning |
| --- | --- |
| `.AttendanceId[0..27]`, `.AttendanceAmount[0..27]` | One item reward per attendance day |
| `.AttendanceSlots` | 6 enables attendance bundles; 0 or absent preserves legacy one-item settings |
| `.AttendanceRewardId[(day-1)*6 + slot]`, `.AttendanceRewardAmount[...]` | Up to six items per day; slots are 0 through 5 |
| `.ResetMonth` | 1 also resets attendance at the first activity of a new month |
| `.TaskKind[]`, `.TaskTarget[]`, `.TaskCount[]` | Aligned task entries; at least five valid entries |
| `.TaskCountMax[]` | Inclusive random upper count; zero/absent keeps the corresponding count fixed |
| `.MonsterPool[]`, `.ItemPool[]`, `.UsePool[]` | Target pools when a task target is zero |
| `.QuestRewardId[entry*6 + slot]`, `.QuestRewardAmount[...]` | Up to six rewards per configured task entry |
| `.QuestRollRewardMin`, `.QuestRollRewardMax` | 1 / 6 selects weighted Roll rewards per quest; both zero enables the fixed QuestReward arrays |
| `.RollId[]`, `.RollAmount[]`, `.RollWeight[]` | Aligned weighted roll pool; 1–1024 entries |

Task kinds are 1 = any monster, 2 = specific monster, 3 = collection,
4 = usable item, and 5 = PvP. A nonzero task target fixes the monster/item ID.
The current PvP entry has `.TaskCount[4] = 1`, `.TaskCountMax[4] = 3` for 1..3 kills.
PvP credit requires a PvP map and a different account; population-engine bots
do not count. Repeated legitimate kills of the same opponent do count.

The current NPC uses explicit arrays for each attendance day. Edit the matching
pair to change that day, for example:

```text
// Day 1: six items, with a matching amount for every ID.
setarray .AttendanceRewardId[0],501,502,503,504,505,506;
setarray .AttendanceRewardAmount[0],10,5,3,2,1,1;
// Day 28: two items, four unused slots.
setarray .AttendanceRewardId[27*6],607,608,0,0,0,0;
setarray .AttendanceRewardAmount[27*6],1,1,0,0,0,0;
```

Use your own item IDs and quantities. Set both fields of an unused slot to zero.
An invalid item/amount rejects the entire day bundle; it never grants only part.
All six items commit under the same account/day claim and use the existing
durable RODEX outbox (two mails if the attachment limit is five).

Collection is an **inventory possession objective**: the required non-rental
items must be in inventory when claiming, and are not consumed. Progress bars
reflect current inventory. Item-use credit is recorded after native use checks;
cancelled delayed-use target cursors do not count.

Set both reward ID and amount to zero for an unused attendance/quest reward slot. At least
one reward is required. Quantities must be 1–30000, and nonstackable rewards
must have quantity 1. Roll weights must be positive integers up to 1,000,000.
Invalid task/reward configuration refuses assignment/claim instead of silently
awarding a different item. Add task entries within these five kinds without
client changes; a genuinely new objective kind also needs its native tracking
implementation.

Assigned daily targets, counts and quest rewards are frozen in SQL until the
next day, so reloading the NPC does not reroll an account's tasks. Attendance
and roll configuration changes apply to subsequent claims. Refresh updates the
possible-reward page count and clamps pages when the pool shrinks.

## Persistence and resets

The server's local calendar determines midnight, including DST. Resets are
evaluated on the next request or tracked event; no online-only midnight timer
is required. After day 28, a new attendance cycle starts the following day.
With `.ResetMonth = 1`, the first activity of the new month also starts a cycle.
Clock rollback cannot grant another day's claims.

`#Attendance_Day` is the number claimed in the current cycle;
`#Attendance_LastClaim` stores the server date as `YYYYMMDD`. They mirror the
account's SQL state and are updated after a confirmed commit. SQL is the
authoritative recovery source if registry saving or the connection is interrupted.

The account row lock covers task assignment, progress, claim status, roll
results and reward enqueue. A unique account/date/type/slot claim key provides
an additional replay guard. The char worker creates RODEX mail and attachments
in one transaction and records the mail ID. It retries pending delivery after
restart without granting the claim again. Six-item quests use multiple mail
batches if the server's attachment limit is five. Rewards go to the character
that claimed them, and do not depend on the rolling animation finishing.

## Files and verification

- `Scripts/Patches/DailyRewardsUI.qjs`: guarded Attendance command replacement,
  payload relocation, private vtable and packet receiver.
- `Scripts/Runtime/DailyRewardsUI/`: editable native UI and packed wire header.
- `Inputs/DailyRewardsUI/runtime.bin` and `runtime.json`: generated import-free
  payload and checksummed metadata. Rebuild with `tools/build_daily_rewards_ui.py`.
- `tools/test_daily_rewards_ui.py`: executes the emitted x86 and renders all tabs.
- Server `src/map/daily_rewards*`, `src/common/daily_rewards.hpp`, NPC and SQL:
  state, tracking, request handling and independent durable mail outbox.
- Server `tools/test_daily_rewards_server.cpp` and
  `tools/test_daily_rewards_database.py`: actual NPC/compiler/VM, native state
  handlers and isolated SQL/claim/mail tests.

DRUI requests remain 32 bytes on the existing custom-request dispatcher 0x0BF8.
The new client initially uses v1 Open with `slot=0x32555244` (DRU2 capability).
Open/Refresh previously ignored slot, so an old server still returns its normal
3308-byte v1 reply. The new server negotiates v2: the unchanged v1 prefix plus
five additional items per visible day, 5268 bytes total. Subsequent claims use
the negotiated protocol. New clients accept either exact version/size pair;
old clients continue using one-item attendance but cannot claim unseen bundles.
Both replies use magic `DRUI` on variable-length 0x0BF4. Non-DRUI quest
status replies retain their original handler. BPUI/GCHA/0x0BF6, VIPU/0x0A1C and
AutoHunt/AutoSupport/0x0BEF routes are not modified.

Offline builds and regression tests do not replace live client acceptance.
This presentation/bundle update needs the new WARP payload, rebuilt map-server
and map-server-generator, and updated `npc/custom/daily_rewards.txt`. Existing
DRUI installations need **no SQL migration, player reset, or char-server change**.
Rebuild on the Linux VPS using its existing build configuration; Windows test
EXEs are not Linux deployment binaries. The VPS was not changed by this update.

Current staged builds and render evidence are under
`Outputs/daily-rewards-restored-20261009/` in each repository. Render tests execute
the emitted native UI and real font calls with placeholder item/monster artwork;
they are not in-game screenshot acceptance. No SQL migration, EXE replacement or game restart is
performed against the installed server/client by these build tools.

The latest preview styling and delayed-reply/Motion-off checks are staged in
WARP's `Outputs/daily-rewards-approved-20261009/`. The paired server remains
`4ab0855` in `devseara/Ragnarok`; this client refinement needs no additional
server changes. To keep build evidence separate, the payload compiler accepts
`--work-dir Outputs/daily-rewards-approved-20261009/runtime`.

The tooltip update is staged in `Outputs/daily-rewards-tooltips-20261009/`.
It retains both DRUI packet versions and needs no additional server update.

## Daily Roll animation update (2026-10-09)

Daily Roll uses the active Gacha timings: a 100 ms icon clock, a 1020 ms first
reveal deadline, then 220 ms between reveals. The 100 ms timer rounds those
deadlines to its next callback (normally 1100 ms and 300 ms). Network latency
can extend Gacha's server-delivered steps; Daily Roll reveals its already
authoritative results locally. Its cosmetic clock continues through delayed
responses; the reveal clock starts only after the reply arrives.

Each card has an independent cosmetic random stream drawn from the complete
configured .RollId pool, regardless of the Possible Rewards page. Duplicate
IDs are collapsed for animation only. Simultaneous spinning cards show
different icons when at least five unique IDs exist; small pools necessarily
reuse items. Icons stay centered, matching Gacha. Weighted prize selection,
1-5 reward count, quantities and once-daily claims remain server-owned.
Animation does not change odds or send extra requests.

DRUI protocol 3 appends 1024 ItemIds to the complete v2 snapshot (9364 bytes
total). The reward_total field gives the catalog length; unused entries are
zero. Open/Refresh initially use protocol 1 with slot=0x32555244 (DRU2) and
date=0x33555244 (DRU3). Read-only Open/Refresh did not otherwise use date.
Existing v1/v2 servers ignore the additional capability and keep their
existing replies. Claims carry the actual calendar date and use protocol 3
only after a v3 reply. Old clients still receive exact v1/v2 replies.
The two daily_rewards_wire.hpp copies must remain identical.

To animate the entire pool, update and rebuild **map-server** (and
map-server-generator if used), restart it, then repatch the client with
DailyRewardsUI. Restart WARP before repatching. An older server remains
compatible but supplies only the visible six-item page for animation.
No SQL migration, NPC reward edits, char-server rebuild or player reset is
required for this update. Battle Pass, VIP, ChatUI and Gacha source are
unchanged. Client test EXEs and Windows server binaries are staged under
Outputs/daily-roll-animation-20261009/ and are not installed automatically.
