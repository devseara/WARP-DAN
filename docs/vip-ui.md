# Native VIP UI v4

The September 18 Ragnarok skin updates the complete native VIP window and its
popups. See [skin, assets and preview deployment](vip-ragnarok-skin.md).

Independent optional patch VipUI (10008), for 2025-07-16 Ragexe. Requires the
matching VIPManager.txt / VIPSystem.txt and VIPU v4 server from devseara/Ragnarok.

Install the current base BattlePass-ChatUI-NPC-Gacha package first (it already
contains the accepted Gacha v20 and Battle Pass name fixes). Then apply the
separate install/DevSeara-VIP-UI.diff after git apply --check succeeds.
The announcement add-on is independent and optional. Do not replay historical
Gacha upgrade diffs over the current full base package.

Select Native VIP UI in WARP and rebuild from the original source client using
your existing patch selections. Applying the patch automatically creates
`data/texture/<client UI prefix>/vipui` beside the output EXE and copies its 7
required PNGs (four Gacha-style button backgrounds, design atlas, crown,
item-box background) only when missing. Existing art is preserved; a later
build repairs missing files. Selecting the checkbox alone does not install art.
No profile is silently changed; no client EXEs are distributed in this package.

The Roulette/VIP icon toggles VIP (its artwork remains yours to replace).
When open it closes immediately, sends the existing Close action, and clears
the popup, capture and polling timer. When closed it retains the native 0A19
request and waits for a fresh server-authorized snapshot. Snapshot delivery
itself does not toggle, so upgrade responses cannot accidentally close VIP.
Esc closes the foreground VIP popup first, then the main card on the next
press. Held-key repeats are consumed without dismissing another window.
Native modals, Alt+Esc, foreign capture and visible foreground roots retain
their existing keyboard handling. The profiled WM dispatch call sites wrap
the existing manager entry; the Battle Pass key hook remains intact.
The native card
shows canonical name, membership dates, VIP EXP, earned crowns, active benefits,
membership/store/storage/buffs and Upgrade. The 460x362 compact card renders the current
character using the native Alt+Q compositor on a private offscreen frame. It
includes body, hair/palettes, upper/middle/lower headgear and garment views, with
costumes taking priority in all four slots. Multi-slot headgear is drawn once;
zero-view costumes hide the underlying normal slot. Equipment is never changed.
Large sprites fit inside the portrait; native SPR/ACT appearance needs live
acceptance. Apply VIP is enabled only without active membership or a pending payment. Open Store and
Open Storage require active membership; Shop also stays disabled until configured.

Single-line fields read `Name: <character>`, `VIP Start Date: <date>` and
`VIP Expiry Date: <date>`. Matching server dates use `09-17-2026 Thursday` format,
server-local calendar dates and English weekdays; missing history is not invented.
When the active-membership flag is absent, both dates display `Not Active`,
even if the server retains historical dates or a previously earned VIP level.

Main and popup buttons use shared Gacha-style PNG backgrounds with
native centered captions and normal/hover/press/disabled states. The four main actions
are 128x22 in a centered two-column grid; Upgrade/Refresh are 60x20.
Hit bounds exactly match the painted controls. Missing/mis-sized normal artwork disables
actions; missing optional states fall back to the normal PNG. The private
`vip_design.png` atlas must be 1412x1114. The bundle contains only the seven
currently used images. Legacy per-control skins are no longer bundled; retain
their backup when rolling back to an older executable.
See [button filenames and sizes](vip-ui-buttons.md). WARP's ordinary installer
does not overwrite existing custom art. Start-date values are green, expiry-date
values red, and labels navy. Dates and all other account data remain server-owned.
Benefits use approved blue/gold crown cards with four visible rows at a time and
bounded, left-aligned text. Main labels, dates, EXP, cooldown and body text use
the same 11px regular native font as Membership active, including every
button, heading and popup price. Canonical names retain their private text helper.
Hovering a clipped benefit card displays its complete server-supplied text in
the existing native Ragnarok tooltip (up to the protocol's 79-byte limit).
Short fitted labels need no tooltip. The hint follows the current scroll row
and is suppressed for modal dialogs, hidden/expired UI and foreign capture.
The client uses stock cursor tooltip reset and positioning, without a shared
tooltip hook or character-name substitution.
The benefits scrollbar has working arrow buttons, a 10px-wide track, and a
proportional draggable thumb. Clicking above/below the thumb pages by four
rows; the native wheel handler (frame slot 35) moves one row per signed wheel
event while the pointer is over the VIP window. Scrolling is local and sends
no packets. Thumb dragging owns only this window's native left capture,
updates through both move routes, and clamps even when released outside.
Same-content refreshes preserve dragging; changed extent/token, expiry, popup,
close/Esc or lost capture cancels it without releasing another window's capture.
Popups, pending requests, invisible artwork and lists of four or fewer rows
cannot start scrolling. Existing arrow and benefit-tooltip behavior is retained.
Popups retain their existing readable sizes and are centered over the parent.
`VIPSystem.txt` supplies the current tier's descriptions
through its `S_Level1`..`S_Level10` / `S_Rows` text configuration (1-20 rows,
up to 79 bytes each). Actual bonus commands stay exclusively in `vip_db.yml`.
The complete `Auto drop -N%` message is another editable row in that script;
native source no longer builds or appends it. Text changes do not change bonuses
or penalties; keep descriptions in sync with YAML and the automation battle flags.
BenefitRows=1024 uses the existing line1/line2 slots for up to 20 current-tier
rows without changing packet size or version. The client still reads old
per-tier pipe-separated snapshots when that flag is absent.
Previous/future tiers are not added together. Non-VIP users, VIP level zero and
disabled VIP levels have no benefit cards; expired benefits clear on the next
snapshot. The PNG arrows move one card at a time, disable at
the limits, and update the position indicator. Refresh preserves position;
reopening resets it and fewer effects clamp it. No new packet or version is
needed. The approved atlas crown appears in earned level boxes:
level zero has no crowns; levels one through ten have one through ten crowns.
The old `star_on.png` is kept for recovery but no longer rendered.
`membership_crown.png` appears on each membership-duration card; keep its alpha.
The main level caption is `VIP Level : N`, with no maximum-level denominator.
Requirement item icons sit inside item_main_bg.png.

The EXP bar uses a gold outline and gold gradient fill at every percentage.
Only its fill length changes with the authoritative percentage. Gold is styling,
not readiness: server permission still controls Upgrade, and level 10 does not
imply another upgrade. The next level's refresh clears the old fill. No image
file or shared texture is recolored.
Level zero without active membership and
zero-denominator EXP counters (including 0/0 EXP) are hidden.

Full EXP enables Upgrade. Confirmation and requirement windows use native
bring-to-front on every open/reopen. Clicking the blocked main VIP window while
a popup is open raises the popup instead of dragging/activating the main card.
Upgrade/Submit Yes now waits for an outstanding Refresh reply and then at least
350ms after that reply before sending once. This avoids the server's existing
shared 300ms Refresh/action cooldown. The parent remains visible with a waiting
message and blocked actions until the authoritative Open response arrives.
No mutation is automatically retried. Changed requirements cancel an unsent
request; Close cancels its local queue. A missing reply after ten seconds shows
a close/reopen instruction. Closing cannot undo an already-sent operation.
The UI timer wakes at 100ms only to service this queue; background refreshes
remain three seconds apart, including while a confirmation sits open, to renew
the server token. Polling pauses only after Yes queues an upgrade. Server packet
formats, cooldowns, costs and validation are unchanged.
Yes/No confirmation starts a server-owned random
item quest; a separate popup shows item images, quantities, inventory counts,
Zeny cost, Upgrade and Cancel. Accepted quests reopen without rerolling; Cancel
only closes the popup. Opening the VIP/roulette icon shows the main card alone,
even with a saved quest. Upgrade reopens that quest without rerolling. Configure
real item pools per level in VIPManager.txt; preserve existing operator edits.
The server rechecks items/Zeny/EXP/VIP/locks before consuming requirements once.
Clicking Upgrade in the requirements window now opens a final frontmost Yes/No
confirmation. Only Yes sends SubmitQuest; No/X returns to the saved requirements.
Changed quest/level/cost/items or lost readiness cancels an open confirmation.
The server uses the regular `0x01F3` EF_ANGEL (371) effect so the upgrading
client resolves its own actor; the profiled `0x019B` handler omits that actor.
No global effect or text renderer is modified. VIP keyboard interception is
limited to its guarded WM key-call wrappers, with stock/Battle Pass fallback.

Hovering an upgrade-quest item displays its bounded name, required quantity
and inventory count in the native tooltip. Empty slots, hidden/closed popups,
dragging, presses, foreign capture and pending requests suppress the hint.
Hovering does not inspect, capture input, send packets or consume anything;
the existing left/right-click item description remains available.

Current automation schedule: non-VIP and VIP 1-5 -75%; level 6 -70%, 7 -65%,
8 -60%, 9 -55%, 10 -50%. These are the automation component, before other drop
bonuses. Matching 5440-5451 (-75% through -20%) TGA files and stateicon additions are in the server
repository's client folder. Those client data files must be merged separately;
WARP's VIP art installer does not overwrite stateicon Lua or custom effect art.

Apply VIP opens five selectable membership durations: 1, 3, 7, 15 and 30 days.
Cards use pale-blue beveled rows, crown and regular duration
on the left, regular right-aligned Zeny prices, and a cream/gold selected gradient.
Text and the card backgrounds remain native and dynamic; prices are not baked
into images. The crown is a separate editable PNG in `vipui`.
Selecting a row does not buy anything. Purchase submits the selected duration
and displayed price; Cancel/X closes without payment. The server owns all prices
through `.MembershipMinutes[]` and `.MembershipCost[]` in VIPManager.txt. The
initial 15-/30-day prices are editable placeholders of 5,000,000z / 9,000,000z.
Purchase is disabled until selection; a changed offer invalidates selection.
Active/pending membership, duplicate/stale tokens, changed quotes, locks and
insufficient Zeny are rejected server-side. Pending login-server acknowledgement
cannot be charged again. This does not replace the existing asynchronous payment
recovery policy with a transactional ledger.

VIP Buffs opens a compact frontmost `VIP Buffs` popup with the existing complete
Yes/No PNGs. The server supplies its prompt from `.BuffAmount` / `.BuffDuration`
(initially +7 all stats for 30 minutes). Opening, No and X do not claim anything.
Yes sends the fixed Buffs action once; no legacy NPC confirmation is opened.
The server reserves a persistent account-wide `#VIPBuffNext` deadline before
applying the six original cash-food effects. Claims are limited to one per rolling
3600 seconds, including after relog/character changes. VIP renewal, death or buff
removal does not reset the wait. The main button is disabled during cooldown and
shows `Buffs: HH:MM:SS` above the action grid's right column; only a server
refresh can re-enable it. Refreshes
occur every three seconds while the card is open. A stale open confirmation is
closed when membership/cooldown eligibility changes. The legacy NPC buff entry
redirects to the native card and cannot grant independently. Account saves use
existing asynchronous persistence, not a new crash-atomic SQL ledger; offline,
unloaded-account and ambiguous-save cases fail closed. A reserved claim stays on
cooldown after status-application failures to prevent repeated partial refreshes.

VIPU v4 uses 0A1C plus VIPU magic (2664 bytes), and independent 0BFA requests
(24 bytes). Five minute/cost pairs append to the unchanged v2 snapshot prefix;
requests append an echoed quote, never an authoritative client-supplied price.
The unchanged v3 prefix additionally gains 4-byte buff seconds and a 96-byte
prompt. BuffReady=512 requires active membership and zero remaining seconds.
Install matching client/map-server binaries together; old/new mismatches fail closed.
Stock roulette-info fallback remains; BPUI/GCHA/0BF6 are unchanged.
The runtime has no imported DLL dependencies, private text/item rendering,
window-owned capture, bounded fields and a UI-thread refresh timer. Its private
API is 372 bytes: existing offsets are unchanged, including the four Purchase
background pointers, regular 11px label/price adapters, crown path, atlas,
compact info/name text, centered status/body adapters and eight main-button
background pointers. The runtime
container format remains version 2; that is separate from the VIPU wire version.

The main window raises itself on explicit open/reopen, just like the quest
popup: registering a root alone inserts it behind existing HUD windows and
can leave covered Inventory/Equipment menu buttons receiving clicks. Refreshes
do not continuously steal the front. Esc handling is scoped to foreground VIP;
all unhandled keyboard input retains the native/Battle Pass path.
`VIP Upgrade Quest` centers each actual BMP inside its 32px box, labels owned
counts `Inventory:`, and formats required Zeny as `3,000,000z`. Left or right
click a populated item box to inspect the native identified item description.
Inspection requires down/up on the same slot, item ID and snapshot token;
right clicks never acquire native left-drag capture. A temporary CItem is
destroyed after the description window synchronously copies it. Empty/unknown
items, hidden windows, changed snapshots and foreign capture fail closed.

tools/build_vip_ui.py builds runtime.bin/json in a full WARP checkout with Visual
Studio C++ and pefile. Tests: test_vip_ui.py (including real EXP color pixels),
test_vip_button_pngs.py (all 60 Gacha-style control states, native captions, editable
pixel ownership, missing/mis-sized art, input states and bounds),
test_vip_visibility.py (earned crown pixels, active/expired benefits, fitted controls,
zero EXP, cleared mockup data and the EXP bar through its final column),
test_vip_portrait.py (native ABI/equipment selection/bounded composition),
test_vip_quest_ui.py (optional --game
for actual item BMPs), test_vip_quest_items.py (centering, both mouse buttons,
native CItem lifetime and input cancellation), test_vip_open_order.py (actual
native root hit selection over underlying HUD controls), test_vip_purchase.py
(five offers, exact quote packets, payment gating, editable Purchase PNG states),
test_vip_asset_install.js, plus all preserved suites and
standalone/reversed-order builds. Offline tests do not certify live gameplay.
`test_vip_buffs.py` covers the native confirmation, fixed claim packet, no-action
cancellation, server-only cooldown/expiry, stale presses, prompt bounds and PNGs.
`test_vip_benefit_boxes.py` verifies left-aligned regular text, 20 script-defined rows and
scrolling. `test_vip_submit_confirmation.py` covers final Yes/No, no premature
submission, foreground/capture and changed-snapshot invalidation.
`test_vip_upgrade_effect.py` executes the actual client handlers and actor
lookups to verify EF_ANGEL resolves both self and other characters.
`test_vip_upgrade_race.py` covers delayed refreshes, single-send ownership,
duplicate clicks, stale requirements, lost replies, transport failure and tick
wrap. `test_vip_benefit_hover.py` covers the complete native tooltip ABI and all
20 scroll rows. `test_vip_timer_visibility.py` verifies that no later background
draw erases the lower countdown glyph rows.
`test_vip_hover_toggle.py` executes the real icon command, keyboard call wrappers,
server-request reopening, popup/main Esc cleanup, repeat/modal/foreground guards,
stock/Battle Pass forwarding and three bounded item-hover hints without packets.
`test_vip_scrollbar.py` covers native wheel ABI, track paging, thumb geometry,
continuous captured movement, bounds/release-outside, content refresh and
all cancellation/capture guards without sending scrolling requests.

Keep stable-battlepass-gacha-2026-09-15 immutable. Back up installed binaries and
data, stop affected processes, verify matching client/server versions, then test
membership, expiry, full-EXP confirmation, quest reconnect/submit and the existing
Battle Pass/Gacha flows. Never reset live player data as part of installation.
