# Native VIP UI v2

Independent optional patch VipUI (10008), for 2025-07-16 Ragexe. Requires the
matching VIPManager.txt / VIPSystem.txt and VIPU v2 server from devseara/Ragnarok.

Install the current base BattlePass-ChatUI-NPC-Gacha package first (it already
contains the accepted Gacha v20 and Battle Pass name fixes). Then apply the
separate install/DevSeara-VIP-UI.diff after git apply --check succeeds.
The announcement add-on is independent and optional. Do not replay historical
Gacha upgrade diffs over the current full base package.

Select Native VIP UI in WARP and rebuild from the original source client using
your existing patch selections. Its twelve supplied PNGs are copied to
data/texture/<client UI prefix>/vipui only when missing. Existing art is preserved.
No profile is silently changed; no client EXEs are distributed in this package.

Roulette opens VIP (its icon artwork remains yours to replace). The native card
shows canonical name, membership dates, VIP EXP, ten stars, scrollable benefits,
membership/store/storage/buffs and Upgrade. The left badge uses supplied star
art; it is not a live player paperdoll. Shop stays disabled until configured.

Full EXP enables Upgrade. Yes/No confirmation starts a server-owned random
item quest; a separate popup shows item images, quantities, inventory counts,
Zeny cost, Upgrade and Cancel. Accepted quests reopen without rerolling; Cancel
only closes the popup. All real item pools remain empty for the operator to
configure per level in VIPManager.txt. Screenshot sample items are test data only.
The server rechecks items/Zeny/EXP/VIP/locks before consuming requirements once.

Current automation schedule: non-VIP and VIP 1-5 -75%; level 6 -70%, 7 -65%,
8 -60%, 9 -55%, 10 -50%. These are the automation component, before other drop
bonuses. Matching 5440-5449 TGA files and stateicon additions are in the server
repository's client folder. Those client data files must be merged separately;
WARP's VIP art installer does not overwrite stateicon Lua or custom effect art.

VIPU v2 uses 0A1C plus VIPU magic (2524 bytes), and independent 0BFA requests
(16 bytes). Stock roulette-info fallback remains; BPUI/GCHA/0BF6 are unchanged.
The runtime has no imported DLL dependencies, private text/item rendering,
window-owned capture, bounded fields and a UI-thread refresh timer.

tools/build_vip_ui.py builds runtime.bin/json in a full WARP checkout with Visual
Studio C++ and pefile. Tests: test_vip_ui.py, test_vip_quest_ui.py (optional --game
for actual item BMPs), test_vip_asset_install.js, plus all preserved suites and
standalone/reversed-order builds. Offline tests do not certify live gameplay.

Keep stable-battlepass-gacha-2026-09-15 immutable. Back up installed binaries and
data, stop affected processes, verify matching client/server versions, then test
membership, expiry, full-EXP confirmation, quest reconnect/submit and the existing
Battle Pass/Gacha flows. Never reset live player data as part of installation.
