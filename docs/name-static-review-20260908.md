# Name-static commit review â€” 2026-09-08

Reviewed `ea2e303ff4a9c1675974e3a37407d14b5a241f1a` (canonical 128-byte names), its follow-up `9408fc8efafd46d3baa57aace6e9d2406065199d` (character footer consumers), and their current state at `f41b9d4`.

Scope: all 25 helper adapters installed by `ExtNameTextStatic.patch128ByteNamePackets`, the shared assembler/text/cache/dispatcher activation path, the two commits' tests, and the supplied client and saved crash dump. The matching Banquet `doc/extended-names.md` was consulted for protocol context. This was a source, PE, and native-code emulation review; no game login or live UI acceptance was performed.

## Findings

### P1 â€” Keep name hooks, native layout edits, and their payloads under one reversible lifetime

Representative location: `Scripts/Patches/BattlegroundNamesStatic.qjs:67-69`; payload writer: `Scripts/Patches/ExtNameTextStatic.qjs:131-138`. Introduced throughout the adapters by `ea2e303`.

The adapters allocate and write their trampoline bodies while the feature patch is active, then call `Exe.ActivateGlobal()` before writing native detours, object/field-size edits, and dispatch-table entries. Each of the 25 helpers follows the global-tag pattern. No name-adapter cleanup path removes those tags. `CustomExtName` has no cleanup handler, and the shared refresh callback does not undo the name-packet layer when its owner is no longer selected.

This lets export retain native branches and layout changes while their feature-owned code/data has been removed. The supplied executable already contains this inconsistent result: 248 source-attributed direct name detours point to destinations whose first 16 bytes are all zero. Every corresponding destination contains code in the fresh names-only build. The count excludes indirect dispatch entries and unenumerated sites, so it is not a count of every damaged reference.

Concrete startup failure:

- `0x00B3A0E9`: original `6A 3C E8 BE 1D 28 00`; supplied EXE redirects to `0x019EC610`.
- `0x019EC610`: zero-filled bytes instead of the 316-byte BG manager allocation trampoline.
- Saved PID 19028 dump: EIP `0x019EDF9B`, exception `0xC0000005`, read address `0x001A0018`; caller frame returns to `0x00DB7A31` after the native BG manager initialization call.
- A fresh export of the user's current recommended-base profile restores stock bytes at all 248 affected branch sites.

The exported inconsistency and crash path are confirmed. Deselect/revert/failure is the source-supported lifecycle explanation; the exact original GUI sequence was not replayed. Re-enabling also requires attention: fresh installer state encounters surviving global edits at exact-stock-byte guards, while stale per-module installed flags can skip reinstallation. These are consequences of the same ownership defect, not separate findings.

Recommended correction: give code, data, hooks, native structure edits, and dispatcher changes one coherent owner or explicitly reference-counted lifetime. Undo the complete 128-byte protocol layer on last-user removal and roll back the entire installation on failure. Invalidating CACHE alone or restoring only the BG jump is insufficient. Exercise enable/export, disable/export, re-enable/export, a failed mid-install, and both orders with other shared text features.

### P2 â€” Include the footer and character-rename regressions in the maintained gate

Location: `tools/verify_all_name_packets.py:11-18`. The runner was introduced in `ea2e303`; `9408fc8` added the footer test without adding it to that runner.

The advertised aggregate omits `verify_extname_character_rename_pe.py` and `verify_character_select_footer_pe.py`. These tests execute distinct native consumers that its existing creation/parser tests do not cover. The original commit's missed character footer is a concrete example: correct 279-byte parsing did not ensure that preview slot, sex, stats, map, and Game Start readers used the new offsets.

The social suites are transitively included through `verify_extname_social_reuse_pe.py`; they are not missing merely because their filenames are absent from the top-level list.

Add the two omitted checks with their required arguments and before-image fixture. The runner also needs an explicit profile requirement for `AlwaysShowNpcName` or a conditional NPC-overlay check: its NPC test fails on a valid names-only build because the separate overlay is absent. That setup failure was resolved in this review by building the required combination; it is not evidence of a runtime NPC regression.

## Historical regression already fixed

`ea2e303` widened `CHARACTER_INFO` from 175 to 279 bytes but missed 37 preview/footer/copy consumers. `9408fc8` supplies those edits. The current fresh build passes the dedicated test: 120 native parser/preview/Game Start vectors, full native record refresh, and the old-code fixtures reproduce the slot/gender/stat corruption. Do not report this as an unfixed current bug.

## Coverage and results

| Adapters / surface | Review and execution evidence |
|---|---|
| CharacterNames, CharacterCreateNames, CharacterOldCreateNames | Native page/create/delete, capacity, input/callback/Enter, footer and Game Start checks pass |
| CharacterRenameNames | Dedicated native rename callback, request, ACK, rejection, cancellation, padding and EH checks pass |
| ExtNameParty, ModernPartyNames | Full member/list records, native strings, queued name ownership after packet reuse, sized destruction and unwind checks pass |
| GuildNames, ClanNames, GuildPositionNames | Scalars, roster/position strides, native lists/strings, clan fields, 20-position outgoing packet checks pass |
| FriendNames, SocialNames, OutgoingSocialNames | Full names, invitation/result routes, input boundaries and repeated long-to-short packet padding checks pass |
| WhisperNames, WhisperBlockNames | Sender/recipient fields, message, block/allow requests, ignore list and native input limits pass |
| BookingNames, ChatRoomNames | Native formatter carriers, malformed record rejection, room membership/ownership and trade consumers pass |
| CompanionNames, CompanionRenameNames | Pet/hom/merc fields and name storage, rename writers, bounds and confirmation checks pass |
| MailNames | Native mail parse/request/send, name and title fields, malformed record and padding checks pass |
| QuestNames | Per-record allocations, clone/move/assignment/destruction and widened parser/reader checks pass |
| GuildStorageLogNames | Widened wire/native rows, copy/move/growth, timestamp sorting, string ownership and cleanup checks pass |
| StarNames, BossTrackerNames, AuxiliaryIdentityNames | Native target/notification, canonical identity, footer and bounded dispatch checks pass |
| Shared EXTN/name text | Cache layout/copies and legacy/current packet parsing checks pass |
| AlwaysShowNpcName changes | All six supported packet-length variants and malformed-record checks pass when the overlay is selected |
| Native packet reader | Disassembly confirms `0x00C16570` checks available bytes against the enlarged requested length before copying/advancing; no partial-read defect was found here |

The unmodified aggregate returned 16/17 passes on the names-only EXE. Its sole failure was the missing optional NPC-overlay signature. That check passed separately on the names-plus-NPC build. Dedicated rename and footer checks also passed. These results establish the exercised machine-code paths, not complete in-game rendering or patch-toggle acceptance.

## Artifacts

- Supplied EXE SHA-256: `0419b5e6545aa090c91f533bf0949526a6e72a312daefea8fccd4cb97cbc4541`.
- Fresh names-only EXE SHA-256: `85d802e789d5ebe36b2a04e5a228f1bb6b5f120c1d4a10194993370134b20978`.
- Fresh original source SHA-256: `ead7c0a316bc6c27705a5a6876daf5093abec31677f3c1af7525c1709b201bff`.
- `tmp/name-static-review-20260908/zeroed-name-detours.json`: all 248 attributed zero-target detours and comparison addresses.
- `tmp/name-static-review-20260908/suite/summary.json` and individual logs: unmodified aggregate results.
- `tmp/name-static-review-20260908/footer-execution.json`: 120 footer vectors and old-code regression evidence.
- `tmp/name-static-review-20260908/verify_extname_character_rename_pe.py.log`: dedicated rename results.
- `tmp/name-static-review-20260908/names-clean.yml`, `names-npc.yml`, and build logs: isolated fresh builds.
- `tmp/name-static-review-20260908/recommended-clean-build.log`: fresh current-profile export; all 248 affected sites match stock.

No production QJS, profile, or deployed client was changed. The console builds updated WARP's last-output setting transiently; its pre-review target value was restored. The pre-existing Settings/profile edits were preserved. Diagnostic builds and dependencies remain under the review's tmp directory. No commit or deployment was made.

## Implementation follow-up

The lifecycle fixes, real WARP regression, full QJS headers, JuanD RO scope and validation results are recorded in [name-static-lifecycle.md](name-static-lifecycle.md). The original findings above are preserved as review history.
