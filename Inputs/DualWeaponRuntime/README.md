# Dual-weapon baseline — 2026-09-06

Keep this directory together with `Scripts/Patches/AllowDualCustomWeaponSprites.qjs`.
The checked-in `compositor.dwcp` is the normal runtime payload, not the offline
contact-measurement build. WARP loads it directly; recompilation is not needed
to apply the patch.

- Runtime SHA-256: `175162d22f030a730dc69805c6d07894633ef3376d2406ffa184b07a3d7ab016`.
- Installed reference EXE SHA-256: `4e23389333cd873e3f136b48a67aa20f95d648c8a254318b6630b4266858636c`.
- Source: `CustomDLL/DualWeapon/compositor.c` and its three generated headers.
- Scope: 2025-07-16, exact female Assassin Cross body, 17 non-Drake views in
  classes 1/2/6. Old dual-attack motion; held pixel-edge contacts; anatomical
  main/off ownership. Live visual acceptance of this build remains pending.
- Male Assassin family: research only, not enabled.

`compositor.json` records the compiler, relocation layout and exact input
hashes. Git attributes preserve byte-sensitive build inputs. Use
`tools/build_dual_weapon_compositor.py` to rebuild the payload when making a
source change; never install a payload built with `--measure-contacts`.

Focused source/payload checks from the repository root:

```powershell
node tools/verify_dual_weapon_profile.cjs
.\.venv\Scripts\python.exe tools/verify_dual_weapon_owner.py
.\.venv\Scripts\python.exe -m unittest discover -s tools -p test_grf_reader.py
.\.venv\Scripts\python.exe -m unittest discover -s tools -p test_dual_hilt_fit_validate.py
```

The [placement report](../../docs/dual-weapon-edge-contacts-20260905.md) links
the recorded geometry, off-only, binary and page-protection results. The
[male research report](../../docs/dual-weapon-male-assassin-research-20260905.md)
records the next implementation's source/visibility requirements.

Game EXEs, GRFs, rendered previews and intermediate builds under `Outputs/`
are local artifacts and are not committed. Reproducing the asset-dependent
audits requires the original client archives and the historical EXEs/payloads
named by those tools. The checked-in generated headers, canonical authored
inputs and normal DWCP preserve the patching baseline without those previews.
Server deployment notes in this repository describe earlier GM testing; this
baseline does not include or change the separate server checkout.
