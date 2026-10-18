# Battle Pass availability switch

With the matching server update, `BattlePassSystem: no` in the server's
`conf/battle/feature.conf` keeps the menu icon visible but prevents the window
from opening. The server displays `Battle Pass is not Started yet` in red.
Set it to `yes` to allow opening again. Missing settings default to enabled.

Repatch using the updated `BattlepassUI` patch and rebuild/restart the matching
map-server. Menu opening now sends BPUI action 21 and waits for the server's
Open reply. Closing remains immediate. The v2 Details control flag 8192 closes
an existing window, stops its timer and clears pending UI state when disabled.
The native view toggle remains available for Escape and approved replies.

The stock menu and ROGlobalZeroMenu use the same published request callback.
Packet IDs, existing protocol layouts, mission/reward handling and Gacha
transport ownership are preserved. Item Collection is unchanged.

Offline verification includes `tools/test_battlepass_feature_gate.py` (built
client plus exported native manifest), `tools/test_battlepass_menu.py` (complete
menu fixture), and the accepted combined-client regression suite. Live game
acceptance remains required before replacing an installed binary.
