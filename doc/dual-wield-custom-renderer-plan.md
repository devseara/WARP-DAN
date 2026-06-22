# Dual-Wield Custom Renderer Plan

Target: `2025-07-16_Ragexe_175220998`, Banquet of Heroes.

## Decision

Switch away from native dual-wield weapon-layer hooks. The master reference now
shows the tested Assassin Cross body ACT does not contain individual weapon
layers for item-specific types `34` (`_1238`) or `45` (`_13412`), and the
client's `DrawWeapon` path is arrow/projectile-specific for this case.

The renderer work should therefore be a separate renderer owned by
`boh_weapon_sprite.dll`, with native EXE probes disabled by default.

## Current Prep

- `boh_weapon_sprite.dll` is the renderer host loaded by
  `AllowDualCustomWeaponSprites.qjs`.
- `BOH_DUALWPN_NO_HOOKS=1` is the safe default; inline EXE hooks are opt-in.
- `BOH_DUALWPN_OVERLAY=1` starts `weapon_overlay.cpp`.
- `weapon_overlay.cpp` now owns a first-pass renderer: it tracks the game
  client window, hides while the game is inactive or minimized, waits for
  read-only actor render state, decodes loose paletted SPR frames, pre-composes
  loose ACT+SPR weapon frames, and draws a main/offhand pair at the client
  center only when exact item assets are available.
- `tools/dual_weapon_act_preview.py` renders extracted ACT/SPR pairs offline.
  It successfully rendered Shadow Cross and base Assassin `_1238` / `_13412`
  pairs from `tmp/dual_weapon_exact`; the first verified nonblank weapon band
  is actions `32..39`.

## Renderer Milestones

0. Safe default.
   - `BOH_DUALWPN_NO_HOOKS=1`.
   - `BOH_DUALWPN_STATE_HOOKS=0`.
   - `BOH_DUALWPN_ALLOW_FALLBACK_SPR=0`.
   - Result: no login-screen weapons, no demo art, no inline EXE hooks.

1. Select exact assets.
   - Real `_1238` and `_13412` `.spr` plus matching `.act` files exist in
     `spritedata.grf`; extraction into `tmp/dual_weapon_exact` produced 142
     ACT files and 142 SPR files for the two target IDs.
   - Required before visual testing: choose the correct job/gender pair for
     the current actor, then load that matching ACT+SPR pair.
   - Do not use Drake fallback art except to test the overlay compositor.
   - Stop condition: repo/tool output lists the selected ACT/SPR pair and its
     frame/action counts.

2. Parse ACT + SPR together.
   - SPR-only drawing is not valid for this goal; it proves pixels only.
   - ACT parsing must provide action, direction, frame index, x/y offsets,
     mirroring, scale, rotation, and alpha/color fields needed by RO sprites.
   - Status: offline preview passes for Shadow Cross and base Assassin target
     pairs; the current C++ overlay pre-composes offset/mirror-only ACT frames.
   - Remaining for full fidelity: pass live action/direction/frame state rather
     than cycling the verified `32..39` action band.

3. Keep the overlay renderer stable.
   - No EXE inline hooks by default.
   - Clean thread shutdown on DLL unload.
   - Reacquire the game window if it is recreated.

4. Source actor presentation data.
   - Only after milestone 2 passes, enable `BOH_DUALWPN_STATE_HOOKS=1` or
     replace it with a safer non-inline source.
   - Required fields: actor screen position, direction, action/motion, frame
     tick, main/offhand item slots.
   - Do not mutate render mode, `[char+0x24C]`, or submit state.
   - Stop condition: DebugView state lines update only in-game, not at login,
     and Alt-Tab does not hang.

5. Draw per-hand weapon overlays.
   - Current: load loose ACT files from `BOH_DUALWPN_MAIN_ACT` /
     `BOH_DUALWPN_OFF_ACT`, or search `data\sprite` for exact item-id names
     such as `_1238.act` / `_13412.act`; raw SPR loading remains a fallback.
   - The overlay does not read GRFs directly. GRF-only assets must be extracted
     to loose `data\sprite` files or supplied through explicit ACT paths.
   - Drake sword/dagger fallback art is opt-in only through
     `BOH_DUALWPN_ALLOW_FALLBACK_SPR=1`.
   - Start with idle/walk frame alignment.
   - Add attack-frame timing after direction/action mapping is stable.
   - Draw main and offhand independently with per-item suffix frames.

6. Decide whether to stay layered-window or move into D3D.
   - Layered window is fastest and safest, but has no scene depth.
   - In-scene D3D can solve occlusion later, after the asset and actor-state
     pipeline is proven.

## Do Not Reopen

- `BOH_DUALWPN_SYNTH_DRAW` as a fix.
- `BOH_DUALWPN_SUPPRESS_NATIVE_SUBMIT` as a fix.
- Mode `9 -> 2` remaps as a fix.
- `[char+0x24C]` resource-key forcing as a fix for mode 2/9.
