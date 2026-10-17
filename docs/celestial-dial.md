# Celestial dial implementation

The Ragnarok-themed native dial shows synchronized server time, rAthena's existing day/night state and current map weather. It reserves space above the monster HUD. Existing ambience is observed without changing its effects or map assets; separately owned rain and thunderstorms are configured by per-map YAML profiles. Only `prt_fild08` is enabled in the supplied defaults. The supplied BanquetOfHeroes deployment configures one hour of day and one hour of night through the existing rAthena timers. The user accepted the dial, denser rain, wet-ground visibility, every-third automatic thunderstorms and corrected storm/shadow appearance in game. Live indoor/outdoor transitions, character re-entry, effect toggling and natural storm expiry passed the bounded cleanup audit below.

The target is 2025-07-16 Ragexe and the matching BanquetOfHeroes map-server bridge. The main WARP profile selects `CelestialDial` (patch ID 389). The dial EXE is installed at the supplied game path, with its Riftlock release signature regenerated and independently verified. No local server process was running during deployment; the cycle initializes on the next map-server startup. Offline captures are native-code render evidence, not live screenshots.

## Implemented behavior

- The 280 by 98 native UIWindow sits at Y=8 and is fully click-through. Its pale silver and blue frame, faceted gold sun or shaded silver crescent, Tahoma labels and server clock are drawn into its private alpha canvas. No external UI artwork or DLL is required. The window ID is `0x3FE`, distinct from the other custom UIs.
- Server time uses the server's Unix timestamp and signed UTC offset. Unsigned client monotonic elapsed time advances `HH:MM:SS` between replies; the PC's wall clock is never read. A request echo provides bounded latency correction. Refreshes occur every 60 seconds, with 10-second retries and a 90-second stale cutoff.
- Day or Night reflects `night_flag`. A real existing timer provides the phase countdown and ring progress. When cycling is disabled, the strip says `No scheduled change`. Reaching zero never changes phase locally; it waits for the server.
- The bottom strip displays current weather beside the phase countdown, within the same 280 by 98 bounds. Server snow, clouds, fog, petals, leaves and fireworks flags can coexist. The client also observes the current actor's exact live CWeather-owned effect for native map ambience. Recognized effects add their condition; unknown scoped ambience displays `Ambient`. Arbitrary combat effects and stale owner pointers are excluded. The rain prototype owns its own native emitter instance; it does not change native ambient-effect ownership, map flags or GRFs. The separate scene-RGB wrapper provides the negotiated night/storm tint and lightning pulse described below.
- A shared global Y cell defaults to 24. While the synchronized dial is visible, it becomes 114. Both monster HUD skins read this value on every update. The incremental candidate redirects the existing monster position call through the same cell, preserving its artwork and behavior.
- Native map and map-server transition handlers invalidate the client cookie and hide the dial before replaying stock processing. Native window destruction and invalid game state reset it too. Stale replies, wrong versions, malformed flags and invalid timezone values cannot reopen it.
- The backend subscribes only after a valid WENV request. A map-thread timer sends subscribed players updates after map, phase, night-eligibility or weather-flag changes, or a periodic clock resync. It never sends WENV to an unmodified client that has not subscribed.

## Source and protocol

`Scripts/Patches/CelestialDial.qjs` installs the static bridges and an import-free payload built from `Scripts/Runtime/CelestialDial/runtime.cpp`. `Inputs/CelestialDial/runtime.bin` and its JSON manifest are generated together. The QJS loader verifies bounds, version and CRC before relocation. The shared `0x0BF6` router retains BPUI/GCHA and its stock fallback, adding WENV without replacing those protocols.

The matching server files are `src/map/world_environment.cpp`, `src/map/world_environment.hpp`, `src/map/world_environment_profiles.cpp`, `src/map/world_environment_profiles.hpp` and `src/common/world_environment_wire.hpp`. `pc.hpp` owns the subscription state per session; `clif.cpp` dispatches requests and starts/stops the metadata timer. Both Visual Studio map projects include the module. CMake and Unix Make already discover map source files automatically. There is no SQL, NPC, char-server or login-server change.

WENV uses a 24-byte request on `0x0BF8` and a snapshot on `0x0BF6`, magic `0x564E4557`. V1 retains its exact 68-byte snapshot. V2 appends a 32-bit weather mask for a 72-byte snapshot; bit values are snow 1, clouds 2, fog 4, petals 8, leaves 16 and fireworks 32. Client-only unknown native ambience uses bit 64 and is rejected on the server wire. V3-v6 retain an 80-byte lease/generation layout, adding Rain 128, Thunderstorm 256 and LightningFlash 512 in their respective versions. The server answers each client in its requested version. A new client requests v6, then retries v5, v4, v3, v2 and v1 after unanswered requests time out; it still observes native ambience with an old server. Both wire-header copies must remain identical. Requests carry only subscribe/refresh, a cookie, request sequence and monotonic echo. Snapshots carry server Unix time, UTC offset, global phase, local night eligibility, actual phase duration/deadline, map identity and response sequencing. There are no mutation actions or client-controlled time settings.

V3 appends `rain_generation` and `rain_remaining_ms` to the v2 prefix, for exactly 80 bytes. Rain is bit 128 and is legal only on `prt_fild08` with a nonzero generation and a remaining duration in 1..300000 milliseconds. Zero remaining duration requires Rain off. V1/v2 clients retain their exact snapshots and never receive the new flag. Client negotiation falls back 3 -> 2 -> 1 on ten-second request timeouts.

## Per-map profiles (WENV v6)

`conf/world_environment.yml` is the weather authority; `conf/import/world_environment.yml` supplies rAthena-style overrides. Legacy global `rain_*` battle settings have been removed. Native `day_duration` and `night_duration` remain 3600000 milliseconds each.

```yaml
Header:
  Type: WORLD_ENVIRONMENT_DB
  Version: 1
Body:
  - Map: prt_fild08
    Enabled: true
    Automatic: true
    Outdoor: true
    ClearDuration: 600000
    RainDuration: 180000
    StormDuration: 180000
    StormEvery: 3
    Weather:
      Rain: true
      Thunderstorm: true
```

All durations are milliseconds. Clear duration accepts 60000–86400000; rain/storm durations accept 1000–300000. `StormEvery: 0` disables automatic storms while preserving permitted manual storms. `Enabled` controls managed weather; `Automatic` controls scheduled showers. An enabled precipitation profile requires explicit `Outdoor: true`, and thunderstorms require rain. New profiles default disabled and nonautomatic. Indoor/unlisted maps remain unmanaged. Only Rain and Thunderstorm are configurable here; existing snow, fog, clouds, leaves, petals and fireworks remain native.

Use `@reloadweatherprofiles` after editing. Loading is transactional, including imports: malformed YAML, unknown fields, invalid bounds and failed imports preserve all active profiles and leases. An unchanged reload retains deadlines and cadence. Changing an automatic profile restarts its clear interval and cancels its automatic lease/cues; permitted manual leases retain their deadline. Disabling/removing a profile cancels its precipitation and queued lightning/audio. Profiles are independent, and manual starts do not advance their automatic shower counter. A missing/nonlocal map does not borrow another map or consume a shower.

V6 adds `ManagedWeather` (snapshot flags bit 4), with no packet-size increase. Rain requires that authorization bit plus the existing valid bounded lease. A v6 client can therefore render managed weather on any configured map. V1–v5 retain their original packet layouts and flags; managed rain/storm remains restricted to `prt_fild08` for those older clients. V5 lightning remains compatible. Server snapshots continue to report concurrent native weather, and one map's thunder cues never reach another map. The existing sunny-shadow prototype remains scoped to `prt_fild08`.

The v6 client payload requires the matching new server for per-map authorization. An old server continues working through version negotiation. Upgrading the supplied EXE preserves its unrelated bytes and requires a newly paired Riftlock signature. Offline parser, scheduling, command, protocol and native-render tests do not establish live acceptance of this revision.

## Outdoor rain prototype

Rain is off at startup. An Admin with command permission can use:

```text
@warp prt_fild08
@rainprototype start 120
@rainprototype status
@rainprototype stop
```

Rain starts on the current map only when its profile permits it. Stop/status select the current configured map, with `prt_fild08` as the compatibility fallback from unconfigured maps. The default is 120 seconds and the accepted range is 1..300 seconds. Existing command-group permissions apply; the new command is also restricted from console, NPC-script dispatch and autotrade. The server owns an independent map-thread deadline and automatic cadence for each configured loaded map, without a new worker or NPC loop. Starting or stopping increments a generation, and the existing one-second poll detects changes. Active rain snapshots refresh every two seconds; the client bounds its lease to five seconds so a lost stop packet or disconnect cannot leave indefinite rain. Renewal does not duplicate the native effect. Restarting the server clears the prototype.

The supported native CActor factory is `0xC44540`, `thiscall(actor, effectId, zero-offset x/y/z, zero float)`, returning the exact effect pointer. The prototype uses ID 857 (`EF_RAIN_PARTICLE`) and a private copy of its 19-entry CEffect vtable plus RTTI. Slot 1 calls the stock process at `0xBC4C70` while owned and leased, or returns false after stop/reset/expiry. The native CWorld loop at `0xA6BAE0` then invokes its stock deleting destructor and removes that exact world-list node. `CEffect::~CEffect` at `0xB90D90` sends owner message 0x17 with its exact pointer and retires its own children. No actor-wide remove-effect packet, manual list unlink, raw delete or shared native-vtable edit is introduced.

This client's stock ID 857 uses `effect\\번개1.bmp`, a blue lightning texture. ID 944 uses stone particles and a separate one-shot effect; it is unsuitable as a plain-rain substitute. The owned instance alone overrides vtable slot 15 (0x3C) to call the same native particle emitter `0xC0D5B0` with `effect\\boh_rain_prototype.bmp`. The deterministic additive streak is generated by `tools/build_celestial_rain_texture.py` and packaged under `Inputs/CelestialDial/`. The patch installs it at `data/texture/effect/boh_rain_prototype.bmp` beside the target EXE. Existing effect textures and all GRFs stay unchanged. The signed release's loose-data integrity manifest includes this new texture.

Patch-time byte checks cover the factory, native process, world disposal path, effect owner release, native emitter and CEffect vtable entries. Rain restarts after stock lifetime expiry at most once per second. Native map/reconnect/reset paths invalidate its ownership before normal processing resumes. The dial gives Rain display priority and retains concurrent conditions (`Rain + Fog`, or `Rain +2` for three conditions). Native rendering retains its own `/effect` behavior, while stop/lease expiry still force the owned instance's normal disposal.

Offline tests execute the emitted runtime and the real CWorld destruction branch, with explicit factory, resource/destructor and rendering boundaries. They verify repeated snapshots, lease loss, stock lifetime expiry, resets, RTTI, private texture routing and preservation of an existing native snow instance plus Snow/Fog flags. The real server module and extracted production ACMD body are compiled and exercised for map scope, numeric grammar, upper bounds, default duration, status, stop, expiry and v1/v2 compatibility. These checks do not establish visible rain coverage, camera behavior, particle density or full renderer/resource teardown in a running client.

### Live rain correction and appearance revision

The first live rain test displayed Rain on the dial without particles. Read-only sampling caught the owned ID 857 instance at age 0 with lifetime 1000, then immediate retirement. Its replacement virtual particle step had been declared `void`, but native `CEffect::Process` tests that step's AL result before advancing age. The stock dispatcher exits at `0xBC2DE1` with `MOV AL,1`; the emitter itself has no Boolean return contract. The corrected step explicitly returns 1. A regression executes the actual native parent update with an emitter that returns an AL value of zero: the earlier EXE retires at age 0, while the corrected EXE advances and preserves normal stop behavior. Earlier factory/process boundary doubles did not cover this contract.

The user then confirmed visible particles but rejected their appearance as rain; the screenshot showed broad amber sparks. The native type-157 renderer selects white for particle palette 0 and red/amber for palettes 1/2. The appearance revision changes only freshly created primitives whose owner and type match the prototype. It fixes palette 0, reduces streak size to 2.0/2.5 world units, sets downward progress to 5.5 units per native tick, distributes drops over radii 60..340 and initial heights 80..192 above their local ground reference, and emits eight four-drop batches per ten native ticks. Child lifetime is capped at 72 native ticks. These are prototype parameters awaiting live appearance acceptance, not a verified full-map rain simulation.

The neutral texture remains unchanged. No stock palette, renderer function, CWeather state, map flag or unrelated primitive is patched. Tests now execute the stock primitive update at `0xB823D0` and verify downward progress in addition to parent keepalive, private texture routing, bounded lifetime, neutral palette and cleanup. Both changes retain the original private-vtable ownership and server lease. `/effect`, camera coverage, movement and manual stop still require live acceptance of the final appearance.

The requested alphabetical ordering is enforced for C++ include blocks in `clif.cpp` and `pc.hpp`, and for each `ClInclude`/`ClCompile` list in both Visual Studio map projects. File entries retain their exact metadata. `tools/verify_world_environment_source_order.py` checks all four files. Both server targets build with the reordered sources; validation binaries are staged under `Outputs/CelestialDial/rain-fix/server-build/`. The running server is left in place because these edits change source ordering only.

### Terrain-aware wet-look prototype

The user selected wet sheen/puddle glints with splashes and ripples. `Scripts/Runtime/CelestialDial/rain_ground.inl` supplies this cosmetic layer; it does not render character or scenery reflections. Each owned type-157 primitive uses a private native vtable with its RTTI, destructor and message slots preserved. Its bounded update moves drops downward until they contact sampled terrain, then fades the impact. Its draw emits thin camera-facing drop quads, expanding ground rings and short contact flashes. The newest child alone draws twelve stable nearby wet-glint patches, avoiding repeated sheen overdraw from all children. These layers stop with the existing rain lease/reset path.

Ground lookup follows the profiled C3dGround15 resource/GAT data already used by the GrayMap surface: world +0x28 gives the ground; ground +4 is its resource, +8/+12 are GND dimensions and +16 is scale. Resource +0x110/+0x114 are GAT dimensions, and +0x11C points to 20-byte cells containing four heights and type. Dimensions must match the expected two-GAT-cells-per-GND-tile relationship. Bounds, finite heights and walkable types are checked. Four-corner sampling places sheen/ripples 0.08 units above the ground; blocked cells and patches spanning more than four units of height variation are skipped. The test map's file samples near the previously observed actor agree with the native -97 ground height. This is a GAT-height approximation, not roof collision geometry or a terrain-material simulation.

Native `CPrim::queueQuad` at `0xB7C4E0` receives four world-coordinate vectors, the original renderer context and a bounded local queue index. The scoped texture table is restored immediately after submission. Stock render eligibility checks (`0xD9D020` and `0xB7F8D0`) retain `/effect` and native visibility behavior. The two generated textures are `boh_rain_ripple.bmp` and `boh_rain_wet.bmp`; the original rain streak remains byte-identical. All three are packaged by the patch. Existing textures, terrain buffers, map GRFs and weather flags are left intact.

The growing import-free runtime is relocated into an extension of the final WARP-owned PE section. Existing section RVAs/raw offsets are unchanged; only the owned bridges/vtable/contract and allocation headers change. The original overlay is preserved, including the certificate-directory file-offset adjustment when needed. The updater requires exact prior-payload bytes and records the permitted changes. The freestanding MSVC `_fltused` marker adds no CRT dependency or DLL import.

The user confirmed both drops and wet-ground effects are visible in game, but found them too sparse/faint. The visibility revision emits twelve four-drop batches per ten native ticks (up from eight), concentrates radii to 45..260 world units, raises initial alpha from 160 to 220 and lengthens the streak geometry from 4.5 to 8.5 world units. It draws twenty-four nearby sheen patches (up from twelve), with alpha 92..131 and radius 6..9. Impact rings also expand from a larger initial radius. Physics, clipping, ownership, `/effect`, leases and cleanup remain unchanged. Native tests cover the revised birth count and alpha fade. Final density/brightness and performance still need live acceptance.

Offline checks cover ground contact at a height different from the primitive origin, contact fading, ripple/sheen geometry, blocked-cell clipping, immutable terrain, private texture-table restoration, RTTI/notification retention, native `/effect` gating and lease/reset cleanup, in addition to the complete dial/router/HUD suite. Live appearance, clipping on the real map, camera movement and performance remain acceptance items. The client release, signed asset policy and rollback are under `Outputs/CelestialDial/deployment-rain-wet-20261016/`; tests are under `Outputs/CelestialDial/rain-wet/`. To restore the previous signed release, restore its paired files and remove only the two newly added texture files so its older loose-tree manifest matches.

Live acceptance: start a short interval on `prt_fild08`; check Rain on the dial while moving and rotating/zooming the camera; stop without warping and confirm particles retire; repeat with `/effect` off/on, a warp out/back, relog and an existing native weather flag. Baseline effects must survive stop. The dial/HUD geometry remains unchanged. The user has accepted the denser rain appearance and authorized the bounded automatic schedule below; camera, cleanup and performance acceptance still require the complete vector.

Native weather identity is profiled for this client only: CWeather `0x015C57D8`, actor owner `+0x10`, effect pointer `+0x44`; the current player's effect-list head/count are `+0x144/+0x148`. Nodes hold next at `+0` and effect at `+8`; CEffect stores its effect number at `+0x168`. Classification requires current-player ownership and membership in that actor's list, bounded to 1024 nodes. Patch-time guards check the native receiver reference, list routine and effect-number store. This does not identify every EffectTool emitter or fog-table parameter; `Clear` means no supported active weather was identified. Rain scheduling is described below; wind and thunder remain separate work.

`conf/import/battle_conf.txt` overrides `day_duration` and `night_duration` to `3600000` milliseconds each. `night_at_start` remains the native daytime default. Timers initialize on map-server startup, so config reload alone does not enable a previously disabled cycle. Existing `nightenabled` rules still determine which maps darken; indoor maps retain their native lighting. A restart begins a fresh phase rather than persisting a wall-clock schedule.

### Natural wet-ground and weather artwork revision

The user requested removal of the conspicuous S-shaped wet-ground lines while preserving drops and splash ripples. `tools/build_celestial_rain_texture.py` now generates `boh_rain_wet.bmp` from diffuse overlapping lobes with soft irregular edges, without the narrow sinusoidal stripe. The renderer uses stable per-patch opacity (100..123) and broader radii (8..11 world units), removing the former sawtooth pulse. Rain density, fall speed, drop texture and ripple texture remain unchanged. This is a cosmetic ground sheen, without scene reflections or changes to map materials/weather.

`Scripts/Runtime/CelestialDial/weather_art.inl` adds native pixel-art overlays inside the existing medallion inset: clouds and precipitation for rain/snow, low bands for fog, and smaller matching decorations for clouds, petals, leaves and fireworks. The approved sun/moon stays visible behind weather, and returns unchanged in clear conditions. Rain overlays follow the same lease-derived weather mask as the dial text and rain renderer. The overlay does not change geometry, hit testing, server time or the monster HUD reservation.

The user selected **prepare the lightning icon for later**, rather than implementing thunderstorm weather. A private presentation-only high bit allows offline previews of cloud/bolt artwork; WENV v1/v2/v3 never accepts that bit, and the existing server never sends it. The prepared artwork adds no thunderstorm schedule, sound or screen flashes. Future storm implementation must negotiate a supported server protocol before exposing this state.

`tools/test_celestial_dial.py` executes both day/night artwork paths for supported weather, checks that every changed medallion pixel stays inside its sky inset, retains click-through, and verifies rejection of the presentation-only lightning bit on the wire. Existing rain lifetime, terrain, `/effect`, packet, lifecycle and patch-order checks still apply. Native-code previews (with explicit font/canvas boundaries, not live screenshots), verification receipts and candidate preservation evidence are under `Outputs/CelestialDial/rain-natural/`. Signed files, original paired release/texture backups and deployment receipts are under `Outputs/CelestialDial/deployment-rain-natural-20261016/`.

### Automatic rain on prt_fild08

The user accepted the denser rain appearance and requested automatic start/stop. The server now owns a repeating **600000 ms clear / 180000 ms rain** cycle on `prt_fild08`. `rain_auto_enabled` defaults to off in `conf/battle/misc.conf`; this installation enables it in `conf/import/battle_conf.txt`. `rain_clear_duration` accepts 60000..86400000 ms and `rain_duration` accepts 1000..300000 ms. The cycle starts with a full clear interval after map-server startup or a configuration change. It is independent of the existing one-hour day/night phases.

The existing one-second map-thread poll advances the scheduler even when no players are on the map. It resolves `prt_fild08` by name; an unloaded map skips that shower and retries after a clear interval. Natural expiry, manual stop, shutdown and configuration changes use the existing rain generation and lease. Native map weather flags are never set or cleared. A delayed timer expires a shower once and begins a full clear interval, without replaying missed showers.

`@rainprototype start [seconds]` replaces the current automatic shower with a bounded manual lease. Its expiry starts a new clear interval. `@rainprototype stop` stops rain and postpones the next automatic shower by a full clear interval, including when already clear. Changing the schedule through battle-config reload cancels an automatic shower and restarts clear; it preserves a manually started shower. Disabling automatic rain cancels only scheduler-owned rain. Legacy v1/v2 packet lengths and weather masks remain unchanged.

The existing client already handles this state: transitions change `rain_generation`, the next one-second poll updates subscribed clients, and active rain refreshes every two seconds. The dial and renderer receive the same snapshot; clients entering the map receive the remaining lease, and clients leaving it clear their Rain state. This scheduling change requires only the matching server binary/configuration, with no client rebuild or new Riftlock signature.

The bright S-shaped marks in the accepted screenshot are the curved highlight in the private `boh_rain_wet.bmp` texture. They are cosmetic puddle glints rather than wind, lightning or additional weather. The circles are impact ripples. This scheduling revision leaves their artwork unchanged.

`tools/test_world_environment_rain_schedule.cpp` in the server repository compiles the production module and verifies repeat cycles, exact boundaries, arrival/exit snapshots, v1/v2 compatibility, manual overrides, configuration reload, missing maps, delayed ticks, native weather preservation and shutdown. Build/deployment receipts are under `Outputs/CelestialDial/rain-auto/`. Offline checks do not replace a live automatic transition check.

### Every-third automatic thunderstorm on prt_fild08

The automatic sequence is now **rain, rain, thunderstorm**, repeating only on `prt_fild08`. Each shower retains the configured 180000 ms duration and is preceded by 600000 ms clear. The independent 3600000 ms day/night timers are unchanged. The first storm starts about 36 minutes after map-server startup, following two ordinary showers and three clear intervals.

Only a successful automatic start advances the three-shower counter. An unloaded prototype map postpones the attempt by one clear interval without consuming its slot. Manual rain/storm commands retain their existing start, stop, status and duration behavior; they neither consume automatic slots nor reset the sequence. A successful automatic start counts even if subsequently interrupted manually. Changes to the enabled/duration settings and map-server restart reset the sequence and begin a full clear interval. Reloading identical values leaves the active sequence alone.

The scheduler invokes the same `start_storm` path as the manual command and restores scheduler ownership after the successful start. Automatic storms therefore share the existing bounded lease, generation updates, WENV v1-v5 compatibility, lightning cadence and delayed native thunder audio. Disabling/reconfiguring automatic weather cancels an automatic storm and its pending cue, while preserving a manual lease. Expiry/stop starts the next full clear interval. Native map flags and day/night ownership are unchanged; the existing client renders the same Storm dial/lighting state. This update requires only the matching map-server binaries, with no client rebuild or Riftlock re-signing.

`tools/test_world_environment_auto_storm.cpp` executes the production scheduler across two complete sequences, exact start/expiry boundaries, entry/exit snapshots, v1-v5 negotiation, flash/audio events, manual replacements, failed map resolution, delayed polls, config changes, empty maps and shutdown/reinitialization. `tools/verify_celestial_auto_storm.py` runs this alongside the existing module, rain schedule, storm, GM command, PIN-header and alphabetical-source checks. Receipts and matching Release builds are under `Outputs/CelestialDial/auto-storm/`. Offline checks do not establish live automatic-storm acceptance.

### Thunderstorms, darker nights and directional ground shadows (WENV v4)

The user authorized manual thunderstorms first, a darker night comparable to their reference, and moving directional shadows rather than an enhancement of static lightmaps. Normal one-hour day/night and ten-minute-clear/three-minute-rain settings remain unchanged.

WENV v4 retains the existing 80-byte rain-lease layout and adds weather bit 256 (`Thunderstorm`), valid only together with Rain, a nonzero generation, a bounded lease, and the exact `prt_fild08` map. V3 subscribers retain their 80-byte plain-Rain snapshot; v1/v2 lengths and masks remain exact. New clients negotiate v4 then retry v3/v2/v1. The payload container/patch contract remains format 3, independently of the wire version. Both wire headers remain byte-identical.

`@thunderstorm start [1-300 seconds]` starts the server-owned storm layer on `prt_fild08` (default 120 seconds); `stop` and `status` work from other maps. The command has the same console/script/autotrade exclusions as the rain prototype and uses existing GM command permissions. Ordinary rain scheduling remains unchanged; a manually started storm replaces the managed shower, and stopping/expiry starts the next full clear interval. `@thunderstorm stop` does not cancel a separately started ordinary rain shower. No native map weather flags, CWeather effects, shared textures or GRFs are changed.

The server issues native `ZC_SOUND` one-shot cues only to ready, subscribed v4 clients on the storm map: first after two seconds, then at most once per twelve seconds. A delayed poll never replays a backlog. Stop, expiry, map exit and shutdown prevent subsequent cues; an already playing three-second sample can finish naturally. Client effects-volume settings remain authoritative. The original deterministic mono PCM cue is generated by `tools/build_celestial_thunder_audio.py` and installed as `data/wav/boh_thunder_01.wav`, included in the newly signed asset policy. No screen flashes are added. The dial shows the cloud/bolt artwork and `Storm`, retaining concurrent native conditions in the strip.

`CelestialWeatherProcess` wraps the profiled `CWeather::Process` call at `0xC74F71`. Stock runs first; then the wrapper caps its scene RGB outputs at +0x38/+0x3C/+0x40 to 0.34/0.39/0.48 for valid local night, or 0.72/0.76/0.82 for a valid daytime storm lease. Native night flags, blend inputs and ambient effect ownership remain untouched. Terrain/model consumers at `0xA59E8C`, `0xA5A5FC` and `0xA63E8B` use these outputs. HUD canvases are not covered by a dark overlay. Day, indoor/non-nightenabled maps and stale state keep stock computation; reset restores only the wrapper's exact last outputs, avoiding overwrites of another producer. Exact appearance relative to the reference requires live acceptance.

`sun_shadow.inl` supplies a bounded ground-shadow prototype on sunny daytime `prt_fild08`, with direction/length derived from the server's actual day countdown. It runs the native RSM scenery render once normally, then projects a second pass through the real model vertices onto sampled GAT terrain. Only the fresh second-pass frame-pool vertices become translucent black; material UVs and alpha keep leaf cutouts. Model meshes and map geometry remain immutable. All three profiled node formats forward through their original renderer projection/submission functions when the scope is inactive. Scenery fade progression is suppressed only for the duplicate pass and its byte is restored immediately. The workload is bounded to 32 nearby scenery actors and 24000 projected source vertices per frame.

The player path wraps `CPlayer::Draw` once through its profiled vtable slot and captures only that exact actor's native SPR submissions. It preserves the existing sprite-render detours at `0xC4A0D0` and `0xC4A647`, original sprite vertices, colors and UVs, and forwards the original draw. A separate bounded private frame array holds terrain-projected shadow silhouettes, preserving the same texture alpha and animation frame; up to 128 player layers per frame are supported. The `0xC4A65E` bridge reads the original caller's EBP receiver and return-site locals, excluding native ground-ellipse helpers. Other actors, effects and UI calls outside this player scope are not captured.

These are directional **terrain-receiver projections**, not a full GPU shadow map: shadows do not fall onto other models, and there is no inter-object light-occlusion/self-shadow pass. Overlapping translucent faces/layers can accumulate darkness. Coverage is intentionally bounded, and uneven terrain, camera rotation, multi-player scenes and performance require live QA. Rain/storm/cloud/fog/snow, night, stale server state and leaving `prt_fild08` disable the added sunlight pass. Native baked lightmaps and native contact ellipses remain intact.

Tests execute the real server module, extracted GM command, emitted client packet/lighting bridges, real stock SSE lighting calculations, terrain projection, moving sun direction, native player/model forwarding, sprite caller-frame bridge, alpha/UV ownership and original terrain/character-buffer preservation. The native harness initializes the engine's degree sine/cosine BSS tables as startup does. All five patch-order fixtures and the exact supplied-client upgrade remain subject to the complete router/HUD/rain suite. Receipts and staged builds are under `Outputs/CelestialDial/storm-v4/`; signed release/rollback data are under `Outputs/CelestialDial/deployment-storm-v4-20261016/`. Offline checks do not establish live visual or GPU acceptance.

### Live shadow correction, packet-version include fix, and flash/audio revision (WENV v5)

The user confirmed that storms run and the thunder asset plays through `@sound`; the remaining request was a convincing thunder recording and periodic illumination. Read-only server samples showed the cue deadline advancing, and the live client showed protocol 4, weather mask 384 and a fresh rain lease. This was not an established audio-delivery failure. The original synthetic rumble has been replaced with a credited public-domain National Park Service recording: [recording](https://www.nps.gov/subjects/sound/sounds-thunder.htm), [usage information](https://www.nps.gov/subjects/sound/gallery.htm). The source MP3 and credit are under `Inputs/CelestialDial/audio-source/`; the deterministic recipe trims 2.9..11.4 seconds, applies boundary fades/peak normalization, and band-limits to mono 22050 Hz PCM. The normal native effects-volume setting still applies.

WENV v5 retains the 80-byte layout and adds bit 512 (`LightningFlash`), valid only with Thunderstorm + Rain on the prototype map. V4 clients retain Storm without the unknown bit, v3 retains Rain, and v1/v2 remain byte-compatible. The server starts a strike after two seconds, repeats at twelve-second intervals, and issues its audio cue two seconds after each strike. Generation changes mark strike start/clear so current subscribers receive immediate state transitions. Delayed polls create one current strike, never a catch-up burst. Stop/expiry cancel future flashes and pending audio. An already playing recording can finish its natural tail.

The client turns a new strike generation into one 350 ms scene-light pulse (45 ms rise, 305 ms fall) using the existing native scene RGB wrapper. Repeated snapshots cannot restart the same pulse. Peak RGB is 0.94/0.97/1.0; the native HUD remains uncovered. The pulse ends independently of the next packet, and lease loss, map reset and stale state prevent continued storm lighting.

The reported "beheaded" shadow was captured using read-only sprite/queue inspection. Both the HD body and native head were present in the private shadow pool. Their per-vertex reciprocal depths differed because these are rendering/occlusion corrections, not a common physical body plane; interpreting each as physical distance displaced the head's ground projection. Sprite shadow unprojection now derives one reciprocal depth from the actor position and current view for every layer, preserving native source vertices/depth and the accepted sprite artwork. Transparent billboard padding below the logical floor is projected as part of the complete plane; ordinary mesh clipping is unchanged. The captured body/head/view data is checked in at `tools/fixtures/celestial_shadow_hd_depth.json`, and the emitted-code regression requires overlapping screen layers to retain an overlapping ground silhouette.

The shared mirrored-sprite helper is also used by normal character layers. Its blanket exclusion has been narrowed to callers whose parent is the actual native ground-ellipse routine. The naked submit bridge reads a parent frame only for that profiled helper, and regression tests cover mirrored head forwarding, contact-ellipse exclusion and the complete stack/register contract. No SPR/ACT, head attachment, scale or GRF was changed to repair this renderer issue.

`pincode_ui.hpp` previously included `config/packets.hpp` before `config/core.hpp`, selecting stock PACKETVER 20211103 and its renewal-family macros before the custom 20250716 definition arrived. The fix loads core/custom configuration first, in alphabetical include order. A before-case reproduces C4005 and stale renewal-family residue; both PIN-first and core-first compile cases now assert PACKETVER/MAIN_NUM 20250716, no RE residue and correct PIN feature macros. Both full server targets build without C4005. This does not suppress or redefine away the warning.

Builds, read-only diagnostics, before/after proof and regression receipts are under `Outputs/CelestialDial/storm-fix/`; the paired release and rollback are under `Outputs/CelestialDial/deployment-storm-fix-20261016/`. The user subsequently accepted the corrected appearance in game. Broader camera/cleanup/performance acceptance and the later automatic-storm transitions remain separate checks.

### Weather cleanup and bounded-work audit (2026-10-17)

The user accepted every-third automatic storms in game. A subsequent audit used the installed client `dcc8b83dd188a5450c06f26d2837485a003b8784b4434ae9c99e433927b495db` and matching automatic-storm server. The live server was still demonstrating one-minute test intervals, so `@reloadbattleconf` applied the already-restored configuration. The file remained byte-identical to the normal baseline: 3600000 ms day/night, 600000 ms clear and 180000 ms showers. A bounded manual storm was used for the transition checks and allowed to expire naturally; no production binary, map flag or weather asset was changed.

Live observations and read-only process samples verified:

- `/effect` off hid the rain and ground layers while retaining the authoritative Storm dial state; restoring it restored effects. The native character aura followed the same option.
- Warping from an active storm on `prt_fild08` to `prt_in` removed the owned emitter and lease, showed Clear, and retained the native character aura. Returning to the original outdoor position reacquired one emitter and the current storm lease.
- Character selection cleared ready/protocol/weather/emitter state and hid the dial. Re-entering the same character reacquired the active storm and dial without an extra actor effect.
- Natural storm expiry cleared the emitter and lease, restored Clear, and reduced the actor effect count from two to its one-effect native baseline. Global world effects settled from the rain range of 141..154 to 56..57; these global counts also include unrelated native objects.

`tools/test_celestial_weather_lifecycle.py` executes the installed payload for 600 simulated ticks with repeated render toggles, then 36 stop/map-reset/UI-destruction cycles through the native CWorld retirement branch. The peak owned primitive count was 96; the sampled render peak was 320 quads and 192 cached-texture lookups per frame. Hidden draws submitted no geometry or texture lookups. Repeated snapshots/toggles created no duplicate parent. Native ambience, terrain bytes and old-cookie rejection were preserved. Allocation/resource-destructor boundaries are doubles, so this establishes lifecycle eligibility and bounded work, not a native heap-leak proof.

`tools/test_celestial_weather_server_load.py` runs 180 production polls over 1000 isolated sessions, including 1000 map transitions, 200 new session objects, and disconnected/loading/inactive clients. Snapshot output remained bounded to one per session per poll; audio recipients remained ready storm-map clients. Native Snow/Fog flags, existing masks, normal durations and stop cancellation passed. Its transport boundaries are doubles; it is not a live server-capacity benchmark.

The full emitted-client suite, stock scene-lighting tests, directional-shadow tests, and all eight server regression groups passed. Live HUD FPS readings were approximately 130..144 during the inspected scenes, but no frame-time distribution or matched GPU benchmark was captured. Process CPU varied with rendering/loading and cannot establish weather-only overhead. The 45-second expiry sample showed cleanup without a persistent owned emitter; a long-duration soak and dense multiplayer/camera stress remain separate performance coverage.

Evidence is under `Outputs/CelestialDial/lifecycle-audit/`. `tools/sample_celestial_weather.py` uses only process query/read permissions, with no hooks, suspension or memory writes. Its 10 ms frame-tick polling is a sampled update indicator, not a GPU FPS measurement.

The long-duration collector is `tools/soak_celestial_weather.py`. It journals 30-second read-only samples at 250 ms intervals and counts the private parent/primitive vtables in both native world lists. This census distinguishes owned weather from unrelated global effects. It records process resources and refuses to hide map departures, config changes or retained private objects during a clear interval. `tools/analyze_celestial_weather_soak.py` requires an hour of coverage, an observed rain/rain/storm sequence, at least three verified cleanup transitions, bounded private objects, and comparable clear-memory windows after warmup. The 16 MiB retained-memory and eight-handle screens require investigation if exceeded; passing them is not an absolute native-heap leak proof. Raw journals stay under `Outputs/`; a compact acceptance record can be retained under `docs/evidence/` after review.

```powershell
.\.venv-target-hud\Scripts\python.exe tools\soak_celestial_weather.py <client-pid> --minutes 60 --output Outputs\CelestialDial\long-soak\new-run
.\.venv-target-hud\Scripts\python.exe tools\analyze_celestial_weather_soak.py Outputs\CelestialDial\long-soak\new-run
```

## Build and validation

From the WARP repository on the current Windows build host:

The verification environment uses Python with `pefile`, `Pillow`, `unicorn` and `capstone`; regenerating the thunder cue also uses `numpy` and `soundfile`. The native payload build requires the installed MSVC x86 tools. WARP console fixtures require the separately distributed `win32/WARP_console.exe`, the original supported client and the existing HUD asset roots; game EXEs, GRFs, signing keys and generated release folders are not source-control inputs.

```powershell
.\.venv-target-hud\Scripts\python.exe tools\build_celestial_rain_texture.py
.\.venv-target-hud\Scripts\python.exe tools\build_celestial_dial.py --work-dir Outputs\CelestialDial\rain-v3\runtime-final
.\.venv-target-hud\Scripts\python.exe tools\build_target_monster_health_bar.py
.\.venv-target-hud\Scripts\python.exe tools\build_celestial_clients.py --output Outputs\CelestialDial\rain-v3\clients-final
.\.venv-target-hud\Scripts\python.exe tools\build_celestial_server.py --output Outputs\CelestialDial\rain-v3\server-build
.\.venv-target-hud\Scripts\python.exe tools\verify_celestial_dial.py
```

The server build helper stages both Windows binaries under `Outputs/CelestialDial/server-build/bin`. Its local fallback links the complete compiled Release object set with the x64 linker and omits PDB generation when the installed PDB components fail. These Windows validation binaries are not Linux VPS deployment binaries.

The native-code checks cover clock advancement, timezone offsets, 64-bit epoch handling, monotonic tick wrap, fixed/automatic phases, stale and malformed packets, map/reconnect cleanup, alpha composition, click-through behavior, resolution changes and both monster-HUD patch orders. Shared-router regressions execute BPUI/GCHA/WENV routing and the real Gacha open/close/reopen path in both selection orders. The server suite compiles and executes the real module against explicit map-thread/player/transport boundaries.

`tools/verify_celestial_dial.py` writes `Outputs/CelestialDial/rain-v3/verification.json`, including source and payload hashes, matching server build receipts and client preservation evidence. Its optional `--reuse-native-logs` checks hash-bound receipts written by already completed native executions. Live rain acceptance remains separate from the user's accepted v2 dial/cycle/weather display.

## Staged client and deployment

The candidate preserving the supplied installation is:

`Outputs/CelestialDial/rain-visible/candidate/2025-07-16_Ragexe_175220998_clientinfo_patched.exe`

SHA-256: `fae8c500e48cf737f8013d8a7a404315f59470f575038cbd4047c3450e75898a`.

The installation target is `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\2025-07-16_Ragexe_175220998_clientinfo_patched.exe`; each release's deployment receipt records its installed hash. The user supplied a newly patched 31,005,005-byte EXE with hash `c05e563c6bfaa19570161393b3ecb372635e63a1e97b417491a4e5dbb68ed453`. Its exact earlier-v3 payload was recognized and upgraded in place with `tools/upgrade_existing_celestial_payload.py`. Exact old-body matching, relocated exports, lifecycle/frame/receive call targets and private UIWindow vtable entries were verified; every byte outside the owned ranges/allocation headers is preserved. This retains the user's newer unrelated patches. The native clock/phase/weather/rain suite and Riftlock verifier pass on the updated candidates. The visibility revision uses the same allocation as the first wet-look release; no further section growth or asset changes are needed.

The live keepalive fix produced EXE `624320ad12685cdfe552dab5d1721642ef9464a2f3a685c7959a504bd7edd9b5`, which the user confirmed emits particles. The final appearance revision upgrades those exact bytes in place, retaining the same preservation gate. Its signed release and rollback are recorded in `Outputs/CelestialDial/deployment-rain-appearance-20261016/deployment.json`; offline regression evidence is under `Outputs/CelestialDial/rain-appearance/`. The server ordering build receipt is copied there but references the actual staged binaries under `rain-fix/server-build/`. The running map-server was not replaced for these ordering-only changes.

`Outputs/CelestialDial/deployment-resign-supplied-20261016/deployment.json` records the new signed release. Its `rollback/` retains the supplied pre-update files; those came with an older signature that did not cover the supplied EXE. The earlier verified rain release remains in `Outputs/CelestialDial/deployment-rain-v3-final/signed/`. Its original deployment receipt records the private texture installation, and its `rollback/` retains the user-accepted v2 release. When restoring v2, remove the newly added private rain texture and any newly created empty directories so its old loose-tree policy matches again. The original pre-dial release remains under `Outputs/CelestialDial/deployment/rollback/`. No GRF or existing map-weather asset changed.

`Outputs/CelestialDial/package/` preserves the initial functionality package and its narrow `server-source.patch`, deployment README and offline verification receipt. It is historical v1 output. Current weather-v2 source/build/deployment receipts and the server rollback are under `Outputs/CelestialDial/weather-v2/`; client signing and rollback are under `Outputs/CelestialDial/deployment-weather-v2/`.

## In game feedback and artwork revision

On 16 October 2026 the user confirmed the dial works in game and supplied a daytime screenshot. They rejected the initial sun/moon appearance. Artwork revision 2 replaces the small flat glyphs and dotted cream medallion with a larger faceted eight-point gold sun, a shaded silver-blue crescent with small stars, contrasting sky insets and a smooth silver bezel. It uses the same native canvas and bounds.

The user subsequently accepted the revised appearance. The weather-v2 revision retains that artwork and the same window bounds, clock and cleanup behavior, adding weather metadata and a split weather/countdown strip. Native execution tests pass for weather states, legacy fallback, the existing monster positioning shim and legacy protocol forwarding. The server source and both Windows targets must match the new session layout.

`tools/build_existing_celestial_client.py` produces this candidate in an isolated real-WARP fixture. It preserves every original mapped byte except the frame call, the two lifecycle dispatch entries, the WENV receive dispatch entry and the existing monster position call. A new `.celdial` section holds the payload. Imports, IAT addresses, existing GrayMap code, resources and the original overlay are preserved. The fixture's incremental router forwards all non-WENV traffic to the previous installed router.

Rebuild and restart the matching map-server on its actual deployment platform when its gameplay/protocol implementation changes. An older server supplies no WENV state, so the new HUD stays hidden rather than inventing a local clock or phase. Use the existing Riftlock client release/signing workflow for a changed EXE. The dial's own artwork needs no external assets; the v3 rain prototype requires its private loose texture, included in the signed asset policy. No GRF edits are needed.

## Existing client and server behavior

| Surface | Source evidence | Consequence |
| --- | --- | --- |
| Global day and night | Banquet `src/map/pc.cpp:13851` sends `EFST_SKE` according to `night_flag`; `map_day_timer` and `map_night_timer` own changes. | Reuse this state. The dial must not run an independent cycle. |
| Eligible night maps | `npc/mapflag/night.txt`, included by `npc/scripts_mapflags.conf:24`, supplies `nightenabled`; `src/map/clif.cpp:11964` applies or clears night on map entry. | Distinguish global phase from effective local lighting. Indoor or unflagged maps need not become dark. |
| Automatic cycle | `conf/battle/misc.conf` retains defaults; `conf/import/battle_conf.txt` now overrides both durations to `3600000`. | Existing timers initialize a one-hour day / one-hour night cycle at map-server startup; no custom cycle loop is added. |
| Server clock | `src/map/atcommand.cpp:5820`, `@servertime`, uses server `time()` and `localtime()`. | Match that clock in the HUD using server-supplied Unix time and UTC offset. The player's PC clock and game phase are separate. |
| Native weather | `src/map/clif.cpp:1913` maps snow, clouds, clouds2, fog, sakura, leaves and fireworks flags to client effects. `clif_specialeffect_single` sends `0x01F3` at line 10407. | These effects already have a server path. Multiple flags can coexist, so retain a bitmask rather than a single exclusive weather enum. |
| Weather removal | `@clearweather`, `src/map/atcommand.cpp:7725`, clears flags and replays enabled weather. Its message explicitly says effects dispel on warp or refresh. | A seamless transition needs verified native stop calls or effect removal. Clearing flags alone is insufficient. |
| Rain | `MF_RAIN` and `@rain` are commented out in `src/map/map.hpp:648` and `src/map/atcommand.cpp:7577`. `EF_RAIN_PARTICLE` and `EF_RAIN_PARTICLE2` still exist in `src/map/script.hpp`. | Do not restore the old flag and assume rain works. Probe newer particles for duration, coverage, attachment and cleanup. |
| Thunder | `EF_THUNDERSTORM` and `EF_THUNDERSTORM2` are special effects also used by quest and skill scripts. | Their names do not establish persistent environmental storms. Avoid confusing environmental lightning with combat effects. |
| Map ambience | WARP `Scripts/Extensions/GenMapEffectPlugin.qjs` documents native map-initialization calls for clouds, snow, leaves, petals, fireworks and night. `EnableEffectTool` is selected in the main profile. | Ambient effects can exist without weather flags or a custom server scheduler. |
| Native HUD | `Scripts/Patches/AutoCombatUI.qjs` profiles native frame, image, text, renderer and packet helpers. `GachaUI.qjs:918` clones a private frame vtable. | A dedicated native HUD window is a suitable implementation pattern. It need not depend on enabling the AutoCombat gameplay feature. |

No dedicated dynamic weather controller was identified in the checked NPC scripts. Static inspection establishes available paths; live weather appearance and the remote server's effective settings remain acceptance items.

## Deployed client evidence

The supplied game folder is `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes`.

The inspected pre-dial EXE was `2025-07-16_Ragexe_175220998_clientinfo_patched.exe`, SHA-256 `3767fff7ffec4b779a4031facb60f204961792102d2044f0f1ac2ea5feac83ba`; those bytes are now in the rollback bundle. The original WARP input is a 32-bit PE at image base `0x00400000`, SHA-256 `ead7c0a316bc6c27705a5a6876daf5093abec31677f3c1af7525c1709b201bff`.

The deployed EXE contains the `RIFTLOCK_GRFS_V1|embedded|` configuration marker, specifying this priority order:

1. `dual_weapon_male_assets.grf`
2. `update.grf`
3. `maindata.grf`
4. `mapdata.grf`
5. `palettedata.grf`
6. `spritedata.grf`
7. `data.grf`
8. `greyworld.grf`

All eight archives exist. The external `DATA.INI` lists only update, maindata, spritedata and data; changing that file does not change the embedded list. `Scripts/Patches/MultiGRFs.qjs:294` defines the embedded-loader pattern and marker.

Reading archive tables found 988 file entries under `data/luafiles514/lua files/effecttool/` in `mapdata.grf`. Its `prontera.lub` is 18,440 bytes of Lua text and includes particle emitters using `smoke2.bmp`; this is ambient content, not proof of dynamic rain. `maindata.grf` contains a 14,762-byte `data/fogparametertable.txt`. No loose EffectTool override was found under the inspected `data/luafiles514` tree.

On the original input, the `CustomSound.qjs` update-loop pattern identifies the likely `g_Weather` receiver `0x015C57D8` and processing call `0x00C136A0` at `0x00C74F6C`. The native `0x01F3` dispatcher entry resolves to `0x00CA64A0`. These are reverse-engineering leads; weather start/stop ABIs still need explicit profiling and live validation before calls are emitted.

## Future presentation extensions

Use a compact pale silver frame with blue-grey edging, native Tahoma text and a small gold celestial medallion. Render the clock as native text so the UI can localize labels and update seconds without regenerating artwork. Final sun, moon and weather art should be small sprites in the same style as native interface icons; the interactive concept uses schematic icons.

The implemented left wing displays `World / Day` or `World / Night`; the right wing displays `Server time / HH:MM:SS` and the actual UTC offset. The first version is passive. A later interactive medallion could open map conditions and local effect preferences. A weather forecast should appear only when the server has scheduled one.

The concept's `UTC+08:00` and clock value are examples. The actual timezone comes from the game server, not the desktop's timezone.

The implemented dial occupies Y=8 through 106; the monster HUD begins at Y=114 while the dial is visible, leaving an eight-pixel gap. It returns to Y=24 when the dial hides. Native execution tests cover this reservation; in-game placement is still a live visual acceptance item. Future interactive controls must preserve pass-through input outside their actual hit regions.

## Future managed weather connection

The implemented `WorldEnvironment` module publishes existing state on the map thread. Weather scheduling can follow after live acceptance. A managed map profile should distinguish inherited ambience, server-managed effects and explicit instance or event overrides. Unknown inherited ambience must not be labelled `Clear` just because server weather flags are zero.

WENV v2 adds existing weather flags through the framed custom-UI transport, preserving v1, BPUI/GCHA and the stock fallback. Further scheduling fields require another negotiated version; do not reinterpret an existing consumer's payload. Keep exact length and version checks.

Send environment snapshots only after a patched client subscribes. Send again after map entry, phase/weather changes and a bounded time resync, for example every 60 seconds. A snapshot should carry:

- Protocol version, server/session generation, sequence, request echo and map/instance generation.
- Server Unix time and signed UTC offset, separate from game phase.
- Global day/night, local night eligibility, schedule-present flag, current phase duration and actual remaining time.
- Inherited/managed ownership, weather bitmask, primary display condition, intensity and transition duration.
- Optional scheduled next weather; otherwise show `Unscheduled`.

Use server time plus client monotonic elapsed time to advance the display. For an echoed resync, account for request round-trip delay; do not use the player's wall clock. Handle unsigned `timeGetTime` wrap, bound extrapolation when disconnected, reject stale map/session updates and resync after reconnect. Update text once per second; draw calls do not send packets. Use the existing timer deadlines for phase remaining time, especially after `@day` or `@night`; do not assume those commands restart the periodic schedule.

Use one phase authority. The first implementation should retain `map_day_timer`, `map_night_timer` and their commands. Dawn and dusk could later become cosmetic transitions around these state changes. If a persistent or wall-time schedule is introduced, migrate timer ownership explicitly rather than adding a competing loop. Multiple map-server processes would also need a shared phase epoch or coordinator.

## Future weather client work

The implemented `CelestialDial.qjs` is independent of enabling AutoCombat gameplay. Retain its private native canvas, static WARP-time bridges and post-reader dispatcher when adding weather. Preserve the no-`recv`-hook boundary.

V1 draws its panel and sun/moon directly. If future weather artwork uses external resources, load those through the native loose-file/GRF loader. Persist new cosmetic preferences through the existing settings pattern without changing server phase or gameplay state.

Before changing weather, profile the native weather controller's start/stop functions and map-reset behavior. Preserve baseline clouds, particles and fog when ending a managed rain or wind layer. Apply a state change once per generation; repeated snapshots must not spawn duplicate emitters. `/effect` and map changes need explicit acceptance checks. Stock night tint should remain the first implementation; smoother illumination is a separate renderer change.

The existing native frame helpers are profiled for 2025-07-16. Supporting 2026-02-19 requires separate UI and weather profiles; the presence of a packet-dispatch profile alone does not establish full compatibility.

## Weather implementation order and acceptance

1. Add the native dial, server subscription, server clock and actual global phase. Verify fixed-day and fixed-night display before enabling a cycle.
2. Connect existing phase timers and native weather flags. Verify `@day`, `@night`, map entry, relogging and clock agreement with `@servertime`.
3. Add managed weather ownership and verified immediate stop/start behavior. Preserve Prontera particles, Lutie snow and map fog through transitions.
4. Probe rain particles on a controlled map. Accept only after start, stop, map coverage, camera movement, warp, relogging and `/effect` behavior are demonstrated. Add wind audio and thunder separately; leave flashes optional.

Offline checks should cover exact packet bounds and versions, stale map/session rejection, clock arithmetic and tick wrap, fixed phases, duplicate snapshots, router composition with BPUI/GCHA in both selection orders and missing assets. Run the bridge IAT verifier if shared imports change. Keep changes away from shared item/title rendering.

Live acceptance must show the dial with the monster HUD at supported resolutions, correct server time from two PCs with different local clock settings, phase changes on eligible maps, unaffected indoor maps, effect teardown without warp, preserved baseline ambience, and reconnect cleanup. Static source and binary inspection do not establish that visual acceptance.

## Interrupted long-duration baseline

The initial read-only soak ended after approximately 46 minutes when the user intentionally restarted the client. User movement and UI activity also changed scenery/cache residency during the run. Its three observed rain/rain/storm cleanups are partial evidence only; it is not an accepted one-hour memory/performance test. A fresh stationary acceptance run is required on the deployed per-map revision before committing. Raw partial evidence remains under `Outputs/CelestialDial/long-soak/run-20261017/`.

The per-map revision is installed with client SHA-256 `5d1d4faf3065a27655e9404357af8beb697ede907959fa9c39ccc15aba3cbc36` and independently verified Riftlock release `1792192166`. Both matching Windows server targets were rebuilt and installed with the YAML defaults above. The complete offline matrix and paired client/server rollback receipts are under `Outputs/CelestialDial/profiles-v6/`. The fresh long-duration acceptance test passed; see the accepted evidence below.

## Accepted v6 stationary soak (2026-10-17)

The new client completed a 60.05-minute read-only run on `prt_fild08`, using WENV v6 throughout and retaining the exact stationary position and normal configuration. The sampled sequence was rain, rain, storm, rain, rain; all four completed showers returned the private emitter and particle counts to zero. Peak ownership stayed at one emitter and 96 primitives. All 109 world-list censuses were stable, all sampling windows observed updates, and there were no read errors or configuration/movement failures. The automatic day-to-night transition was observed with a 3600000 ms phase duration. The final rain was still active when the hour ended.

After warmup, comparable clear-window private-memory medians were 850.688, 853.012, 854.836, 854.902 and 854.797 MiB. The last minus first median was 4.109 MiB; the final two differed by -0.105 MiB. Median clear-window handles fell from 681 to 589. Transient clear-period peaks subsided. This passes the bounded cleanup/memory screening gates; it does not establish universal heap-leak freedom or GPU frame-time performance. Sampling used 250 ms polls in 109 approximately 30-second windows, with process-launch gaps between them.

Durable summary: `docs/evidence/celestial-weather-soak-20261017.json`. Raw journal, collection and analysis: `Outputs/CelestialDial/long-soak/profiles-v6-header-run-20261017/`. The official rAthena YAML GPL/banner/schema headers were corrected before this accepted run, with the complete YAML bodies preserved byte for byte. The original interrupted runs remain incomplete historical evidence.
