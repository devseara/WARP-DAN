# Mounted sprite upstream import — 2026-10-19

Imports `YlenXWalker/WARP20250716-main` commit
`10a9ca4f913f1cc016caafb4b91406e75d57b3e0` into WARP-DAN.

The user approved retaining the current enabled profile. Its bytes are unchanged:
`AllowAllRidingCombat`, `MountedMageAttachments`, `UniformSpriteRHW`, and
`FloorSafeSpriteDepth` remain unselected. The two new patches are registered as
392 and 393 for future selection. The overlapping sprite-depth documentation uses
the updated upstream explanation. Existing weather draw ownership checks remain.

No client executable, game artwork, player data, NPC configuration, or server
setting was deployed by this import. The earlier local skill-critical alignment
edits remain separate and are not part of this commit.

## Local validation

Evidence is retained locally in `Outputs/upstream-mounted-20261019/`:

- QJS banner, CRLF, encoding, and indentation checks passed for all three patches
  and the Mage template. Generated Mage source matches its template/specifications.
- Imported Python sources parse. The existing GrayMap builder retains the same
  syntax tree except for accepting an absent overlay as empty bytes.
- Real WARP All_Riding exports passed, including rejection before writes for a
  mismatched gate and idempotent reopening. Native input gates, packet production,
  and action mapping checks passed; only the four intended gate bytes changed.
- Real WARP FloorSafeSpriteDepth exports passed. Living behavior passed 66 body
  and three shadow cases. The corpse fix passed 24 cases and 17 unchanged controls
  against the previous local patch.
- The isolated Mage builder preserved all other mapped section bytes. Every
  emitted bridge matches the generated specifications. Native execution passed
  24 death-dispatch cases, five mount/repeated-notification transitions, five actor
  controls, and ten unchanged shield refreshes. Resource loading is stubbed at
  documented boundaries; artwork was not tested.
- All 57 protected file hashes match their pre-import values. The accepted-feature
  guard reports the same pre-existing BattlepassUI/GachaUI baseline differences.
  Neither protected file nor accepted manifest was changed by this import.
- The main profile and installed Eitr executable match their recorded hashes.

The local base executable has SHA-256
`73349f3606de8e9535d91b73e0177813c38369f06795f5a91200715a177f1a9f`.
It differs from the exact upstream base required by the Mage QJS allocation gate.
Real WARP correctly rejects that input; positive Mage execution was validated
through the isolated-section builder. A successful Mage QJS export from its exact
upstream base and live rendering with matching artwork were not tested locally.
The imported `docs/evidence/` reports describe upstream testing, not deployment
or visual acceptance on this installation.
