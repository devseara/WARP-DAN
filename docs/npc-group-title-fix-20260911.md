# NPC group-title truncation — 2026-09-11

> Superseded by the [completed scope cleanup and paired release](name-scope-cleanup-20260911.md). Historical findings and hashes below are retained as evidence.

The screenshot's Dietrich title is set by `npc/merchants/refine.txt:1268` to
`<Responsible for smelting products>` (35 encoded bytes). The earlier scope
change limited `unit_data.title` and `setunittitle` to 24 bytes including NUL,
producing the 23-byte prefix `<Responsible for smelti`. This truncation happens
on the server before the client receives the title.

## Correction

- `NPC_TITLE_LENGTH` is 128 bytes including NUL, independently of `NAME_LENGTH`.
- The shared `unit_data.title` buffer accommodates that maximum. The script
  setter selects its bound by entity type: NPCs accept 127 content bytes;
  players, mobs and companions retain the 23-byte default.
- Mob database titles retain their 23-byte content cap. Mob initialization
  retains the destination-sized copy from the preceding crash fix.
- Group labels, guild positions, clan/BG identifiers, service tokens and script
  labels retain their existing scoped limits.

Both `0x0ADF` and EXTN already carry 128-byte title fields, so packet sizes,
client patch code and the client EXE remain unchanged. Rebuilding the server
is required because the internal unit layout changes. Restart the corrected
map-server to reload NPC OnInit titles; script reload alone cannot enlarge the
old executable's buffer.

## Verification

`tools/verify_server_name_buffers.py` compiles actual server headers and copy
expressions. All 72 cases pass: NPC/non-NPC script assignment, mob database
loading, both title packet fields, boundary and over-limit strings, adjacent
memory preservation, and the historical overflow negative control. The exact
smelter title is included.

`tools/verify_npc_name_receiver_pe.py` executes the existing client's native
NPC ACK handler through its cache call. All 32 vectors pass with empty,
23-byte, exact 35-byte smelter and 127-byte titles. String assignment is stubbed;
this is receiver validation, not a live pixel comparison.

The effective packet-table/compiled-layout gate also covers the unchanged
Gold PC, BG, party-expel and macro-report contracts.

Build and evidence: `Outputs/npc_group_title_20260911/`. The previous running
servers are not replaced or restarted by this build. The existing
`2025-07-16_Ragexe_name_menu_fixed.exe` remains the paired client, SHA-256
`2b111715ae643bee75963b2a4b0d152dda8a4d27b8ded4e49f3fc52570f473d5`.

The earlier crash investigation and its original-layout evidence are retained
in [the server regression report](map-server-name-scope-regression-20260911.md).
The new NPC-title build supersedes its server binary while preserving its fixes.
