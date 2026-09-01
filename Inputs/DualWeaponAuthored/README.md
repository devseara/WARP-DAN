# Dual-weapon authored source closure

This directory is the clean, non-ignored authority for authored dual-weapon
data. Generated pixel matches, native-guide estimates, rejected DWR3/DWC2
tables, and temporary EXEs are not accepted inputs.

## Accepted content

- `poses/female-assassin-pair28.csv`: 224 live-accepted pair28 records
  (96 held and 128 attack, including 16 intentional hidden terminal cells).
- `grips/female-assassin-views34-45.csv`: the 48 accepted/identity grip keys
  for Zeny Knife view 34 and Naght Sieger view 45.
- `accepted-act/female-assassin-pair28-attack-body-guide.act` and `.spr`: the
  only recovered user-edited Act Editor pair. Their hashes are pinned in
  `manifest.json`.

## Missing content

- The user-edited pair28 held authoring ACT was not recovered.
- No non-pair28 pose or per-view hilt/grip ACT has been authored and imported.
- Existing files formerly under `tmp/recovered_dual/ActEditorWork` were
  generated starting points and are not accepted.

## Build policy

The replacement implementation must consume only versioned records from this
directory. Every record carries an explicit acceptance state. A build may
enable a pair/view cell only when both physical hands have complete held and
attack pose/grip coverage. Missing cells remain entirely stock.

The final patch should be a small readable QJS loader plus a deterministic
binary payload generated from readable C/CSV/JSON. Do not reintroduce giant
inline hex constants or use documentation CSVs as implicit build inputs.
