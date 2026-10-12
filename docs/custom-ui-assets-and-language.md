# Auto UIs: languages, assets and accepted build

Target: 2025-07-16 Ragexe. AutoSupport requires AutoCombat and the Banquet map
server. This is the single implementation, asset and acceptance guide for this work.

## Accepted build

Accepted by the user on 2026-09-11. Saved in
`Outputs/accepted-auto-ui-2026-09-11/`, with `client.exe`, `client-and-assets.zip`,
`profile.yml` and `verification.json`. The profile preserves Japanese AutoCombat,
Filipino AutoSupport and the existing UTF-8 code page (65001).

EXE SHA-256:
`2e62da2ff147e9711bb168cfd5f24c40d42b3b6c7a1c26961c15cf082b18281e`.

The cleanup rebuild is byte-identical to this EXE and all 3,412 exported asset
files. Six unused generators and 28 unused parameters were removed without
changing emitted code or allocation layout. Runtime packages stay outside Git.
Use the package with an existing game installation; choose other languages when
applying the patches in WARP.

## Language and presentation

`$autoCombatUILanguage` and `$autoSupportUILanguage` independently offer eight
choices, with English as default. Saved `Chinese Traditional` and
`Chinese Traditional (Big5 / CP950)` values resolve to Traditional Chinese.

| Language | Native font | Legacy code page |
| --- | --- | ---: |
| English | Arial | ASCII |
| Traditional Chinese | MingLiU | 950 |
| Thai | Tahoma | 874 |
| Brazilian Portuguese | Arial | 1252 |
| Indonesian | Arial | 1252 |
| Filipino | Arial | 1252 |
| Korean | Gulim | 949 |
| Japanese | MS Gothic | 932 |

`Inputs/AutoUI/languages.json` defines the menu, font selector/charset and encoding.
Each translated locale has 140 human-readable labels and a generated ASCII byte
catalog with UTF-8 and legacy encodings. The native mapper at `0x00A6F060` selects
the appropriate bytes after all patches run; incompatible overrides fall back to
English. Initializers preserve registers, flags, stack and receiver while updating
only the 266 UI-owned text buffers. Windows locale, the client's global code page,
shared renderers and native tooltip font selection are unchanged. Fonts must cover
the chosen script; Windows font linking can supply missing glyphs. Server names,
protocol/resource keys and native Reset/Close bitmap labels retain their contracts.

Both UIs use the same 88x16 dropdown field, bitmap arrow, compact option labels
and 88-pixel popup with one outer border. AutoCombat hitboxes match the drawn list;
outside clicks dismiss it without reaching controls beneath it. Both menu tooltips
use the child-local `(0, -20)` anchor above the icon in Classic and New layouts.

The supplied `msg_autoattack.csv` contains 119 Base64 key/value rows with valid
UTF-8 Traditional Chinese, all representable in CP950. Its SHA-256 is
`9409fa2265d973746f6d7aa7f7dbc0b2bc946f2c6b075c64eff2254d6dcd33ff`.
Matching messages and terminology informed the Chinese wording. CSV `{}`/`<EDIT>`/
font tags and literal newline escapes are adapted to the native printf/plain-text
renderer. The original is unchanged; `Outputs/msg_autoattack.decoded.csv` is readable.

## Assets

Selected patches copy required assets beside `Warp.TgtExe` during `onApplied`,
without confirmation or saved copy flags. Test mode skips copying; failures remain
errors. AutoCombat reuses the AutoSupport dropdown source BMPs and exports them
even when AutoSupport is not selected.

| Patch | Files | Destination |
| --- | ---: | --- |
| AutoCombat UI | 2 | Native `autohunt/setting_looting` field and arrow |
| AutoSupport UI | 134 | Native `autosupport` (107), `effect/roz_autosupport` (27) |
| Item Collection UI | 77 | Native `item_collection` and `uirenewal/menuicon` |
| Redesigned Equipment Window | 21 | Native `uirenewal/equipmentui` |
| Redesigned Status Window | 18 | Native `uirenewal/statusui` |
| Fluent Emoji | 3,148 | `BohEmoji/fluent`, including manifest and licenses |

Native UI folders are below `data/texture/<native UI prefix>`. Target Monster
Health Bar already exports its six BMPs. Controller frames remain embedded.
Stock/GRF requirements and the separate Game Settings Lua prompt are unchanged.

`Assets/AutoSupportUI/autosupport` mirrors the dedicated runtime namespace;
`setting_player/bg_player_autosupport.bmp` supplies the Player page. Menu icons
have six states: New 45x41 and Classic 32x34, each normal/hover/pressed. Classic
preserves the stock frame, state chrome and magenta key. Rebuild it with
`tools/build_autosupport_classic_menu_icons.py --native-menu-root <extracted-menu-folder>`.
`tools/build_autosupport_icon_assets.py` and `tools/render_autohunt_controller_frames.py`
retain reproducible icon/controller sources; active loops contain 30 frames plus
one inactive frame.

## Runtime contract

QJS owns native rendering/input, drag/drop, lifecycle and snapshot decoding.
Banquet owns validation, persistence, execution and snapshots. AHUI uses the
3,792-byte profile layout; ASUI reuses it with party character IDs and single-master
selection in monster rows. Banquet returns the canonical selected party name.
ASUI uses request `0x0BF8`, snapshot `0x0BEF`, magic `0x49555341`, and messages
Open 1 / Snapshot 2 / SetScalar 3 / Resync 6. Router v4 keeps AHUI/ASUI/PINC/COUI
handler cells independent.

AutoCombat has seven tabs, scrollable Basic/Monster views, three Skill pages,
two Potion/Looting pages and Item intervals. Auto-Hunt evaluates potions;
Auto-Potion is a mutually exclusive potion-only mode on setting 46. Controller
coordinates persist under HKCU. AutoSupport replaces the Monster tab with Player
(up to eleven peers) and owns an independent window. Its 216x72 merged controller
orders AutoHunt/AutoSupport/AutoPotion and uses peer callbacks for the outer tiles.
Menu callbacks remain safe across patch removal/reapplication. `/autohunt` and
`/autosupport` remain alternate settings openers.

Drag/drop resolves inventory indices before registration. Server-owned delay
dialogs use shared attack/support/healing/recovery/item slots. AutoSupport loot
policy respects support priority; party/master validation and execution remain
server-owned. Existing servers require `sql-files/autosupport/support_assistant.sql`;
`support_assistant_profiles` persists the master name/ID and related ability/item
records preserve category, slot, delay, state, recovery/movement and loot policy.

## Verification

The language matrix passed 21 WARP builds with stock/UTF-8 mappings, saved Chinese
aliases and mixed windows. Unicorn checks generated text, encoding switches, cached
calls, register/flag/stack preservation and writable buffer bounds. The final saved
profile also passed those runtime checks. Dropdown/hover validation covered 100
mouse-handler cases, 12 tooltip cases and baseline/reapply-AutoCombat menu builds.
Windows GDI checked 72 fixed captions and 48 dropdown labels across all languages.
The AutoSupport asset/router/server contract, Status UI and item/grade source gates
pass. The cleanup's byte-identical rebuild preserves this accepted behavior.

```powershell
.\.venv\Scripts\python.exe tools\build_auto_ui_language.py --check
node tools\verify_auto_ui_options.cjs
.\.venv\Scripts\python.exe tools\verify_auto_ui_fonts.py
.\.venv\Scripts\python.exe tools\verify_auto_ui_warp.py --source <pristine-2025-07-16-client.exe>
python tools\verify_autosupport_ui_contract.py
.\.venv\Scripts\python.exe tools\verify_status_ui_contract.py
.\.venv\Scripts\python.exe tools\verify_item_grade_color_contract.py --source-only
```

The AutoSupport contract verifier additionally needs Pillow and the adjacent Banquet
source tree. The language/runtime tools use the repository's Python environment.
