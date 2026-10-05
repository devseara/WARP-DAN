# Riftlock client transport v1

Status: activated for the profiled `2025-07-16 Ragexe` client. The production
Ed25519 public key is embedded, the official 32-bit libsodium runtime is
staged, isolated/current-main-profile WARP builds pass, and the disposable
server live phase passes. Interactive Ragexe login/relog/map-change acceptance
remains.

## Runtime boundary

Riftlock is a standalone `riftlock.dll` loaded through
`CustomDLL.applySpec()`. It does not hook `ws2_32.recv`, rewrite executable
code at runtime, patch an IAT or vtable at runtime, or detour Winsock.

WARP installs three static surfaces:

- `CConnection::Connect` at `0x00C13FC0` resets transport state for every
  login, character, and map TCP connection.
- The two `CPacketQueue::InsertBackData` calls at `0x00C1495D` and
  `0x00C1496C` wrap native client packets after stock packet-key obfuscation
  and before queue insertion.
- The shared receive-queue insertion at `0x00C145D2` strips and authenticates
  server control packets `0x0CF0`, `0x0CF2`, and `0x0CF5` before login,
  character, or map mode-specific packet parsing. Ordinary server bytes are
  forwarded unchanged.

The DLL sends the raw Riftlock probe before the first native packet, buffers
native packets until the signed handshake is ready, and then flushes them as
strictly sequenced authenticated envelopes. The raw probe and control replies
bypass native packet-key obfuscation; the envelope's inner packet retains the
stock obfuscated opcode so rAthena decrypts it in its normal parser after
Riftlock unwraps it.

## Configure and build

Generate the server key with the server repository's
`tools/riftlock_keygen.py`. Keep the 64-byte secret only on the server. Embed
the printed 32-byte public key in the client source:

```text
python tools/configure_riftlock_public_key.py <64-hex-character-public-key>
```

The generated public-key header contains the active server public key. Resetting
it to the all-zero placeholder is fail-closed: `RiftlockInit()` returns zero and
native traffic is dropped.

Build the dedicated DLL:

```text
cd CustomDLL\src
build_split.bat
```

The Riftlock compile uses `/W4 /WX` and produces a 32-bit `riftlock.dll`.
Deploy the following beside the patched game executable:

- `riftlock.dll`
- a trusted 32-bit `libsodium.dll`

Select `RiftlockTransport` in WARP and rebuild from the offline/no-Gepard
client. Do not deploy Gepard and Riftlock in the same cutover build.

## Hook evidence (protocol v7)

`riftlock_hooks.inl` compares 13 Winsock and time-source exports (`send`,
`recv`, `WSASend`, `WSARecv`, `connect`, `closesocket`,
`QueryPerformanceCounter`, `GetTickCount`, `GetTickCount64`, `Sleep`,
`timeGetTime`, `NtQueryPerformanceCounter`, `NtDelayExecution`) with the on-disk
image of their Windows-directory module. It reads the first 32 live bytes plus
three extra bytes, undoes every HIGHLOW base relocation that starts inside the
window, compares with the file bytes, and also requires `GetProcAddress` to
match the on-disk export RVA. Unloaded modules and forwarded exports count as
unresolved. The first scan runs during initialization; handshakes and
heartbeats send the latest snapshot and queue a background rescan. The server
side and wire format are documented in the server repository's
`docs/riftlock-transport-v1.md`.

Build only the Riftlock DLL and the standalone verifier into
`CustomDLL\src\riftlock_stage\` with the same hardened flags:

```text
CustomDLL\src\riftlock_stage_build.bat
```

Run the verifier from the game directory:

```text
riftlock_stage\riftlock_v7_hooks_verify.exe "<game-directory>" <client-exe>
```

A healthy result reports `hook_checked=13 unresolved=0 mismatches=0`, then
`hook_prologue_probe_detected ... first_target=4`,
`hook_eat_probe_detected ... first_target=6`, and a clean
`hook_probe_restored` line. The probes patch only exports the verifier never
calls and restore them before exiting.

## Repeatable static verification

```text
python tools/verify_riftlock_client.py --exe <patched-client.exe>
python tools/fix_custom_bridge_iats.py --dll riftlock.dll <patched-client.exe>
```

The second command is read-only without `--write`; it must report
`stale bridge operands: 0`.

## Live acceptance gate

Use server monitor mode first. A release candidate is not accepted until all
of these pass with the real client and production public key:

1. login, character select, map entry, relog, map change, reconnect;
2. heartbeat challenge/response over at least three intervals;
3. every native client packet observed as `0x0CF4` in enforce mode;
4. wrong build, bad signature, bad ready MAC, replay, and bad envelope MAC
   fail closed without a client crash;
5. normal exit and reconnect leave no stale session key or sequence;
6. `riftlock.log` contains no initialization or transport failure.

Only after this gate should the server change from `provider: none` to
`provider: riftlock`. Keep server enforcement in monitor mode until the live
false-positive window is complete.
