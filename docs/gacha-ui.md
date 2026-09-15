# Universal Zeny Gacha UI v20 - DevSeara

Select **Zeny Gacha UI with Pity** (`GachaUI`, ID **10006**) for the
**2025-07-16 Ragexe** client. Native 760x440 light-blue UI; no DLL or web view.

## Features

- Independent NPC machines, costs, pools, rates, pity, history, spender rankings,
  Legendary Winners and machine-scoped GM99 Admin reset.
- Legendary, Epic, Rare and Common. Main NPC base rates are 0.10%, 1.00%, 5.00%
  and 93.90%; names/rates/prices/pity remain script-editable.
- x1, x5 + one free, x10 + two free. Each reward stops/reveals/delivers separately.
- Exact prizes go to inventory or durable mail if inventory cannot accept them.
  Mail title/message are script-editable. Mail survives relogs/restarts/resets.
- Legendary and Epic announce after delivery or successful mail queuing.
  Legendary Winners lists only Legendary rewards; history keeps all tiers.
- First eight distinct Legendary-pool IDs are featured, in declaration order.
  One item shows one box, five show five, eight or more show eight. Unused boxes,
  icons and hit targets disappear. No Epic padding; the entire reward pool still
  remains available for rolls and Show Prizes.
- Native right-click descriptions on all eight featured icons and reward cards.
  Twelve slots/page, data-backed Next, centered page numbers and canonical names.
- Text-fitted tabs/buttons, plain balance/per-pull text, no repeated modal balance,
  blue bonus text, no public-tab footer captions, left-aligned Admin panel,
  stable native rendering and no `itembox_000`.

## Required server and migration

Requires matching **GCHA wire v9**: 3788-byte snapshots, 32-byte requests,
version 9. The last three featured IDs are appended; earlier offsets and
independent Battle Pass routing are preserved. Old versions are rejected.

Server: [devseara/Ragnarok at 7b3e48a](https://github.com/devseara/Ragnarok/commit/7b3e48a2dd4c2bcd618e0661389c59e2757c129e).
Review changes for your fork rather than blindly cherry-picking an entire
server commit. This package excludes server source/executables, credentials,
player data, logs and personal patch profiles.

- [Active four-tier NPC](https://github.com/devseara/Ragnarok/blob/7b3e48a2dd4c2bcd618e0661389c59e2757c129e/npc/custom/gacha_zeny.txt)
- [Copyable independent machine](https://github.com/devseara/Ragnarok/blob/7b3e48a2dd4c2bcd618e0661389c59e2757c129e/npc/custom/gacha_machine_example.txt)
- [Tier settings and compatibility](https://github.com/devseara/Ragnarok/blob/7b3e48a2dd4c2bcd618e0661389c59e2757c129e/doc/gacha_ui_v19.md)
- [Eight-featured-item protocol/layout](https://github.com/devseara/Ragnarok/blob/7b3e48a2dd4c2bcd618e0661389c59e2757c129e/doc/gacha_ui_v20.md)
- [Mail behavior and editable wording](https://github.com/devseara/Ragnarok/blob/7b3e48a2dd4c2bcd618e0661389c59e2757c129e/doc/gacha_ui_v16.md)
- SQL: [original tables](https://github.com/devseara/Ragnarok/blob/7b3e48a2dd4c2bcd618e0661389c59e2757c129e/sql-files/gacha_zeny.sql),
  [Admin recovery](https://github.com/devseara/Ragnarok/blob/7b3e48a2dd4c2bcd618e0661389c59e2757c129e/sql-files/upgrades/gacha_ui_v7_admin.sql),
  [machine isolation](https://github.com/devseara/Ragnarok/blob/7b3e48a2dd4c2bcd618e0661389c59e2757c129e/sql-files/upgrades/gacha_ui_v15_machines.sql),
  [four-tier/mail upgrade](https://github.com/devseara/Ragnarok/blob/7b3e48a2dd4c2bcd618e0661389c59e2757c129e/sql-files/upgrades/gacha_ui_v16.sql).

For a v15 server, back up SQL and install the additive v16 mail schema plus
matching map-server, generator, char-server and client. Map/char must share the
configured database and required mail tables must be InnoDB. If the v16 mail
worker is already installed, eight featured items only needs the newer map/client
pair. Stop affected processes before replacement.

Keep Machine IDs unique/permanent. Admin reset archives/clears this machine's
records and all character pity for it, including offline characters; it does
not refund Zeny, remove awarded items, clear mail, or reset another machine.
Installation performs no reset and does not enable the example NPC.

## Install and test

Use [README](../README.md)'s fresh combined diff or v15-to-v20 upgrade. Required
helper scripts/registrations/router/assets are included by the full installer;
do not copy Gacha QJS alone into an old tree. Chat/Auto Combat helper scripts
must exist, but those features need not be selected.

Applying Gacha creates
`<output EXE folder>/data/texture/<UI prefix>/genericsui/gacha/` and copies
the four arrows only when missing. Customized images are preserved. Item
artwork comes from the client. Checkbox selection alone does not install assets.

```powershell
node tools/test_gacha_asset_install.js
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_gacha_featured.py path/to/patched.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_gacha_ui.py path/to/patched.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_gacha_v16_layout.py path/to/patched.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_gacha_capture.py path/to/patched.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_gacha_surface.py path/to/patched.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_packet_0bf6_route.py path/to/patched.exe --expect bpui,gcha
```

Use `--expect gcha` or `--expect bpui` for single-feature builds. Drawing tests
use Windows fonts. Optional previews/local artwork are offline fixtures, not
live game acceptance. See [package verification](gacha-package-verification.md).
