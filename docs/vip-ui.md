# Native VIP UI v4

Independent optional patch VipUI (10008), for 2025-07-16 Ragexe. Requires the
matching VIPManager.txt / VIPSystem.txt and VIPU v4 server from devseara/Ragnarok.

Install the current base BattlePass-ChatUI-NPC-Gacha package first (it already
contains the accepted Gacha v20 and Battle Pass name fixes). Then apply the
separate `install/DevSeara-VIP-UI.diff` after `git apply --check` succeeds.
That preserved bootstrap installs the original VIP package. Next apply
`install/DevSeara-VIP-UI-v2-upgrade.diff` to install this updated source, runtime
and artwork. Existing original-v2 installations need only the upgrade diff.
Do not reapply either diff to an already updated working copy; check first.

```powershell
git apply --check -- "$patchPackage/install/DevSeara-VIP-UI-v2-upgrade.diff"
git apply --whitespace=nowarn -- "$patchPackage/install/DevSeara-VIP-UI-v2-upgrade.diff"
```

Back up existing client VIP artwork before the original-v2 migration. Replace
the old complete button PNGs with the matching files from `Assets/VipUI` and
preserve/reapply custom artwork at the documented dimensions. The automatic
missing-file installer intentionally never overwrites an existing image.
Install matching client and map-server together; no player-data reset is needed.
The announcement add-on is independent. The preserved VIP bootstrap's registry
context expects it installed first. Do not replay historical
Gacha upgrade diffs over the current full base package.

Select Native VIP UI in WARP and rebuild from the original source client using
your existing patch selections. Its 58 bundled PNGs (52 complete button states,
the crown and retained legacy artwork) are copied to
data/texture/<client UI prefix>/vipui only when missing. Existing art is preserved.
No profile is silently changed; no client EXEs are distributed in this package.

Roulette opens VIP (its icon artwork remains yours to replace). The native card
shows canonical name, membership dates, VIP EXP, earned crowns, active benefits,
membership/store/storage/buffs and Upgrade. The 800x420 card renders the current
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

Every button loads a complete PNG including its caption: no code-drawn caption,
border, tint, cropping or scaling. Open Store, Apply VIP, Open Storage and VIP
Buffs have separate `openstore`, `applyvip`, `openstorage` and `vipbuffs` files.
Their fitted widths and click bounds are preserved. Main and quest Upgrade share
`upgrade` images. Refresh, Yes, No, Cancel and Close have their own images too.
Purchase has its own fitted 56x18 images. Each has `_out`, `_over`, `_press` and `_off` variants. Arrows keep `scroll_top.png`
and `scroll_bot.png` for normal, plus `_over`, `_press` and `_off` variants.
Keep exact dimensions when editing; missing/mis-sized normal artwork disables
the corresponding action. A missing/mis-sized optional state falls back to normal
artwork, not a regenerated caption. See [button filenames and sizes](vip-ui-buttons.md).
Existing legacy openstore images are only skin strips (66x18), not the new
complete 68x18 buttons. Back them up and explicitly replace them during migration;
the ordinary WARP installer deliberately does not overwrite existing artwork.
Benefits use vip_status_bg.png with one centered-text 44px card per effect,
five visible at a time. `VIPSystem.txt` supplies the current tier's descriptions
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
snapshot. scroll_top.png and scroll_bot.png move one card at a time, disable at
the limits, and update the position indicator. Refresh preserves position;
reopening resets it and fewer effects clamp it. No new packet or version is
needed. `membership_crown.png` appears in earned level boxes:
level zero has no crowns; levels one through ten have one through ten crowns.
The old `star_on.png` is kept for recovery but no longer rendered. The same crown
appears on each membership-duration card. Keep its original transparent alpha.
The main level caption is `Vip Level : N`, with no maximum-level denominator.
Requirement item icons sit inside item_main_bg.png.

vip_exp.png stays green below full EXP. It is tinted gold only at 100% when the
server permits upgrading, including saved quests with full EXP. Maximum level 10
does not imply another upgrade. This is a private draw tint, preserving the
supplied pixels' shading/alpha and leaving the image file/shared texture intact.
The next level's EXP refresh restores green automatically.
Opaque interior columns of vip_exp.png are stretched so all four rows reach the
end; its transparent edge is not stretched into a narrowed tail. Level zero and
zero-denominator EXP counters (including 0/0 EXP) are hidden.

Full EXP enables Upgrade. Confirmation and requirement windows use native
bring-to-front on every open/reopen. Clicking the blocked main VIP window while
a popup is open raises the popup instead of dragging/activating the main card.
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
No global effect/input/render hook is modified.

Current automation schedule: non-VIP and VIP 1-5 -75%; level 6 -70%, 7 -65%,
8 -60%, 9 -55%, 10 -50%. These are the automation component, before other drop
bonuses. Matching 5440-5451 (-75% through -20%) TGA files and stateicon additions are in the server
repository's client folder. Those client data files must be merged separately;
WARP's VIP art installer does not overwrite stateicon Lua or custom effect art.

Apply VIP opens five selectable membership durations: 1, 3, 7, 15 and 30 days.
Cards match the provided reference: rounded gray rows, crown and bold duration
on the left, bold right-aligned Zeny prices, and a cream/gold selected gradient.
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
shows `HH:MM:SS` alongside it; only a server refresh can re-enable it. Refreshes
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
API is 320 bytes: the previous 292-byte API remains unchanged, followed by four
Purchase PNG pointers, a private bold 14px label adapter, the crown path and a
private right-aligned bold 18px price adapter. The runtime
container format remains version 2; that is separate from the VIPU wire version.

The main window raises itself on explicit open/reopen, just like the quest
popup: registering a root alone inserts it behind existing HUD windows and
can leave covered Inventory/Equipment menu buttons receiving clicks. Refreshes
do not continuously steal the front. No global hotkeys or stock menus change.
`VIP Upgrade Quest` centers each actual BMP inside its 32px box, labels owned
counts `Inventory:`, and formats required Zeny as `3,000,000z`. Left or right
click a populated item box to inspect the native identified item description.
Inspection requires down/up on the same slot, item ID and snapshot token;
right clicks never acquire native left-drag capture. A temporary CItem is
destroyed after the description window synchronously copies it. Empty/unknown
items, hidden windows, changed snapshots and foreign capture fail closed.

tools/build_vip_ui.py builds runtime.bin/json in a full WARP checkout with Visual
Studio C++ and pefile. Tests: test_vip_ui.py (including real EXP color pixels),
test_vip_button_pngs.py (all 48 real state PNGs, no caption overlays, editable
pixel ownership, missing/mis-sized art, input states and bounds),
test_vip_visibility.py (earned crown pixels, active/expired benefits, fitted controls,
zero EXP and four-pixel bar through its final column),
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
`test_vip_benefit_boxes.py` verifies centered text, 20 script-defined rows and
scrolling. `test_vip_submit_confirmation.py` covers final Yes/No, no premature
submission, foreground/capture and changed-snapshot invalidation.
`test_vip_upgrade_effect.py` executes the actual client handlers and actor
lookups to verify EF_ANGEL resolves both self and other characters.

Keep stable-battlepass-gacha-2026-09-15 immutable. Back up installed binaries and
data, stop affected processes, verify matching client/server versions, then test
membership, expiry, full-EXP confirmation, quest reconnect/submit and the existing
Battle Pass/Gacha flows. Never reset live player data as part of installation.
