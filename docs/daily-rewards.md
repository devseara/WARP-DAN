# Attendance, Daily Quest and Daily Roll

Select **Attendance, Daily Quest and Daily Roll** (`DailyRewardsUI`) in WARP.
Target: **2025-07-16 Ragexe**, with the matching rAthena changes in
`D:/AAARAGNAROK/Ragnarok`. Repatch the clean source EXE; do not patch an already
patched executable. Restart WARP to load the new patch entry.

This replaces the action of the existing **Attendance** menu button. It works
through the same command in Classic and New menu layouts. Keep Attendance
visible in your menu configuration. The original calendar icon is reused;
there is no extra menu button or separate Battle Pass tab.

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
  count from one to five, then draws each reward from a weighted pool. Repeats
  are allowed. Gacha-style horizontal cards reveal the server's result one at a
  time; unused slots say “No reward.” **Motion: On/Off** and **Skip Reveal** only
  change the animation, never the server's awards. Possible Rewards uses six
  cards per page (three columns by two rows), with automatic page counts and
  disabled arrows at the ends.
- The approved three-tab layout keeps Daily Roll beside Attendance and Daily
  Quest under the existing Attendance menu button. Daily Roll has five numbered
  cards (four above, one below), mystery placeholders before rolling, and gold
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

1. Review `npc/custom/daily_rewards.txt`. Its rewards are **example settings**;
   set item IDs, quantities, task counts and weights for your server economy.
2. Apply `sql-files/daily_rewards.sql` to the character database used by both
   map and char servers. It adds four independent InnoDB tables. The existing
   mail and mail-attachment tables must also use InnoDB. Do not truncate the
   claim/outbox tables during a daily reset.
3. Build the matching `map-server`, `map-server-generator` and `char-server`.
   The NPC is already registered in `npc/scripts_custom.conf` in this checkout.
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

All gameplay settings live in `npc/custom/daily_rewards.txt`, NPC name
`DailyRewardsConfig`. `.Enabled = 0` disables this feature. Keep `.Version = 1`.

| Setting | Meaning |
| --- | --- |
| `.AttendanceId[0..27]`, `.AttendanceAmount[0..27]` | One item reward per attendance day |
| `.AttendanceSlots` | 6 enables attendance bundles; 0 or absent preserves legacy one-item settings |
| `.AttendanceRewardId[(day-1)*6 + slot]`, `.AttendanceRewardAmount[...]` | Up to six items per day; slots are 0 through 5 |
| `.ResetMonth` | 1 also resets attendance at the first activity of a new month |
| `.TaskKind[]`, `.TaskTarget[]`, `.TaskCount[]` | Aligned task entries; at least five valid entries |
| `.MonsterPool[]`, `.ItemPool[]`, `.UsePool[]` | Target pools when a task target is zero |
| `.QuestRewardId[entry*6 + slot]`, `.QuestRewardAmount[...]` | Up to six rewards per configured task entry |
| `.RollId[]`, `.RollAmount[]`, `.RollWeight[]` | Aligned weighted roll pool; 1–1024 entries |

Task kinds are 1 = any monster, 2 = specific monster, 3 = collection,
4 = usable item, and 5 = PvP. A nonzero task target fixes the monster/item ID.
For example, `.TaskCount[4] = 3` changes the example PvP task to three kills.
PvP credit requires a PvP map and a different account; population-engine bots
do not count. Repeated legitimate kills of the same opponent do count.

The updated NPC enables six attendance slots and copies each existing daily
reward into slot 0; it does not add extra items to your economy automatically.
Place overrides **after** that initialization loop, for example:

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
