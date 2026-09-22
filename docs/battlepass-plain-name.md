# Battle Pass plain character names

The 2025-07-16 Battle Pass client now renders the `player` snapshot field directly
in My Stats and the Hunter sidebar. The server already fills this field from
`sd->status.name`; no SQL, NPC or packet-format change is needed.

The private renderer bypasses the shared actor-name formatter, so Admin prefixes,
custom titles and guild-position suffixes are not added. It does not strip words
from actual character names. World labels, other windows, item text and Gacha are
unchanged. Battle Pass works without selecting Gacha in WARP.

Implementation: `Scripts/Patches/BattlepassUI.qjs`, `plainPlayer(height)`.

- Retains the configured Battle Pass font height and existing text positions/color.
- Reads at most 23 bytes from the existing 24-byte field, converts UTF-8 to UTF-16,
  and fits the name within the 141px sidebar or 526px stats area.
- Preserves complete surrogate pairs when fitting Unicode names.
- Uses the profiled native surface DC/font cache and direct GDI TextOutW; restores
  the HDC color and releases the native wrapper, which restores the original font.
- Checks the native entry signatures and GDI imports before applying the patch.
- Adds a small `BattlepassUI.PlainName.v1` read-only verification record; it is not
  a new protocol envelope or runtime hook.

Offline regression tests (not live screenshot acceptance):

```powershell
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_battlepass_plain_name.py <client.exe>
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_packet_0bf6_route.py <client.exe> --expect bpui,gcha
```

Run the name test and router test again on a Battle-Pass-only build with
`--expect bpui`. The test executes emitted x86 with explicit native/GDI boundary
doubles, checks both call sites, canonical/Unicode names, length and width bounds,
font height, failure handling, GDI state restoration and callee-save/stack ABI.

The combined and standalone 14px builds passed these checks on September 15,
2026. The combined build also passed the Gacha v20 eight-featured-prize regression
and Battle Pass asset-install test. Deployment requires closing only Ragnarok;
map-server and char-server are unchanged. Keep the previous EXE for rollback.
