# GM weapon-slot testing — deployed 2026-09-05

The approved server patch is installed and the map server has restarted successfully. It permits a player with `PC_PERM_USE_ALL_EQUIPMENT` to place any real weapon whose database equipment mask includes a hand in either individual hand, including a weapon normally occupying both hands. The current configuration grants that permission to Admin group 99.

Server directory: `D:/Programs/Games/Ragnarok/01_github/BanquetOfHeroes`.

## Permission and source behavior

`conf/import/groups.yml` contains this override:

```yaml
Body:
  - Id: 99
    Permissions:
      all_equipment: true
```

`all_equipment` already bypasses the stock item eligibility checks in `pc_isequip` (`src/map/pc.cpp:2295`). Configuration alone does not generalize weapon slots. The deployed patch adds two permission-gated guards:

1. `pc_equippoint_sub`, `src/map/pc.cpp:1909`: return `EQP_ARMS` for `IT_WEAPON` records with any hand bit in their database mask when the actor has `PC_PERM_USE_ALL_EQUIPMENT`.
2. `pc_equipitem`, `src/map/pc.cpp:12933`: apply the existing requested-hand/default-hand selection to these permitted weapons. This converts normally two-handed weapons into one selected hand instead of reserving both slots.

The guards use the permission, not a hardcoded group number. Granting `all_equipment` to another group in future also grants this weapon-slot behavior. No additional group was granted the permission by this deployment. Normal players, armor, ammunition, shadow equipment, and weapon records with no hand equipment bit keep their prior slot behavior.

`all_permission: true` is unnecessary: the parser in `src/map/pc_groups.cpp:151` enables the entire permission bitset for that setting. This change did not enable it. A group configuration edit can be loaded with `@reloadatcommand`; activating the C++ slot changes required the completed map-server restart.

## Build and activation evidence

The [reviewed patch](../Outputs/gm_all_weapons_20260905/gm-all-weapons.patch) changes only the two guards above. Its candidate rebuilt staged `pc.cpp` with the server's recorded Release/x64 compiler flags, then linked it with the unchanged existing Release objects and libraries. No database records were edited.

| Artifact | SHA-256 |
| --- | --- |
| Installed `map-server.exe` | `21d80fc5186130ec1b65efc8cc37e347c8eb8f8dbfb161e177994224c74d479e` |
| Installed `src/map/pc.cpp` | `eb9fc3b8a0cc8bc3efbd3dc2290b713fcde4c18103f66465a0bc8b042b0d4852` |
| Previous executable, preserved backup | `2ca1a116b6f913fc67da1ed474ef4cdefdfc9d9c17497d285f600e67636cf622` |
| Previous source, preserved backup | `ff0b9e3ffc1aecfb46d37279e63459645052b71a55ce1abf629108dee972502e` |

The [compiled equipment matrix](../Outputs/gm_all_weapons_20260905/equipment_matrix.json) passed **188,786 checks**: 94,393 each in Renewal and classic modes. It compiles the actual baseline and candidate equipment-point function and requested-slot branch, covering 23 weapon subtypes, hand and non-hand masks, both permission states, job/skill eligibility variants, requested hand, and existing hand occupancy. It is a slot-selection test; it does not emulate network inventory interaction or client rendering.

The [deployment evidence](evidence/gm-all-weapons-deployment-20260905.json) records:

- Before resuming, the approved source was already installed but the executable was still the old binary.
- Old map PID `17304` had an isolated console containing only its parent `cmd.exe` and the deployment helper. Login and char servers were explicitly excluded before sending one `CTRL_C_EVENT`.
- The native signal shutdown path ran and the old process exited with code `0`; there was no forced termination.
- The new map process started at **2026-09-05 15:19:06 +08:00**, PID `10068`, with a hidden console.
- TCP port `5121` is listening, the map process connected to char server port `6121`, and startup reported `Map Server is now online.`
- Login PID `15648` and char PID `2060` remained running. Startup contained no error/fatal messages; its only warning was the existing administrative-privileges warning.

Backups and build artifacts are in `Outputs/gm_all_weapons_20260905/`. `deployment-before-map-server.exe` and `deployment-before-pc.cpp` preserve the previous server content. The [deployment helper](../tools/deploy_approved_gm_weapon_server.py) verifies exact hashes and console isolation and has no force-kill path.

## Acceptance boundary

Server activation and a newly permitted off-hand mace equip are verified. After reconnecting, the user equipped mace1504/main with knife1238/off, then swapped them. Read-only client captures record `[1504,1238]` and `[1238,1504]` in actor fields +0x440/+0x444: [main mace](evidence/dual-weapon-live-mace-after-server-20260905.json), [off mace](evidence/dual-weapon-live-off-mace-after-server-20260905.json). These captures verify the actual item slots; original mace artwork and placement remain separate client work. This permission and slot patch does not supply missing weapon SPR/ACT assets, choose grip coordinates, or prove all weapon families render correctly. The dual-weapon compositor work must verify those independently.
