# Map-server regression after name scoping — 2026-09-11

> Superseded by the [completed scope cleanup and paired release](name-scope-cleanup-20260911.md). Historical findings and hashes below are retained as evidence.

> Follow-up: the screenshot identified a truncated NPC group title. The
> [NPC-title correction](npc-group-title-fix-20260911.md) supersedes this server
> candidate and preserves the crash fix. The original evidence below is retained.

The September 10 server candidate is superseded. Its reduced `unit_data.title`
buffer exposed a missed writer in `status_calc_mob_`. The client candidate is
unchanged by this server correction.

## Confirmed memory corruption

`unit_data.title` was reduced from 128 to 24 bytes, but the mob initialization
path still called `safestrncpy(md->ud.title, md->db->title.c_str(), NAME_LENGTH)`.
The local implementation always zero-pads the entire supplied count. Thus even
an empty title writes 104 bytes beyond the destination.

The compiled Release x64 layout places the title at `unit_data+1057` and the
end of `unit_data` at 1160. The overwrite crosses `group_id`, both vector
representations, movement state and then the enclosing mob's view pointer and
the beginning of its status. This is a concrete corruption mechanism consistent
with disappearing mobs and a subsequent map-server crash. No original crash
dump was available to identify the final faulting instruction.

The fix uses `sizeof(md->ud.title)` at that producer. Script-assigned titles
already use the destination size. A second correction restores
`guild_log_entry.name` to `CHARACTER_NAME_LENGTH`: it identifies the player who
used guild storage, not the storage's label.

`tools/verify_server_name_buffers.py` compiles the actual server headers,
the exact current mob-title copy statement, and the server's `safestrncpy`
implementation. Six current vectors (empty, 1, 23, 24, 127 and 300 bytes)
preserve every adjacent byte. Six negative controls with the old bound corrupt
adjacent state. The test restores vector representations before destruction.
It also asserts 128-byte NPC, mob and guild-storage player-name fields.

The recorded town rejection occurred at 00:17:51 and the first recorded fatal
signal at 00:18:51. The town guard returns false normally; those log messages
do not locate the fatal fault.

## Character select and NPC follow-up

Read-only process-image lookup identified the client opened for inspection
(PID 6616) as the game folder's older
`2025-07-16_Ragexe_175220998_clientinfo_patched.exe`, SHA-256
`e09489696b05ab9497f727443885243582e0645bc5ddca753f6a6ddd303ea2b9`.
All 37 character-footer corrections are absent from that file. It has the
previously documented slot/gender regression. Windows denied memory-reading
access to this elevated process; no live record capture is claimed.

Both the delivered `2025-07-16_Ragexe_name_menu_fixed.exe` and the copy in the
game folder hash to
`2b111715ae643bee75963b2a4b0d152dda8a4d27b8ded4e49f3fc52570f473d5`.
All 37 footer corrections are present. The existing native parser/preview/Game
Start regression passes 120 vectors for this candidate.

The user located the NPC truncation above the NPC. Reproduction with the
correct candidate remains pending; the older process cannot establish that the
new EXE regressed. The server keeps NPC display names at 128 bytes. The existing
NPC discovery test only exercises ring discovery, not final balloon rendering.
The added `verify_npc_name_receiver_pe.py` executes the native 0x0ADF handler
through its cache call: 16 vectors preserve names through 127 bytes and empty
or 23-byte titles. String assignment is stubbed; final rendering is not covered.

## Artifacts

Evidence and corrected server build: `Outputs/server_name_regression_20260911/`.
The previous live servers and game executable were not overwritten or restarted
by this investigation. A source build and memory regression are not live
acceptance of the server/client pair.
