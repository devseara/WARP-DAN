# Floor-depth crash: render caves overwrote weather state

The user reported exception `0xc0000005` at `0x02570ABC`, followed by native
player draw `0x00D3A325` and Celestial player draw `0x0256D5E3`, on
`new_1-1.rsw`. EAX was zero. The rejected client hash is
`601fa320dceb31f016649d8183f8f8604668901acc5f81caf25d0a15d6fcce00`.

## Exact reproduction

The existing Celestial payload occupies `0x0256AA00..0x02576018`.
`CelestialState` begins at `0x02570A38`. WARP's allocator, when reopening the
already-patched image, reused its zero-filled globals as apparent free space:
the floor constant/body/shadow code began at `0x02570A50/60/BC` inside that
owned payload. The shadow entry is State+132, the `weather_mask` field.

Executing the real emitted `CelestialReset` clears that field and its neighbors.
The shadow bytes change from `F3 0F 5F 3D ...` to zero bytes. Executing them
with EAX=0 produces the same instruction address and null memory read as the
user's report. `crash-reproduction.json` and `reset-then-render.json` pin that
reproduction. The static cave emulator and prior sun-shadow test did not
detect allocation ownership: they either ran unmodified file bytes or stubbed
native player draw rather than executing the depth cave after state writes.

## Correction

The upgrade now generates the same QJS cave on the native fixture and relocates
its four zero-constant reads and two native return jumps into a separate
`.rhwfix` section outside the entire original mapped image. It grows the PE
header by one file-alignment block when needed, updating section raw pointers
while preserving all existing section RVAs/data except the intended render
hooks and old clan-hook removal. Inputs with auxiliary raw debug/certificate/
symbol layouts require separate profiling rather than an unchecked move.

The corrected cave range is `0x02577000..0x025770A0`; it no longer intersects
the weather payload. FloorSafeSpriteDepth also rejects allocations overlapping
the registered Celestial runtime. CelestialDial records the runtime's complete
base/size alongside its existing draw owner for that check.

The new native regression calls reset, processes snapshots for `new_1-1` and
`prt_fild08`, resets again and executes both actual caves after those writes:
ten native cave executions pass, with code bytes intact and expected SSE,
register, stack and flag results. Both Celestial patch orders and the native
sun-shadow test pass. The existing floor emulator covers all66 body/3 shadow
cases on the corrected binary. An injected allocation-overlap fixture verifies
rejection before renderer-hook writes.

## Corrected release

Corrected client SHA-256:
`83c027c36c7a0fef5126af25ac88747084fd6248cb72c478070bd47b8f0fd65b`.
It is built from the healthy pre-upgrade client, not the corrupted state image.
The versioned release checkpoint is
`Outputs/sprite-depth-crash-fix-20261018/deployment/`. Its `before/` preserves
the rejected file for diagnosis, while `healthy_recovery` points to the prior
healthy EXE/manifest/signature set. Failed installation restores that healthy
set. No GRF, sprite artwork, DLL or server setting changed. The corrected release
is installed and signing/independent manifest checks pass. Live game retesting
is still required; offline execution is not a claim of live acceptance.
