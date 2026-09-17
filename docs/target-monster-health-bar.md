# Target monster HUD

`TargetMonsterHealthBar` (patch ID 382) supports **2025-07-16 Ragexe** and is selected in `profiles/2025-07-16 PROFILE MAIN.yml`.

## Design selection

When applying **Tiered Monster Target Health Bar**, WARP asks for **Monster HP Bar Design**:

- **Classic** (default): the existing red ornamental bars.
- **Wings and Stars**: the supplied second design, with green Normal, gold Mini Boss and red MVP bars.

The choice covers all three monster tiers and is saved as `$targetMonsterHUDDesign`. Existing profiles without this input default to Classic. To select the second design in a console profile, add this entry under `inputs:`:

```yaml
    $targetMonsterHUDDesign:
        data: '57696e677320616e6420537461727300'
        display: 'Wings and Stars'
        type: 10
```

WARP embeds the selected skin's resource keys and fill/text coordinates, then copies its six BMPs beside the output EXE. Classic retains its existing resource keys; Wings and Stars uses the `mobhpbar/wings-and-stars/` subfolder. Both skins can coexist in the same client data folder or GRF. Changing designs requires repatching the client.

When moving the patched EXE to another game folder, also copy the generated skin directory under `data/texture/.../uirenewal/mobhpbar/`, preserving its subfolder structure. Moving only the EXE leaves Wings and Stars without its six resources and the HUD stays hidden. After adding missing assets, fully restart the client: failed loads are cached for the process lifetime.

## Behavior

`/monsterhp` controls the complete presentation:

- **On:** hover a living monster to show its name, HP, details and original group icon in the custom HUD. Otherwise, an active attack/targeted-skill target is used. Native nameplate text, group icons and fallback boss badges are suppressed.
- **Off:** hide the custom HUD and restore the stock name, info and icon beneath monsters. The current hovered monster is refreshed immediately.
- Hover remains available while the player is dead. Death disables stale attack-target fallback. Dead target monsters and known zero monster HP remain excluded.
- NPC, player, pet and item labels are unaffected. If the HUD BMPs cannot load, native nameplate fields remain intact.

The layout is:

```text
NORMAL / MINI BOSS / MVP
Monster name
HP bar: current/max HP ♦ percentage
Mob Level: value ♦ Mob ID: value
Mob Element: name Level: value ♦ original group icon
Mob Race: name
```

HP quantities use commas through billions, including `3,000,000,000/4,000,000,000 ♦ 75%`. **Mob IDs never use commas.** Show Mob Info controls all optional text: bit 1 enables current/max HP, bit 2 enables HP%, and the remaining bits select detail rows. With `@showmobinfo 0`, the tier, monster name and live bar remain, with no numeric HP, percentage or detail rows. HP comes from the native monster-HP channel regardless of these text preferences.

Names use the native 14px font; other text uses the native 12px font. Classic artwork stays at its accepted 50% source scale; Wings and Stars uses the supplied 768x232 canvases without resizing. The 768x232 transparent window is top-centered at Y=24; extra height provides 24px detail-row spacing beneath the MVP crest. The native group icon retains its own dimensions. Divider ends use true alpha fading.

## Assets and resource loading

Classic uses these six assets:

```text
data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º/uirenewal/mobhpbar/
    target_mob_normal_empty.bmp
    target_mob_normal_full.bmp
    target_mob_mini_empty.bmp
    target_mob_mini_full.bmp
    target_mob_mvp_empty.bmp
    target_mob_mvp_full.bmp
```

Wings and Stars uses the same six filenames under `mobhpbar/wings-and-stars/`. `Assets/TargetMonsterHUD/designs.json` lists both manifests: `assets.json` and `assets-wings-and-stars.json`. Resource keys, copy hooks, code generation, tests and packaging derive from those manifests. The verifier and packager identify the selected design from all six resource keys embedded in the EXE.

HUD reads use native **CFile → CFileMgr**. They follow the selected DATA.INI loader or embedded GRF list and normal loose-folder/GRF priority. Profile Main uses `GRFsEmbedded` with `Inputs/Sample_DATA.INI`; embedded mode does not additionally parse external DATA.INI. For GRF distribution, store the BMPs under the exact same `data/texture/...` keys in a configured archive. Existing group-icon resources are reused without replacement. Restart the client after changing cached BMPs.

BMP format: 32-bit `BITMAPV4HEADER`, one plane, `BI_BITFIELDS=3`, 122-byte pixel offset, bottom-up straight BGRA. Masks are `00FF0000`, `0000FF00`, `000000FF`, `FF000000`. Loading validates file size, dimensions, format and masks. Alpha-zero pixels are skipped; partial alpha survives bitmap and native text/icon drawing.

`Assets/TargetMonsterHUD/three-tier-concept.png` is the accepted extraction source. Its SHA-256 is recorded in the Classic manifest. The generator preserves the original texture scale, repairs baked percentage text, and separates the divider opacity from the reference background.

The second skin was supplied as six V5 BMPs in `33232`. Its checked-in resources have V4 headers for the existing strict loader. Only the headers changed: every BGRA pixel byte remains identical to the supplied files. Source and normalized-file SHA-256 hashes are recorded in `assets-wings-and-stars.json`. Its wider fill bounds and HP-text positions are independent of Classic. The existing artwork extractor regenerates Classic only.

## Build, verify and package

Run from the repository root on Windows. Keep the original client at:

```text
2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe
```

Profile Main contains local source paths; adjust its `from` path if your checkout differs. Original client binaries, generated EXEs and packages are not committed.

Create the isolated dependency environment once:

```powershell
python -m venv .venv-target-hud
.\.venv-target-hud\Scripts\python.exe -m pip install -r tools/requirements-target-monster-hud.txt
```

Generate the QJS and build Profile Main:

```powershell
.\.venv-target-hud\Scripts\python.exe tools/build_target_monster_health_bar.py
New-Item -ItemType Directory -Force Outputs/TargetMonsterHUD | Out-Null
.\win32\WARP_console.exe -using "profiles/2025-07-16 PROFILE MAIN.yml" -to "Outputs/TargetMonsterHUD/2025-07-16_Ragexe_monster_hud.exe"
.\.venv-target-hud\Scripts\python.exe tools/fix_custom_bridge_iats.py "Outputs/TargetMonsterHUD/2025-07-16_Ragexe_monster_hud.exe" --dll cps.dll --write
.\.venv-target-hud\Scripts\python.exe tools/verify_target_monster_health_bar.py "Outputs/TargetMonsterHUD/2025-07-16_Ragexe_monster_hud.exe" --report Outputs/TargetMonsterHUD/verification.json
.\.venv-target-hud\Scripts\python.exe tools/package_target_monster_hud.py "Outputs/TargetMonsterHUD/2025-07-16_Ragexe_monster_hud.exe" --verification Outputs/TargetMonsterHUD/verification.json
```

The package is `Outputs/TargetMonsterHUD.zip`; it contains the EXE, the selected design's six BMPs, this guide and a hash manifest. The verifier receipt records the design and all six asset hashes; packaging rejects mismatched or subsequently changed assets. Extract into the existing game folder and use the normal launcher/login arguments.

For a faster isolated check, create a profile with the source `from:` path above, your own `to:` output path, the desired design input, and just `TargetMonsterHealthBar` under `patches:`. Build it with `WARP_console.exe -using <profile.yml>` and pass its EXE explicitly to the verifier. Repeat for both choices. Only regenerate the BMPs after changing their extraction logic:

```powershell
.\.venv-target-hud\Scripts\python.exe tools/build_target_monster_hud_assets.py
```

Maintain the readable Python/x86 modules listed below, then regenerate the QJS. Its byte chunks and relocation operands are build output, formatted in bounded lines for review; do not hand-edit those tables. The generator also owns the patch header so regeneration preserves attribution. GitHub marks this QJS as generated through `.gitattributes`; review behavior changes in the generator/helper modules and expand the generated diff when needed.

Before committing, check that the checked-in QJS is reproducible without rewriting it:

```powershell
.\.venv-target-hud\Scripts\python.exe tools/build_target_monster_health_bar.py --check
```

For a generator-formatting change, require the rebuilt client to remain byte-for-byte identical to its verified baseline. Changes to x86 behavior still require the regression and live acceptance checks below. The profiled native addresses remain specific to this client build; supporting another executable requires new signatures and ABI verification.

The selectable QJS is self-contained at patch time. Python is needed only for generation, verification and packaging. QJS remains UTF-8 without BOM, CRLF and tab-indented. Generated machine-code chunks must not overlap; relocation operands are calculated from the emitted bytes rather than staged WARP reads.

## Source and native contracts

| File | Responsibility |
| --- | --- |
| `tools/build_target_monster_health_bar.py` | Static x86 hooks and generated QJS |
| `tools/target_monster_hud_layout.py` | Shared fixed data layout |
| `tools/target_monster_hud_designs.py` | Design catalog and embedded resource-key identification |
| `tools/target_monster_hud_showmobinfo.py` | Independent EXTN reader for optional names/details |
| `tools/target_monster_hud_native_hp.py` | Native 0x0977 HP mirror and independent cache |
| `tools/target_monster_hud_metadata.py` | Typed fields, names and row formatting |
| `tools/target_monster_hud_presentation.py` | Commas, group icons and option refresh |
| `tools/target_monster_hud_text.py` | Native font calls and bounded alpha repair |
| `tools/build_target_monster_hud_assets.py` | Reproducible artwork extraction |
| `tools/verify_target_monster_health_bar.py` | Emitted-code regression checks |
| `tools/package_target_monster_hud.py` | Verified package and resource-key checks |

The HUD independently drains the existing `0x0BB7` EXTN ring for names and optional detail labels: 1024 slots of 1024 bytes, at most 64 packets per frame, bounded overrun recovery. It does not consume another reader's cursor. Current 653/657-byte packets and the existing bounded 773/777- and 233/237-byte layouts are supported. Only entity type 1 is considered. EXTN HP and percentage tokens select their respective text visibility flags only; their numeric values never populate or overwrite the HP cache.

The label parser recognizes `#ID`, `Lv.level`, element `Lv.1..4` and race tokens. It separates element Undead from race Undead. Overflow, invalid levels and partial numeric tokens are rejected. The native HP cache and label cache have independent 512-entry storage and reset with the world. Row formatting updates on target/packet revision changes. Native `-1` HP sentinels remain special; authoritative native HP packets may use the complete unsigned 32-bit range. Grouped numeric buffers are bounded, with a dedicated 64-byte HP label.

| Address or field | Contract |
| --- | --- |
| `C76591` | Observe the native hit-test result in EDI after A797B0; preserve A47B90's original call, argument, return value and ret-4 cleanup |
| `10904B8`, GameMode+CC, World+2C | Game-mode, world and local actor guards |
| Actor+314 / +304 / +300 | Monster wire type 5 / Normal-Mini-MVP tier / native HP gauge |
| `A69EB0`, `5A1460` | Native actor and original name-info lookup |
| `C6D308` | Preserve D8E9D0; clear only producer-owned name/title strings and local group ID when relocating |
| `C6D355` | Preserve C43230; suppress only the local fallback badge argument when relocating |
| EBP-1D8 / -160 / -148 / -1E4 | Local name string / title string / group ID / tier byte in the profiled nameplate producer |
| `68EA70` option D5, `C6D1D0` | `/monsterhp` state and immediate native balloon refresh |
| `8361B0`, `83BD30`, `863F10` | Native gauge constructor, destructor and HP setter |
| `A21C90`, `A25A70` | Native text width/drawing, font selector 1 |
| `1090EC8`, `A90350`, `A8E500`, `A9F030`, `A8D4A0`, `A1D260` | Original group bitmap format, lookup and drawing |

Global name records and packets are never edited. Native string assignment operates only on the producer's private copies. Group bitmaps are manager-owned and reacquired for each redraw. Native vtable slots and RTTI are preserved except the custom HUD draw/destructor entries. No shared TextOut, item/grade renderer, recv hook or runtime executable modification is added. The server integration below supplies independent native HP.

## Validation and release state

Regression checks execute emitted x86 with native-call fixtures, actual HUD BMPs and packet inputs. They cover target selection, stale attack rejection after death, hover while dead, both `/monsterhp` states, private-string ownership, group/badge restoration, optional fields, large HP, ungrouped IDs, missing resources, alpha preservation and calling conventions.

Classic's accepted interactive baseline is v12. The design chooser preserves Classic's emitted code/data payload and relocation positions exactly. Both selectable designs pass isolated WARP builds and emitted-x86 checks, including empty/partial/full/clamped fill bounds and exact asset copying. Wings and Stars still requires live in-game visual acceptance; emulated rendering is not that acceptance.

For Classic, earlier live captures confirmed all tiers, original icons, changing HP, divider alpha and both presentation modes. The dead-player failure was isolated with a valid native monster hit while player state was 3, then corrected and covered by emitted-code tests. Cleanup removes the diagnostic preview, file logger and frame snapshots; the three rendered verification surfaces and all six BMPs match the accepted baseline exactly.

This feature has no runtime trace file or diagnostic slash command. When changing rendering or native hooks later, repeat the emitted-code checks and live acceptance for Normal, Mini Boss and MVP, both toggle states, target switching, player death/revival, map change and clean exit.

## Independent HP server integration

The ordinary 0x0977 `ZC_HP_INFO` packet contains a 32-bit monster GID, current
HP and max HP. The profiled call at CA8AA2 is mirrored after the native packet
reader has consumed the full 14-byte packet. The original handler remains the
continuation, except that a full-HP seed does not create a new world gauge for
an otherwise untouched monster. Existing world gauges still receive stock
healing/full-HP updates. The custom cache accepts the full unsigned range and
survives the first frame after early visibility packets arrive.

HP does not come from @showmobinfo. Its 0x0BB7 packets affect only names and the
optional HP/HP% text and level/ID/element/race rows. Changing @showmobinfo between 0 and 63 cannot
clear or replace native HP. /monsterhp remains the presentation toggle.

The paired BanquetOfHeroes changes are in src/map/clif.cpp and src/map/mob.cpp:

- Send native HP when a monster becomes visible/spawns and in validated hover
  name replies, including full-health monsters.
- Send damage/healing HP to nearby active viewers independently of the label
  preference. Retain summon-specific updates and avoid duplicate attacker sends.
- Keep monster_hp_bars_info and MF_HIDEMOBHPBAR restrictions, and reject inactive
  sessions before writing the native packet.

Rebuild/restart the map-server to activate these source changes. No new wire
packet or client HP query is added. Without the server integration, native
attack HP still works when supplied, but untouched HP may remain unknown.

The package includes `server-native-hp.patch`. Apply it in the paired server
checkout (`git apply --check` first), rebuild `src/map/map-server.vcxproj` in
Release/x64 with the server root as SolutionDir, then restart the map-server.
The live local server has already been rebuilt with this integration. Client
builds made from the current QJS install the 0x0977 mirror automatically.
