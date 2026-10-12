# Riftlock Anti-Cheat Replacement Plan (Gepard Shield 3.0 → Riftlock)

Status: ACTIVE IMPLEMENTATION. Server authority, provider interface, transport
v1, review queue, and the profiled 2025-07-16 client transport are implemented
and statically integration-tested. Production-key and live-client acceptance
remain. Date: 2026-09-27.
Scope: `Banquet of Heroes - Main` / `Banquet of Heroes v1.0` (Gepard clients),
`Banquet of Heroes` (offline, no Gepard — used as clean baseline),
server `GitHub\BanquetOfHeroes` (rAthena, PACKETVER 20250716, Laravel CP).

Normative implementation documents:

- Server protocol: `BanquetOfHeroes/docs/riftlock-transport-v1.md`
- Client implementation and live gate: `docs/riftlock-client-v1.md`

---

## 0. Ground truth (surveyed, not assumed)

### Client
| Item | Finding |
|---|---|
| Game exe | `Banquet of Heroes.exe` — patched 2025-07-16 Ragexe, **not packed**. Sections `.text .rdata .data .rsrc .reloc .edata .tls .lotus .xdiff`. v1.0 `.xdiff` = 0x3C2000 (WARP diff + relocated imports). |
| Gepard | `gepard.dll` 27.9 MB, VMProtect (`.vmp0-2`), signed RU cert, byte-identical in both installs. `gepard.license` re-issued per exe build. `gepard.register` header "Gepard Shield 3.0". |
| Gepard load path | **Not in the exe import table and no "gepard" string in the exe.** Loaded indirectly (likely via `uxs.dll`/`dinput.dll` chain or obfuscated string). Must be confirmed before removal (Procmon `Load Image` + x32dbg `LdrLoadDll` bp). |
| Other in-process code | `dinput.dll` (ROExt proxy, `dinput.ini`), `uxs.dll` (`.grfkey` section, GRF decrypt, imports `cps.dll`), `bohcustoms.dll` (`.bohseal`, Gepard-aware, logs `packet_source=… likely_gepard=…`; imported by Main only), stock `aossdk/v3hunt/BaseSDK/IAPSDK`. |
| WARP runtime surfaces | `CustomPacketDispatch` dispatcher-table hook (`0x00CAA2E0`: 0x0BB7/0x0BDD/0x0BEF), NPC frame bridge `0x00C7642D`, CustomDLL import injection, `dll_integrity` self-seal. See `docs/gepard-safe-runtime-checklist.md`. |

### Server
| Item | Finding |
|---|---|
| Gepard wiring | Complete: `src/common/socket.cpp:247-640` (crypt units, init, CS/SC processing, WFIFOSET hook :1625), `login/loginclif.cpp:547` (login gate), `login/account.cpp:50-240` (unique_id bans), `map/clif.cpp:113-168` (sync timeout 40 s, reports), `char/char_mapif.cpp:29-352` (block/report tables), `@gepard_*` commands, `get_unique_id()` script cmd, autocombat/autosupport `LIMIT_GEPARD`. |
| **Config in repo** | `conf/gepard_shield.conf` → `gepard_shield_enabled: no`. **Verify production value** — if prod is also `no`, the Gepard client currently protects nothing server-verifiable. |
| rAthena obfuscation | Off (`PACKET_OBFUSCATION` commented; keys zero for >20180307). |
| Existing server AC | `skill_timing_control.cpp` + `spam_delay_engine.cpp` + `unit.cpp:88-310` (delay, flood 20 pps, variance/desync, auto temp/perm ban), `max_walk_speed`, `min_skill_delay_limit`, macro captcha (punishment 0), SQL logs (chatlog **off**). |
| Laravel CP | `AccountModerationController`, `CpModerationLog`, `AuthAuditLog`, transparency logs. **No Gepard/AC views.** |

### Design lessons from the Gepard integration (do not repeat in Riftlock)
Gepard is being removed, not fixed. These are recorded only as requirements for the new design:
1. Never trust a client-supplied IP/identity (Gepard INIT_ACK accepts an optional "real IP").
2. Enforce minimum client version from day one (`min_allowed_license_version` was never checked).
3. Gate map actions from connect, not from the first handshake reply.
4. Ship schema as `sql-files/upgrades/` migrations, not runtime DDL.
5. Heuristic signals flag for review; they do not auto-perm-ban.

---

## 1. Honest framing

- **A user-mode anti-cheat written by a small team will be bypassed** by a motivated reverser. Gepard itself is bypassed publicly from time to time. The achievable goal is:
  1. make every *cheap* cheat fail (OpenKore without client, packet editors, CE speedhack, dropped proxy DLLs, edited GRF/lub),
  2. make *expensive* cheats detectable server-side by behaviour,
  3. make bypasses short-lived (per-build rotation) and bans sticky (HWID + account graph).
- **The server is the only trustworthy party.** Every client signal is advisory evidence; every server-authoritative violation is proof.
- "Perfect" is not a measurable target. Section 7 defines measurable acceptance instead.

### Decision
**Full replacement: Gepard is abandoned.** `gepard.dll`, `gepard.license`, `gepard.register`, the `gepard_*` server code, `@gepard_*` commands and Gepard tables are removed at cutover. Riftlock is developed and validated against the offline `Banquet of Heroes` client (no Gepard), so the two protectors never have to coexist. The only Gepard behaviour carried forward is a stable per-device ID for consumers such as `get_unique_id()` and autocombat/autosupport `LIMIT_GEPARD`, which the new provider must supply.

---

## 2. Threat model (RO-specific)

| # | Threat | Typical tool | Where it must be caught | Primary signal |
|---|---|---|---|---|
| T1 | Client-less bot | OpenKore, custom Python | Transport (handshake) + server behaviour | No valid handshake / MAC; inhuman timing |
| T2 | Bot bridged through real client (XKore-style, injected) | OpenKore XKore, DLL bots | Client module + server behaviour | Foreign module, hooked send/recv, timing |
| T3 | Speed hack | Cheat Engine speedhack, `timeGetTime`/QPC hooks | **Server** (authoritative) | Move/attack cadence vs server tick |
| T4 | Packet editing / replay | WPE, RPE, Frida scripts | Transport (seq + MAC) + server validation | MAC fail, seq replay, impossible params |
| T5 | Memory editing | Cheat Engine (zoom, no-delay visuals, auto-pot) | Client module (weak) + server (strong for effects) | Debugger/handle signals; server-impossible states |
| T6 | Asset hacks | Edited GRF/lub (transparent walls, no-effect sprites, name reveal) | Client module | Hash mismatch of manifest entries, loose `data\` overrides |
| T7 | Macro / input automation | AutoHotkey, hardware macro | **Server** behaviour (only partially solvable) | Low inter-action variance, 24/7 sessions, captcha fail |
| T8 | Multi-client abuse | Sandboxie, VMs, mutex patch | Server (HWID + IP graph) | Same HWID cluster, concurrent sessions |
| T9 | Ban evasion | HWID spoofers, VPN, new accounts | Server (identity graph) | Fuzzy HWID match, payment/email/IP graph |
| T10 | Server exploits via crafted packets | Fuzzers, dupes | **Server** input validation | Malformed length, state-machine violation |
| T11 | Tampering with the AC itself | Patch out DLL, emulate heartbeat | Transport (challenge–response bound to session key) | Missing/incorrect challenge responses |

---

## 3. Target architecture (layered)

```
┌──────────────────────────── CLIENT ─────────────────────────────┐
│ Banquet of Heroes.exe (WARP-patched, static)                    │
│   └─ riftlock.dll (imported via CustomDLL.applySpec, packed)    │
│        ├─ Integrity: section hashes, module allowlist, GRF      │
│        ├─ Environment: debugger/handle/thread-origin signals    │
│        ├─ Identity: HWID vector (salted, hashed)                │
│        └─ Transport: handshake, session key, packet MAC, HB     │
└───────────────────────────────┬─────────────────────────────────┘
                                │ TCP (login/char/map)
┌───────────────────────────────▼─────────────────────────────────┐
│ rAthena                                                          │
│   src/common/shield/  (new; gepard_* code deleted at cutover)    │
│     ├─ shield_iface.hpp  — on_connect/on_cs/on_sc/on_tick        │
│     ├─ provider_riftlock — implemented                           │
│     └─ provider_none     — dev/offline                           │
│   map: movement/attack/skill authority, rate limits (existing+)  │
│   → ac_event table (SQL) ───────────────┐                        │
└─────────────────────────────────────────┼────────────────────────┘
                                          ▼
┌──────────────────────────────────────────────────────────────────┐
│ Laravel CP: AC review queue, scoring, ban waves, audit log       │
└──────────────────────────────────────────────────────────────────┘
```

### 3.1 Layer 0 — Server authority (highest ROI, no client needed)
Extend what exists; do not duplicate `skill_timing_control`.
- **Movement:** validate each walk request against `status->speed`, last accepted position/tick, and `max_walk_path`. Track accumulated drift (server-computed arrival tick vs next request). Speedhack = sustained requests faster than server walk-completion, not single outliers.
- **Attack/skill cadence:** already covered; add per-account histogram of inter-action deltas (for T7) — log, don't auto-ban.
- **State machine checks:** skill not learned / wrong level / out of range / dead / on cooldown / wrong map; item use not in inventory; NPC dialog responses without open dialog. These are *proof* → safe for automatic kick.
- **Rate limits per opcode class** (not just global 20 pps).
- **Economy analytics** (offline job over `picklog`/`zenylog`): zeny/hour and drop/hour z-scores per map → review queue.
- **Enable `chatlog`** (or at least whisper metadata) for RMT evidence; disclose in ToS.

### 3.2 Layer 1 — Transport authentication

Purpose: T1, T4, T11. Implemented as Riftlock transport v1 for every login,
character, and map TCP connection. The client probes first; the server returns
an Ed25519-signed ephemeral hello; both sides derive X25519/HKDF-SHA256
directional keys; the client verifies an HMAC-bound ready acknowledgement.
Every native C→S packet is carried in a strictly sequenced `0x0CF4` envelope
with a 16-byte HMAC tag. Server challenges and client responses are also bound
to the directional session keys. Three consecutive heartbeat misses disconnect
only in enforce mode. See `BanquetOfHeroes/docs/riftlock-transport-v1.md` for
the packed byte contract and packet IDs `0x0CEF` through `0x0CF5`.

Reality check: an attacker who dumps a session key from process memory can
bridge a bot. That is why Layer 2 and Layer 0 still exist, and why builds rotate.

### 3.3 Layer 2 — Client module `riftlock.dll`
Loaded via `CustomDLL.applySpec` (never hand-edit import directory). Initialise in a dedicated thread, not heavy work in `DllMain`.
- **Integrity**
  - Build-time manifest (tool: `tools/bg_manifest.py`): SHA-256 of exe sections `.text .rdata .xdiff .lotus`, every shipped DLL, and **selected GRF entries** (walls/effects/sprites prone to T6, lub files). Sign manifest with Ed25519; ship signature, server holds manifest per `build_id`.
  - Do **not** full-hash 2.7 GB GRFs at startup; hash GRF header + file table + manifest-listed entries; cache by (size, mtime, header hash).
  - Detect loose `data\` overrides for manifest-listed paths.
  - Periodic re-hash of `.text` in small slices (spread CPU).
- **Module allowlist:** `LdrRegisterDllNotification` + initial PEB walk; allowlist by SHA-256 (own DLLs, known OS/GPU/overlay DLLs: Discord, Steam, NVIDIA, AMD, OBS, RTSS). Unknown module → report (not kill) during rollout.
- **Thread origin:** thread start addresses outside any mapped image → manual-map signal.
- **Hook detection:** compare prologues of `ws2_32!send/recv/WSASend/WSARecv`, `kernel32!QueryPerformanceCounter`, `winmm!timeGetTime`, `GetTickCount` against on-disk bytes (T2/T3 signals).
- **Debugger/handles:** `IsDebuggerPresent`, `NtQueryInformationProcess(ProcessDebugPort)`, PEB `NtGlobalFlag`, hardware breakpoints in DR0-3 of own threads; open-handle scan to own process (`NtQuerySystemInformation(SystemHandleInformation)`) — report only.
- **Identity (HWID vector):** SMBIOS UUID, system volume serial, `MachineGuid`, primary MAC(s), CPU brand/ID, GPU adapter LUID-stable IDs → each hashed with server salt; server does **k-of-n fuzzy match** (spoofers change 1–2 components, hardware upgrades change 1).
- **Self-protection:** pack with a commercial virtualizer (VMProtect/Themida licence — Gepard itself uses VMProtect). String encryption, per-build randomised opcode/field layout of the handshake, per-build keys. Without a packer, assume the DLL is read like source.
- **Crash-safety:** all checks wrapped in SEH; a failing check reports and continues. The AC must never be the reason the game crashes.

### 3.4 Layer 3 — Decision pipeline
- New table `ac_event(id, ts, account_id, char_id, session_id, hwid_cluster, ip, build_id, source{server,client,transport}, code, severity, evidence_json)` + proper `sql-files/upgrades/` migration (design lesson #4). New `ac_block` keyed by HWID cluster. Gepard `unique_id` blocks do not transfer (different ID scheme); only account-level bans carry over. Gepard tables/columns are dropped at cutover.
- **Scoring:** per-account rolling score; server-proof events can auto-kick; client-only events never auto-ban.
- **Ban waves:** client-detection bans applied in batches (e.g. weekly), not instantly — cheat devs cannot bisect which check fired.
- **Laravel CP:** review queue (evidence, timeline, related accounts by HWID/IP), actions logged to `CpModerationLog`, appeal flag.
- **Remove `@gepard_*`**; add `@acblock/@acunblock/@acinfo`.

---

## 4. Do's and Don'ts

### Do
1. **Treat the server as the source of truth.** Validate every action server-side; client checks only add evidence.
2. **Build behind a provider interface** (`shield_iface` with `provider_riftlock` + `provider_none`) and delete all `gepard_*` code in the cutover release.
3. **Ship in monitor-only (shadow) mode first** and collect false-positive data from real players before any enforcement.
4. **Separate proof from suspicion:** a server-impossible state is proof; an unknown DLL is suspicion.
5. **Delay client-signal bans** (waves); **instant-kick** only on transport/state-machine proof.
6. **Version-gate clients** (`build_id` + minimum version) and rotate keys/layouts every release.
7. **Bind challenges to the session key and a server nonce** so answers cannot be replayed or precomputed.
8. **Allowlist, don't blocklist,** for modules; keep a curated list of benign overlays.
9. **Hash + salt all hardware identifiers**, store only digests, disclose collection in ToS/privacy page.
10. **Fuzz every new server parser** (length fields, truncated packets, bad seq) — the AC must not introduce a server crash vector.
11. **Log evidence immutably** (append-only table, include build_id and raw values) so every ban is defensible.
12. **Keep a kill switch** (`Transport.Mode: Off/Monitor/Enforce` in `conf/riftlock.yml`) reloadable without restart.
13. **Reuse WARP infrastructure** (`CustomDLL.applySpec`, `dll_integrity` seal, `CACHE`) and document every EXE surface like `gepard-safe-runtime-checklist.md` does.
14. **Keep a vanilla offline client** (`Banquet of Heroes`) as the control group for every test.
15. **Budget ongoing maintenance** (~1 day/week after launch) — an unmaintained AC decays in weeks.

### Don't
1. **Don't write a kernel driver.** Signing (EV + attestation), BSOD risk, and player trust cost outweigh benefits for a private server.
2. **Don't crash or `ExitProcess` on detection** — it tells the cheater exactly where the check is. Report and let the server decide.
3. **Don't auto-perm-ban on heuristics** — heuristic signals flag for review.
4. **Don't trust any client-supplied identity/IP.**
5. **Don't roll your own crypto primitives** — use libsodium/Monocypher (X25519, Ed25519, ChaCha20-Poly1305, BLAKE2/SHA-256).
6. **Don't embed a static symmetric key** as the only protection — it is extracted once and shared forever.
7. **Don't scan the user's filesystem, browser, or unrelated processes' memory.** Window-title/process-name scans: low value, high privacy cost; if used, hash names and keep the list small.
8. **Don't hash multi-GB GRFs at every startup** — kills load time, players will leave.
9. **Don't ship a build containing both `gepard.dll` and `riftlock.dll`** — cut over in one release; the patcher removes `gepard.dll`, `gepard.license`, `gepard.register`.
10. **Don't reuse or redistribute Gepard's code, protocol constants, or licence files**; check your Gepard contract for termination/notice clauses.
11. **Don't publish detection details** (changelogs, Discord) — describe "security improvements" only.
12. **Don't declare a detection "working" without a reproducible test case and a measured FP rate.**
13. **Don't leave `get_unique_id()` consumers broken** — autocombat/autosupport device limits depend on `unique_id`; provide the same value from the new provider.
14. **Don't block benign overlays** (Discord, Steam, OBS, RTSS, NVIDIA/AMD) or accessibility tools.
15. **Don't ship unpacked in enforcement mode** — acceptable only for internal/closed-beta monitor builds.

---

## 5. Phased delivery

| Phase | Work | Output |
|---|---|---|
| **P0 Baseline** (1–2 wk) | Trace how `gepard.dll` is loaded (Procmon `Load Image`, x32dbg `LdrLoadDll`) so it can be removed cleanly; inventory every `gepard_*` / `unique_id` consumer; measure FPS/CPU/login time on the offline client on 3 machines. | `docs/ac-baseline-2026-xx.md` |
| **P1 Server authority** (2–4 wk) | Section 3.1 work; `ac_event` table + migration; heuristic auto-ban → review flag. | rAthena PR |
| **P2 Shield interface** (1–2 wk) | Add `shield_iface` + `provider_none`; remove `gepard_*` from `socket.cpp`, login/char/map, `@gepard_*`, Gepard tables. | rAthena PR |

Transport and client implementation details moved to the normative documents
listed at the top of this plan. Production-key embedding, x86 libsodium
deployment, client initialization, and the disposable server live phase pass.
Cutover remains blocked on the interactive Ragexe acceptance matrix and the
planned protected/packed enforcement build.
