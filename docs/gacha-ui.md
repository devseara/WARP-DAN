# Universal Zeny Gacha UI v15 — DevSeara

Select **Zeny Gacha UI with Pity** (`GachaUI`, ID **10006**) for the
**2025-07-16 Ragexe** client. Native 760x440 light-blue UI inspired by the
provided Myth of Yggdrasil reference; no DLL or web view.

## Features

- Multiple NPC machines with independent server-owned prices, reward pools,
  rates, tier display names and pity limits.
- Permanent Machine IDs isolate character pity, history, spending ranks,
  Grand Winners and the GM-level-99+ Admin reset.
- Pull x1, x5 + one free, or x10 + two free. Rewards stop/reveal/deliver one
  slot at a time; future rewards are not sent early to the client.
- Native right-click item descriptions with the item-capture crash fix.
- Five featured Grand-prize slots; 12 slots per results/information page.
  Data-backed Next arrows; ten pages of history/spenders/winners and paginated
  prize catalogues. Canonical character names and centered winner labels.
- Fitted buttons/headings, tab descriptions, blue bonus text, stable cached
  rendering and a separate, confirmed Reset This Machine action.
- Existing original Machine 1 data is preserved when upgrading the server.

## Required server component

This is **not a script-only client patch**. Use matching GCHA **wire v7**
support. This WARP package intentionally excludes server executables/source,
database credentials, player data and personal patching profiles.

The matching server implementation is already published in
[devseara/Ragnarok at 6416b1a](https://github.com/devseara/Ragnarok/commit/6416b1a946809d2628efcb4c6b81c12d0f332736).
That commit also contains other server changes; review it for your fork rather
than blindly cherry-picking the entire server commit.

- [Multiple-machine setup guide](https://github.com/devseara/Ragnarok/blob/6416b1a946809d2628efcb4c6b81c12d0f332736/doc/gacha_machines.md)
- [Copyable independent NPC example](https://github.com/devseara/Ragnarok/blob/6416b1a946809d2628efcb4c6b81c12d0f332736/npc/custom/gacha_machine_example.txt)
- [Bridge and protocol definitions](https://github.com/devseara/Ragnarok/tree/6416b1a946809d2628efcb4c6b81c12d0f332736/src/map)
- SQL setup: [original tables](https://github.com/devseara/Ragnarok/blob/6416b1a946809d2628efcb4c6b81c12d0f332736/sql-files/gacha_zeny.sql),
  [Admin recovery tables](https://github.com/devseara/Ragnarok/blob/6416b1a946809d2628efcb4c6b81c12d0f332736/sql-files/upgrades/gacha_ui_v7_admin.sql),
  [independent-machine tables](https://github.com/devseara/Ragnarok/blob/6416b1a946809d2628efcb4c6b81c12d0f332736/sql-files/upgrades/gacha_ui_v15_machines.sql).
  The original-table schema already uses 127-character name storage;
  older installations may also need the server's `gacha_ui_v2_names.sql` upgrade.

Keep each independent NPC's `.MachineID` unique and permanent. Change its
`.MachineName$`, costs and pool arrays freely; moving/renaming an NPC does not
change its identity. Copy the example to create a machine and load it explicitly
in your server's NPC configuration. Do not reuse retired IDs. Existing legacy
8/16-argument commands use Machine 1; the new command appends Machine ID/name.

Admin reset affects this machine's records and every character's pity for it,
including offline characters, while leaving other machines alone. Permission,
single-use token, transaction, archive and generation checks are server-side.
The client cannot authorize a reset, price or reward. Completed awards are not
removed and Zeny is not refunded by a reset. Installing these files never runs
a reset or enables the example NPC automatically.

## Client installation and dependencies

Use the fresh combined or NPC-package upgrade diff described in [README](../README.md).
The diffs include the four arrow images and the necessary native helper exports.
The Chat UI and Auto Combat helper **scripts** must exist, but those features
do not need to be selected. Battle Pass and Gacha remain independent handlers;
a shared native opcode router prevents either patch from overwriting the
other's receive slot. The router also works with either feature selected alone.

Do not copy only `GachaUI.qjs`: the helper-router update, Battle Pass integration,
patch registration/ID and assets are required. Avoid mixing the updated raw
Battle Pass script with an old unmodified native helper.

When applied, Gacha creates `<output EXE directory>/data/texture/<UI prefix>/genericsui`
and copies missing `arrow_off_left.png`, `arrow_off_right.png`, `arrow_on_left.png`
and `arrow_on_right.png`. Existing customized images are not overwritten.
Item icons come from the client's own resources; no item database/art is bundled.

## Verification

The development v15 build passed the real-bridge/script/compiler suites and
isolated SQL tests for costs, pools, names, sequential awards, permission/token
boundaries and bidirectional Machine 1/2/3 reset/pity/record isolation. Live
Machine 1 was accepted by the author before the universal extension; v15 adds
offline isolation coverage and still needs your own live deployment checks.

Package tests execute the emitted x86 against explicit native boundaries:

```powershell
node tools/test_gacha_asset_install.js
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_gacha_ui.py path/to/patched.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_gacha_capture.py path/to/patched.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_gacha_surface.py path/to/patched.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_packet_0bf6_route.py path/to/patched.exe --expect bpui,gcha
```

Use `--expect gcha` or `--expect bpui` when only that feature was selected.
The full drawing test uses Windows fonts. `--preview path/to/preview.png` is
optional; `--game path/to/client-folder` optionally reads real item BMPs from
your local resources. Neither option is required or sends live purchases.
See [package verification](gacha-package-verification.md) for installer checks.
