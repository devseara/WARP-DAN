# Dual weapons: daggers, swords and axes — 2026-09-05

Current implementation: [old attack motion, held pixel-edge contacts, anatomical slot mapping and installed bytes](dual-weapon-edge-contacts-20260905.md). The following acceptance records describe earlier builds; they do not accept the current build's live appearance.

The user limited the original dual/off-hand sprite patch to the existing
dagger, one-handed sword and one-handed axe resource families. This supersedes
the [all-type experiment](dual-weapon-all-types-20260905.md). The restricted
EXE is installed; missing mace assets and all-type attack extensions are outside
the current scope.

## Exact scope

| Base class | Weapon | Original dual/off-hand composition |
|---|---|---|
| 1 | Dagger | Eligible |
| 2 | One-handed sword | Eligible |
| 6 | One-handed axe | Eligible |
| Other classes | Including two-handed swords/axes, mace, staff, katar and ranged weapons | Stock behavior |

All nine ordered combinations of classes1/2/6 are eligible, as are off-hand-only
weapons in those three classes. Eligibility still requires valid original
resources and supported source frames. Custom item views remain supported when
the active Lua mapping resolves them to one of these base classes; the patch
does not confuse item IDs, view IDs and base classes.

The owner in `Scripts/Patches/AllowDualCustomWeaponSprites.qjs` rejects excluded
classes before temporary solo loads, suffix lookups, or retained-resource
publication. `CustomDLL/DualWeapon/compositor.c` independently enforces the same
allowlist before any custom draw. This prevents a stale or externally supplied
row from bypassing the requested scope.

Both layers retain the original-resource suffix checks, female Assassin ACT
family check, exact selected-image ownership, native ACT/packet coordinate
conversion and accepted legacy views45/34 path. The coordinate algorithm was
not changed. The existing female Assassin reference scope remains; this update
does not add male/job poses or force native solo80 into dual88.

The previous GM server equipment override remains enabled as separately
authorized. This change restricts the client sprite feature; it does not change
server equipment permissions, rebuild the map server or alter the GRFs.

## Installed executable and payload

Game path:
`D:/Programs/Games/Ragnarok/02_client/Banquet of Heroes/2025-07-16_Ragexe_175220998_clientinfo_patched.exe`.

| Artifact | SHA-256 |
|---|---|
| Installed EXE | `c2e857e3e9d63b510f8b7f31015f821f951aab5033aeb404806acb1751eeeb02` |
| Current `Inputs/DualWeaponRuntime/compositor.dwcp` | `943f4ea74e680db40c10050e02a9d176ea58e6d5b9edef77a7a3f10d62b83ac5` |
| Previous EXE, backed up | `91b1690045634a07dae3b09c52a5564b8ae7895b16e53b1bb9235b2ed6bedeb8` |

[Deployment evidence](evidence/dual-weapon-supported-deployment-20260905.json)
records the closed-client check, atomic replacement, verified installed hash,
verified backup hash, and all four installed hook byte spans. The backup is
`2025-07-16_Ragexe_175220998_clientinfo_patched_before_dagger_sword_axe_91b16900.exe`
in the game directory. The earlier accepted `0bb06dbc...4509` backup also remains.

The [rebuilt EXE](../Outputs/dual_weapon_supported_types/client-dagger-sword-axe.exe)
matches the installed file. Preferred-image virtual addresses for this exact
2025-07-16 profile are:

| Hook VA | Replacement bytes | Target VA |
|---|---|---|
| `00D403A0` | `E9 FB 76 14 01` | `01E87AA0` |
| `00605D41` | `E8 6A 1D 88 01 89 45 94 90` | `01E87AB0` |
| `00C4A0D0` | `E9 FB 68 24 01 90` | `01E909D0` |
| `00C4A647` | `E9 64 63 24 01` | `01E909B0` |

Owner `01E66410` is2,284 bytes; compositor entry `01E7B430`, base `01E7A4F0`,
context `01E87A40`, legacy core `01E66D00`, depth helper `01E87B30`.
State remains `[01E60000,01E65000)`, separate from every code allocation.

## Verification

- [Owner execution](evidence/dual-weapon-supported-owner-20260905.json):596
  cases. Across all529 ordered single-class combinations, exactly9 are admitted
  and520 are rejected. Off-hand-only admits exactly1/2/6. Resource lifetime,
  suffix validation, cleanup, stock restoration and calling convention checks pass.
- [Compositor execution](evidence/dual-weapon-supported-compositor-20260905.json):
  the same9/520 admission boundary,3 admitted off-only classes,17 real compatible
  views in both physical roles,20 rejection guards and observable legacy dispatch.
  Real resource partners use a dagger or axe so they also satisfy the allowlist.
- [Native geometry](evidence/dual-weapon-supported-native-basis-20260905.json):
  576 off-only and672 dagger/dagger cases, zero differences beyond tolerance.
- [Mapped-PE crash regression](evidence/dual-weapon-supported-page-protection-20260905.json):
  eight equipment transitions and19 native calls pass. The archived NX crash
  still reproduces at `01E5F000` with return `01E664A1`.
- [Binary verification](evidence/dual-weapon-supported-binary-20260905.json):
  full owner and payload relocation match; unchanged legacy/depth implementations;
  only four changed mapped hook regions; preserved unrelated patches and overlay;
  valid section/header bounds and isolated writable state pages.

The profile/CRC gate and all4,096 virtual-page alignment residues pass. QJS
remains UTF-8 without BOM and CRLF. These checks establish the scope, code,
resource selection and reference geometry. They do not promote axe or additional
item placement to live-accepted status; the user's prior successful reference
tests remain the visual baseline.
