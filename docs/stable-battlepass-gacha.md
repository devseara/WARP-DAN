# Accepted Battle Pass / Gacha restore point

On September 15, 2026, the user confirmed both features working perfectly and
requested preservation before developing other features. The restore-point tag
is **`stable-battlepass-gacha-2026-09-15`** in both repositories:

- [WARP-DAN](https://github.com/devseara/WARP-DAN/tree/stable-battlepass-gacha-2026-09-15)
- [Ragnarok server](https://github.com/devseara/Ragnarok/tree/stable-battlepass-gacha-2026-09-15)

This is Gacha v20/GCHA wire v9 plus the Battle Pass plain-character-name fix.
Server runtime source is commit `7b3e48a2dd4c2bcd618e0661389c59e2757c129e`;
the server tag adds preservation docs/checks without changing gameplay.

## Behavior to preserve

- Independent BPUI/GCHA handlers, state and lifecycle. Only 0x0BF6 framed
  transport is shared; client requests remain 0x0BF9 and 0x0BF8 respectively.
- Battle Pass quests, daily reset, rewards, native opening and plain character
  names in Hunter/My Stats, without altering global actor/item text.
- Configurable Gacha machines, costs, four tiers, rates, pools, pity, mail text,
  Legendary/Epic announcements and isolated per-machine records/reset.
- Sequential item reveal/delivery, x5 = six rolls, x10 = twelve, mail fallback
  for inventory limits, safe right-click descriptions and stable 760x440 UI.
- Twelve-slot pages with data-aware arrows, fitted controls/alignment and up to
  eight Legendary featured items; undeclared featured boxes stay hidden.
- GM99-only confirmed reset. Never reset live records/pity as a regression test.

## Guards and testing

The JSON manifest records accepted binary hashes and normalized source/raw
artwork hashes. GitHub Actions checks protected files and asset installers on
pushes/PRs. It detects changes; it does not prove gameplay compatibility or
configure branch protection. Do not refresh hashes just to silence a failure.

```powershell
python tools/test_stable_feature_guard.py
python tools/verify_stable_features.py --manifest docs/stable-battlepass-gacha.json
# Check installed WARP, including the shared native helper installed by the diff:
python tools/verify_stable_features.py --manifest docs/stable-battlepass-gacha.json --root D:/warp/WARP20250716-main --installed
# Execute all seven native combined-client tests from this package:
uv run --with pillow --with pefile --with capstone --with unicorn python tools/verify_stable_features.py --manifest docs/stable-battlepass-gacha.json --client path/to/staged.exe
```

The suite covers BPUI names, independent routing, the item-click crash, cached
surface shrinking, four-tier layout, eight featured slots and full Gacha flow.
Tests use isolated native boundaries, not live purchases/mail/player resets.
All seven tests passed against the preserved accepted EXE when publishing this
tag. Both asset installers and the client/server source guards also passed.
For shared helper/routing changes, repeat standalone and both-selection-order
builds. Server changes also need current server harnesses and production builds.

The accepted client SHA-256 is
`C6602D9B314D5EE98D2C31F8E0D23696E6EE2627C4510E60D0538101A2DDC1B3`.
The source client is 2025-07-16. No gameplay code changed during preservation.

## Future work and recovery

Keep unrelated features separate. Stage new builds, review protected-file diffs,
run both feature suites and obtain live acceptance before deployment or updating
the baseline. Create a new tag for an accepted successor; never move this tag.

Recover source by cloning both tagged repositories into new directories with
`git clone --branch stable-battlepass-gacha-2026-09-15 <repository-url>`.
Never reset a dirty workspace. The tagged fresh diff reconstructs the accepted
modules on compatible upstream WARP `9a10e8b`.

A private, hash-verified backup is under the author's WARP
`Outputs/stable-battlepass-gacha-20260915/`: matching client/server EXEs, server
PDBs, protected source, personal build profile and runtime feature artwork.
`backup-sha256.json` inventories 143 copies. No executable, private profile,
credentials or player data is published. This is not a database backup.

Before binary rollback, close affected processes, preserve the newer install,
verify backup hashes and restore a compatible matching client/server set.
Review later schema/protocol migrations separately; never automatically restore
an old database or reset player records. No server restart or database change
was performed to create this baseline.

## Installer verification

Fresh install, previous v20 + Battle Pass upgrade, and v15 + v20 + Battle Pass
upgrade passed isolated-index checks and actual application. All produce tree
`0895d2e16c6250fec3d9d16154f32eee5b7f5c5d`.

- Fresh combined diff SHA-256:
  `D947D5C02FABD6CA6C4B8638EBB1E8ACEC1520A77DB322853F1C479E705B04B2`
- `DevSeara-BattlePass-plain-name-upgrade.diff` SHA-256:
  `3C6666B0B5A4C82867464C395A25ECEE9BD345E8B7DD785817A3CE23EB140E4F`

The incremental name fix changes only BattlepassUI.qjs. No Gacha/server/NPC/SQL
installation change is needed for it.
