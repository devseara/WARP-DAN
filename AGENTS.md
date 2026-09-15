# Accepted Battle Pass and Gacha baseline

The user confirmed both features working perfectly on September 15, 2026.
Preserve the `stable-battlepass-gacha-2026-09-15` tag in this repository and in
`devseara/Ragnarok`. Never move, replace, or delete these restore-point tags.
Read `docs/stable-battlepass-gacha.md` before changes affecting either feature.

- New features must remain separate. BPUI and GCHA share only the framed 0x0BF6
  transport router; never merge their state, handlers, commands or lifecycle.
- Do not alter working rewards, odds, costs, pity, history, mail or reset behavior
  while implementing an unrelated feature. Preserve script configurability.
- Treat AutoCombatUI's shared native helpers, text paths, input/capture, surfaces,
  packet dispatch, patch registrations and build ordering as regression-sensitive.
- Run `python tools/verify_stable_features.py --manifest docs/stable-battlepass-gacha.json`
  before/after unrelated work. Changed protected files require explicit review;
  never refresh hashes just to make a failed guard pass.
- For a new combined client, run the same command with `--client <new.exe>` using
  Python with Pillow, pefile, Capstone and Unicorn. Also test each feature alone
  and both selection orders when shared routing/helpers change.
- Test assets with the existing Node installers. Keep `.qjs` CRLF/UTF-8 without
  BOM and tabs. Build errors may be logged even when WARP returns exit code zero.
- Preserve private plain character-name rendering in Battle Pass and Gacha;
  do not change global actor titles or shared item/grade rendering for this.
- Keep new builds staged until both suites pass and live behavior is accepted.
  Back up the exact installed EXE, verify hashes and check affected processes are
  closed before replacing binaries. Never stop/restart them without direction.
- Database resets, migrations and player-data restoration are separate operations;
  never use the Admin reset as a test. Do not commit credentials, player data,
  game executables, PDBs, personal profiles or local backup directories.
- Respect dirty worktrees. Make a new accepted tag for a deliberate future
  baseline; keep this original restore point intact.
