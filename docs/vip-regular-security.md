# VIP regular typography and security follow-up — 2026-09-18

The compact 460x362 layout, control positions, server protocol and no-DLL client
architecture are unchanged. Every VIP-only text helper uses regular weight,
including price/day labels in popups. Field spacing, clipping and hover decisions
measure the same regular font. The 60 native-size button states use Tahoma Regular
with optically centered captions. The approved regular-weight preview supplies
the skin atlas; live account values are still erased/redrawn from server data.
Start dates remain green; expiry dates remain red. Asset inventory stays exactly
63 canonical PNG files. No global font or Battle Pass/Gacha renderer is changed.

The compact regression asserts nonbold draw/measurement flags in the main window
and all five popup modes. The button regression reproduces every installed PNG
from the regular-font exporter; hover/race/countdown regressions remain enabled.

Server changes are separate: see `doc/vip-security-20260918.md` in rAthena.
Offline native tests are not live gameplay acceptance or a claim that no exploit
exists. Server source and staged binaries do not update an already running server.
