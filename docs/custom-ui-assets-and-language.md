# Auto UIs and automatic asset export

Target: 2025-07-16 Ragexe. AutoSupport depends on AutoCombat and the Banquet
map server. This is the consolidated Auto UI implementation/acceptance note.

## Language and rendering

`$autoCombatUILanguage` and `$autoSupportUILanguage` independently select
**English** (default) or **Chinese Traditional**. Existing profiles containing
`Chinese Traditional (Big5 / CP950)` remain compatible. The 146 translations cover
266 fixed-string allocations; server names, resource paths and protocol keys
retain their existing encoding contracts. Native Reset/Close labels remain English.

Chinese uses font selector 4 (CHINESEBIG5_CHARSET/MingLiU) for drawing and width
measurement; English uses selector 1. Each UI initializer reads the final native
mapper at `0x00A6F060`: 950 selects Big5, 65001 selects UTF-8, and other overrides
use English. It updates only UI-owned writable buffers when the result changes,
preserving registers, flags, stack and receiver. Bootstrap, draw and tooltip entry
points initialize the text. This supports CustomCodePage applied after the UIs
without changing Windows locale, the client's code-page setting or shared renderers.
Native tooltips retain their existing font selection.

Edit `Inputs/AutoUI/zh-TW.json`; `tools/build_auto_ui_language.py` generates the
single ASCII `zh-TW.bytes.json` runtime catalog with both encodings. Keep both
files: one is editable translation source, the other supplies exact legacy bytes.

## Automatic assets

Selected patches copy assets beside `Warp.TgtExe` during `onApplied`, with no
confirmation or saved copy flag. Test mode skips copying; failures remain errors.

| Patch | Exported files | Destination |
| --- | ---: | --- |
| AutoSupport UI | 134 | `data/texture/<native UI prefix>/autosupport`, `data/texture/effect/roz_autosupport` |
| Item Collection UI | 77 | Native `item_collection` and `uirenewal/menuicon` folders |
| Redesigned Equipment Window | 21 | Native `uirenewal/equipmentui` folder |
| Redesigned Status Window | 18 | Native `uirenewal/statusui` folder |
| Fluent Emoji | 3,148 | `BohEmoji/fluent`, including manifest and licenses |

Target Monster Health Bar already exports its six BMPs. AutoCombat embeds its
controller frames. Other Louis T Steinhil BMP references have no copy prompt;
stock/GRF requirements and the separate Game Settings Lua prompt are unchanged.

## AutoSupport contract

The QJS patch owns native rendering/input, drag payload forwarding, lifecycle and
snapshot decoding. Banquet owns party/master validation, persistence, execution
and snapshots. Selection sends a character ID; the server returns the canonical
party name and never silently substitutes another master.

ASUI uses request `0x0BF8`, snapshot `0x0BEF`, magic `0x49555341`, and messages
Open 1 / Snapshot 2 / SetScalar 3 / Resync 6. The 3,792-byte AHUI layout is reused:
monster rows carry party character IDs/names and single-master selection. Router
version 4 has independent AHUI/ASUI/PINC/COUI handler cells.

Tabs are Basic, Player (up to eleven peers), Skill, Potion, Looting, Move and Item.
AutoSupport has an independent window ID and chains AutoCombat lifecycle hooks.
Its 216x72 AutoHunt/AutoSupport/AutoPotion controller replaces the two-tile group;
peer tiles use AutoCombat state/senders. Native menu routing and dedicated red/blue
controller frames plus `roz_autosupport` STR/texture assets remain unchanged.

Drag/drop resolves inventory indices before registering skills, potions, items
and movement resources. Server-owned delay dialogs map shared slot numbers to
attack/support/healing/recovery/item records. Looting has lowest support priority.
`support_assistant_profiles` stores master name and character ID; ability/item
tables retain category, slot, delay, state, recovery/movement and loot policy.
Existing servers require `sql-files/autosupport/support_assistant.sql`.

## Accepted build and checks

Accepted on 2026-09-11: the user's in-game screenshot shows readable Traditional
Chinese in both visible AutoCombat/AutoSupport pages. Other pages/tooltips and
server interaction cases are outside that screenshot's acceptance.

Full-profile EXE SHA-256:
`dab96a398b3ab1a60d9264af20cdbb2cd0dfe3ab61bb4d16eea2e9004edf5e29`.
The cleanup rebuild matches this hash byte-for-byte.
The local package is `Outputs/auto-ui-utf8-client-cey5abyk/client-and-assets.zip`;
use it with an existing game installation. Build outputs stay outside Git.

```powershell
.\.venv\Scripts\python.exe tools\build_auto_ui_language.py --check
node tools\verify_auto_ui_options.cjs
.\.venv\Scripts\python.exe tools\verify_auto_ui_warp.py --source <pristine-2025-07-16-client.exe>
.\.venv\Scripts\python.exe tools\verify_status_ui_contract.py
.\.venv\Scripts\python.exe tools\verify_item_grade_color_contract.py --source-only
```

The seven-case WARP matrix covers English, stock/950/65001 Chinese, mixed choices
and saved legacy choices. Unicorn checks actual generated code, exact strings,
encoding changes, register/flag/stack preservation, cached calls and writable
buffer bounds. Asset hashes and shared renderer bytes are checked. The older
`verify_autosupport_ui_contract.py` has an unrelated stale menu assertion for
`buildButtonMouseUp(autoSupportRequestVir)` that already fails at HEAD.
