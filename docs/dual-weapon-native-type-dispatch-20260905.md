# Native weapon dispatch and animation audit — 2025-07-16 client

This is a read-only binary audit. No hook, client asset, or executable was changed by this audit. The proposed animation wrapper below is not implemented or visually accepted.

Audited EXE: `D:/Programs/Games/Ragnarok/02_client/Banquet of Heroes/2025-07-16_Ragexe_175220998_clientinfo_patched.exe`.

SHA-256: `0bb06dbc84d9e0a5df4fb3002b8946388d00158576ef18be74b3fbff754d4509`.
Architecture: PE32 / i386; preferred image base `0x00400000`. All addresses below are preferred-image virtual addresses, not file offsets. This audit applies to that binary profile only.

## Mace resource selection: dual carrier differs from the retained solo resource

The native code has two distinct paths. Conflating them would produce the wrong fix.

For a dual loadout, `0x00D409E6` resolves the off-hand item with `ItemToWeaponView` (`0x00D8A1D0`). A positive result selects `0x00D409FC`, which calls the legacy item-range pair mapper `0x00D39130`. For the Assassin family, `0x00D40A3B–0x00D40A4C` maps pair results `0`, `7`, and `8` to class `2`. Both resource-name calls at `0x00D40A6A` and `0x00D40A92` then receive `item=-1`: they request the generic class resource. This path is unconditional after the pair mapping; it does not first look for the main weapon's original custom image.

That explains the live mace/knife capture: [dual-weapon-live-mace-20260905.json](evidence/dual-weapon-live-mace-20260905.json) contains native channel 5 `sprite\인간족\어세신\어세신_여_검.spr` / `.act`, and channel 6 `..._검_검광.spr` / `.act`. A generic sword can remain a packet producer for a separate compositor. It cannot be mistaken for the retained original mace resource.

For a **solo load**, the `0x00D40C0D` path instead resolves the actual main item at `0x00D40C18`, then constructs the requested item/view filename at `0x00D40C3B`. The resource existence check is `0x00D40C5A`, followed by `TEST AL,AL; JE 0x00D40CD2` at `0x00D40C5F` / `0x00D40C61`. On success, channel 5 receives the requested ACT at `0x00D40C73` and SPR at `0x00D40CAE`. The job-dependent `0x00D42790` remap occurs only afterward (`0x00D40CBB`) for the remaining class/trail processing; it does not replace those already loaded channel 5 resources.

On requested-ACT absence, the failure branch reaches `0x00D40D6A`, remaps the class with `0x00D42790`, and constructs the generic fallback with `item=-1` at `0x00D40D8E` / `0x00D40DE6`. The Assassin branch `0x00D427FE` remaps mace class `8` and class `7` to sword class `2`. Thus the fallback happens *after* the requested solo ACT failed its existence test.

### Exact filename proof for Mace item 1504

The two native resource wrappers are:

```cpp
// ECX is the database singleton at 0x015FA3C0. Hidden string result is arg1.
String* __thiscall WeaponActName(String* out, int jobIndex, int gender,
                                int weaponView, int itemId, int bodyJob); // D8A010, RET 18h
String* __thiscall WeaponSprName(String* out, int jobIndex, int gender,
                                int weaponView, int itemId, int bodyJob); // D8A160, RET 18h
```

Both forward to `0x00B456C0` (`RET 1Ch`), inserting extension kind `0` for ACT or `1` for SPR. The extension table is verified directly: `[0x01227310]` has bytes `78 15 01 01`, pointing to `0x01011578 = "act"`; `[0x01227314]` has bytes `D8 1E 01 01`, pointing to `0x01011ED8 = "spr"`. Thus `D8A010` constructs ACT names and `D8A160` constructs SPR names. Its argument order is `(out, extensionKind, jobIndex, gender, weaponView, itemId, bodyJob)`.

`0x00B4581C` resolves the native hand family through `0x00D99150`; `0x00B45823/2E` indexes the table at `[0x01602410]`. The live table entry 12 is exactly `어세신\어세신`, including both directory and filename prefix. Gender is obtained through `0x00D815F0` at `0x00B45865`.

When `itemId != -1`, `0x00B45A20` calls `0x00D60DE0`. This routine looks up `itemDB[itemId].view` at `0x00D60E19` and calls Lua **`ReqWeaponNameByClassNum`** (literal at `0x01098C7C`) with that view. The active WeaponNameTable record for Mace view `8` is **`_클럽`**, as recorded in [dual-weapon-type-coverage.json](evidence/dual-weapon-type-coverage.json). It is not `_둔기` and it is not the numeric item suffix `_1504`.

The active text Lua function in `data/luafiles514/lua files/datainfo/weapontable_f.lub` (SHA-256 `acdfc4a3509c1177d9691247e5e8eb9d37faceea66bd19007f04180d941fb79a`) directly returns `WeaponNameTable[classNum]` when non-nil, otherwise an empty string. It does not reject generic values below 30. `GetRealWeaponId` in the same resource returns `Expansion_Weapon_IDs[weaponId]` when present, otherwise the input value.

The filename format literal at `0x01088BF4` is `\%s_%s%s.%s`. `0x00B44190` supplies the `인간족` path component for this family; the normal loader adds the sprite/data root. The resulting client resource keys for this capture are therefore:

- `data/sprite/인간족/어세신/어세신_여_클럽.spr`
- `data/sprite/인간족/어세신/어세신_여_클럽.act`

Both are currently absent according to the complete active-archive coverage report. Correctly authored files at those exact keys would satisfy the native **solo** requested-resource path before mace-to-sword fallback. A native filename hook is not required merely to make the owner's solo capture load these resources. This statement does not establish that another job's ACT coordinates can be copied unchanged: authoring/registration still needs independent evidence. Adding these keys also does not alter the stock **dual** carrier path, which is separate.

For custom weapon views, use their actual Lua-resolved suffix; do not generalize `_클럽` or a numeric item suffix to all views. The existence test precedes SPR loading but checks the requested ACT; deploy SPR and ACT as a matched pair.

## The actual 80 / 88 animation selector

`0x00D72D30` is **not an actor getter**. Its exact recovered ABI is:

```cpp
bool __thiscall UseAlternateWeaponAnimation(
    void* itemDatabase, int job, int gender, int mainWeapon, int offWeapon);
// ECX = 0x015FA3C0; return value in AL; RET 10h.
```

The current unmodified prologue is `55 8B EC 83 EC 08` (six complete bytes). This is a possible future verified trampoline boundary, not permission to transplant the address to another client build.

Its arguments can contain legacy direct view values or actual item IDs. At `0x00D72D47–0x00D72D50`, off < 0, or off == 0 and main < 105, skips item conversion. For positive off on the Assassin family, the function resolves the off view with `0x00D8A1D0`, then calls the separate native pair mapper `0x00D95500` (`RET 8`) before normalizing the resulting view through `0x00D5DDB0` (`GetRealWeaponId`, `RET 4`). Do not replace these arguments with an assumed actor pointer.

The branch at `0x00D72F18` is shared by jobs `12`, `4013`, `4035`, `4059`, `4065`, `4101`, and `4254`. Its table returns true for classes **16, 25, 26, 27, 28, 29, 30** and false for the remaining direct values 0–30. It is therefore an alternate-attack predicate, not exclusively a dual-weapon predicate; class 16 must retain its stock semantics.

The result reaches the body action in independently visible callsites:

- At `0x00C42CDF`, the call result is converted to `EDX = (AL != 0) * 8 + 0x50` by `0x00C42CEE`: false selects base **80**, true selects **88**.
- At `0x00C4780C`, the result chooses literal `0x58` at `0x00C47823` or `0x50` at `0x00C4782F` before the actor animation setter at vtable +`0x1C`.
- The actor attack paths `0x00D422D1` and `0x00D4252E` pass actual item fields +`0x440/+0x444`; the related paths `0x00D41B5E` and `0x00D41CD1` pass +`0x438/+0x43C`. The latter are a distinct field pair and must not be silently equated with current equipment IDs.

Isolated Unicorn execution of the actual `D72D30` and `D95500` bytes confirmed the table for all seven jobs and all direct classes 0–30. Only the database/view boundaries `D8A1D0` and `D5DDB0` were stubbed with the captured/active-table mappings (1238→34→1, 13412→45→2, 1504→8→8). The native predicate returned:

| Main item | Off item | Native AL | Body action base |
|---|---|---:|---:|
| 13412 | 1238 | 1 | 88 |
| 1238 | 13412 | 1 | 88 |
| 1238 | 1238 | 1 | 88 |
| 1504 | 1238 | 0 | 80 |
| 1238 | 1504 | 0 | 80 |
| 1504 | 0 | 0 | 80 |
| 0 | 1504 | 0 | 80 |

This is native control-flow evidence with explicit lookup stubs, not a live attack capture. The final stack pointer was checked for the documented 16-byte argument cleanup. The mace/knife result confirms why a compositor that only accepts 88–95 must fall back for its native attack phase: relabeling phase 80 as phase 88 would mix different body timelines.

## Held generic-sword carrier reconstruction

The current candidate `Outputs/dual_weapon_all_types/compositor.dwcp`, SHA-256 `aee8b54a4a6087c107f5f6d53fe4d1e493eac70ed788bbaab8216bb0657e5728`, reconstructs the accepted pair28 held output from the generic sword channel-5 packet in **288 passing cases**: eight directions, six held frames, two native projection scales, and three actor draw angles. Maximum output geometry difference from the actual legacy core is `0.0001220703125` pixels/degrees. The expected path executes the accepted legacy core using genuine pair28 resources; the actual path uses the generic sword as the owned stock resource and keeps original reference art 13412/1238 unchanged. Both incoming packets execute native `C40C20`.

Run `.venv/Scripts/python.exe -B tools/verify_dual_weapon_sword_carrier.py --client "D:/Programs/Games/Ragnarok/02_client/Banquet of Heroes" --exe "D:/Programs/Games/Ragnarok/02_client/Banquet of Heroes/2025-07-16_Ragexe_175220998_clientinfo_patched.exe" --payload Outputs/dual_weapon_all_types/compositor.dwcp`. The [carrier evidence](evidence/dual-weapon-sword-carrier-20260905.json) contains every actual carrier layer, expected/actual output packet geometry, code hash, and source-resource hashes.

This establishes packet-carrier independence for the specified held phase under an equal explicit native origin/attachment fixture. It does not prove a new mace image's grip registration or live attack behavior. The test requires an explicit payload argument so its report identifies exactly which runtime build was executed.

The parallel actual-asset audit found that generic sword body and trail actions 88–95 each have eight frame records per direction but **no visible image cells**. Consequently, changing the body selector from 80 to 88 alone would not provide the current final-draw compositor with a weapon packet to intercept. A future attack implementation needs both an owned valid carrier for the selected phase and the correct body/source timeline, or an independently verified actor-draw integration. A pair28 carrier must stay separate from the retained original weapon resources.

## Minimum conditions for a future owned animation override

A global `D72D30` detour that returns true solely because both item IDs look like weapons is too broad. The function has no actor argument; an equal job/gender/item tuple can occur on an unregistered actor or an unsupported resource family. A registry lookup by item tuple alone cannot establish ownership.

A narrow callsite-aware wrapper is feasible. The seven direct CALL sites and their proven caller-frame actor locations are:

| CALL / return address | Actor in the original caller frame |
|---|---|
| `C42CDF / C42CE4` | `[caller EBP - 04]` |
| `C4780C / C47811` | `[caller EBP - 10]` |
| `C59082 / C59087` | `[caller EBP - 08]` |
| `D41B5E / D41B63` | `[caller EBP - 14]` |
| `D41CD1 / D41CD6` | `[caller EBP - 14]` |
| `D422D1 / D422D6` | `[caller EBP - 34]` |
| `D4252E / D42533` | `[caller EBP - 34]` |

The caller frame is the incoming EBP **before** the selector's prologue. A future wrapper must preserve that value and the incoming database ECX, then verify the exact return-address profile before reading its corresponding stack local. Unknown callers must execute stock unchanged. A callsite bridge that explicitly passes the actor is an alternative with less hidden stack interpretation, at the cost of several hooks.

The native resource filename starts at byte offset **20 decimal (`0x14`)**, as read by the live inspector; `0x20` is a different address and must not be used for the resource-family identity check.

For either design, first preserve the native result. Permit an override only if the exact actor owns a ready, collision-checked registry row; both current item identities still match the resources retained for that row; job/gender arguments match the actor and the supported family; both original resources have registered source-frame/grip coverage; and the actor's actual loaded body ACT fingerprint has the accepted 88–95 phase. Preserve stock for single-hand loads, missing/unsupported resources, unregistered male/body families, transient item mismatches, and all already-true cases. The owner must publish enough immutable request identity to verify these checks; retained pointers plus a pair class alone are insufficient.

Calling native first preserves the existing pair28 decision and nondual alternate-attack cases. A scoped return override changes animation selection without rewriting actual item fields or changing the native filename resolver. Attack speed/duration also receives this boolean at `0x00D5D0D0`, so the result must be consistent across the covered paths; testing one direct action setter is insufficient. The caller at `0x00C59082` does not visibly consume AL before its next setter, so it must not be treated as an independent proof of action selection.

Until this scope and the body/source frame contract are verified, the general compositor should handle only its explicitly supported current phases (held 32–39 and dual attack 88–95) and preserve native phase-80 rendering. No claim of all-weapon attack acceptance follows from owner classification covering types 1–23.

## Reproducible native selector verification

Run `.venv/Scripts/python.exe -B tools/verify_dual_weapon_native_type_dispatch.py --exe "D:/Programs/Games/Ragnarok/02_client/Banquet of Heroes/2025-07-16_Ragexe_175220998_clientinfo_patched.exe"`. The checked-in [native-dispatch evidence](evidence/dual-weapon-native-type-dispatch-20260905.json) records the exact code-region hashes, verified byte anchors and extension-pointer table, all 434 direct-class cases and 98 item-loadout cases, explicit lookup stubs, and native ABI checks. Its AL-to-80/88 conversion also executes the original caller bytes.

## Byte anchors for reproducible review

| VA | Original bytes | Meaning |
|---|---|---|
| `D409FC` | `E8 2F 87 FF FF` | legacy dual pair mapping |
| `D40A4C` | `BB 02 00 00 00` | Assassin unsupported pair carrier becomes sword |
| `D40A6A` | `E8 A1 95 04 00` | generic dual ACT filename |
| `D40C3B` | `E8 D0 93 04 00` | requested solo ACT filename |
| `D40C5A` | `E8 A1 D8 D4 FF` | requested resource existence check |
| `D40C61` | `74 6F` | absent requested resource → fallback |
| `D40C73` | `E8 48 CB FF FF` | load requested channel-5 ACT |
| `D40CAE` | `E8 DD F0 FF FF` | load requested channel-5 SPR |
| `D40D6A` | `E8 21 1A 00 00` | fallback job-class remap |
| `D40D8E` | `E8 7D 92 04 00` | fallback generic ACT filename |
| `D40DE6` | `E8 75 93 04 00` | fallback generic SPR filename |
| `D72D30` | `55 8B EC 83 EC 08` | alternate-attack selector prologue |
| `C42CDF` | `E8 4C 00 13 00` | call alternate-attack selector |
| `C42CEE` | `8D 14 D5 50 00 00 00` | base = 80 + 8×predicate |
