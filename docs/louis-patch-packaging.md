# Louis customer patch packages

The first migration supports **Ping**, **FPS**, and **FPS + Ping** on the profiled
2025-07-16 Ragexe. Other products are not yet registered in this package catalog.
The existing full WARP distribution continues to load both feature scripts.

## Seller workflow

Run from the WARP repository:

~~~powershell
python tools/package_louis_patches.py --feature ping --output Outputs/customer-packages/Louis-Ping-1.0.0.zip
python tools/package_louis_patches.py --feature fps --output Outputs/customer-packages/Louis-FPS-1.0.0.zip
python tools/package_louis_patches.py --feature ping --feature fps --output Outputs/customer-packages/Louis-FPS-Ping-1.0.0.zip
~~~

Existing archives are never overwritten. Choose a new output filename for another
build. Archive contents, file order, timestamps and permissions are deterministic.

The builder reads packaging/louis/catalog.json, resolves transitive module
dependencies, and includes only selected feature files, required support,
generated WARP registrations, installer, optional setting snippets, license and
instructions. It does not copy this customized checkout into a customer's package.

A Ping sale contains these managed WARP files:

- Scripts/Patches/PingOverlay.qjs
- Scripts/Patches/CustomSlashCommand.qjs
- Scripts/Support/Class_NativeTelemetry.qjs
- Patches/LouisTelemetry.yml

It contains no FpsOverlay.qjs, FPS sampling implementation, extended-name
implementation, other paid UI, custom DLL, client EXE, or image assets.
The common state layout retains reserved slots so combined packages use the same ABI.

## Customer installation and upgrades

Extract the ZIP outside the customer's WARP folder, close WARP, and run:

~~~powershell
python install.py --warp "C:/path/to/WARP" --check
python install.py --warp "C:/path/to/WARP"
~~~

Python 3.10+ is sufficient; the installer has no third-party dependencies.
The first command performs the complete preflight without changing the destination.

The installer merges the category include into Patches.yml and patch IDs into
Tables/Patch.yml. IDs 45000 and 45001 are used for these customer packages;
collisions are refused. The category explicitly permits simultaneous selection.

A lock file records features, support versions and managed hashes. Reinstalling
the same package is a no-op. Send **one cumulative package** when a customer adds
another feature. The installer refuses partial replacements, older versions,
unmanaged conflicts, changed installed files and changed shared code without a
module version bump. It stages each file replacement and rolls back completed
writes if an installation write fails.

Existing pre-modular copies of these custom scripts are not automatically migrated.
Use a separate clean WARP copy; the installer refuses to overwrite those unmanaged
files or duplicate their existing metadata registrations.

The installer does not edit player settings or deploy an EXE. The customer selects
the purchased patches, chooses their coordinates/font, and builds a new EXE from
the supported original client. /ping and /fps toggle their respective features.
Optional runtime-options.lua entries can be merged into the existing
savedata/OptionInfo.lua after its CmdOnOffList table definition.
A replacement Game Settings Lua bundle is not included.

## Module contract

Class_NativeTelemetry.qjs exposes support API 1 / version 1.0.0. Feature scripts
register their channel descriptions while WARP loads scripts. Loading a module
does not patch an EXE. The support file is loaded from WARP's Support directory
before the feature scripts.

The core owns integer formatting, GDI drawing, font selection, shared state
and the post-Present bridge. FPS frame sampling and its presentation policy live
in FpsOverlay.qjs. Ping capture and latency color policy live in PingOverlay.qjs.

The original six-byte store at 0x00543441 is replayed before the bridge executes;
the bridge returns to 0x00543447. Ping preserves the original ECX assignment at
0x00C9E8F8, returning to 0x00C9E8FD, and captures the stock packet RTT.
There are no additional imports, receive hooks, runtime trampolines or DLLs.

WARP tags replace earlier writes when reopened. Runtime allocation and per-channel
configuration therefore use separate tags. Removing one feature clears its own
configuration and slash command while retaining the shared renderer for remaining
users. Removing the final feature restores the Present hook and clears shared state.
Failed feature construction releases any shared registration it obtained.

CustomSlashCommand.unregister refreshes the generated dispatcher before the
feature's private callback allocation is cleared. The dispatcher also
initializes its own named cache tag; it does not depend on unrelated patches
initializing support.

When changing support files, bump the appropriate module version in the catalog.
Change ApiVersion and feature requirements for incompatible descriptor/layout
changes. Every archive must contain matching feature and support code. Patch IDs
are stable across customer upgrades.

## Verification

~~~powershell
python tools/verify_louis_package_installer.py --output Outputs/customer-packages/installer-check
.\.venv-target-hud\Scripts\python.exe tools/verify_telemetry_packages.py --base ..\WARP0716 --output Outputs/customer-packages/native-check
~~~

The native verifier requires pefile and unicorn. It uses a **fresh output
directory**, creates ZIPs with the production builder, installs them into isolated
WARP fixtures, and runs WARP_console.exe. Single-feature fixtures physically
omit the other feature's script. The verifier rejects cancelled builds and
unexpected WARP errors rather than trusting the process exit status.

Cases cover Ping-only, FPS-only, both application orders, removal of either
feature, removal of both, reapplication, and injected Ping failure with FPS active.
Generated x86 is executed with emulated Windows/native option APIs. Checks cover:

- Packet RTT capture and stock ECX replay.
- Present register/flags preservation and the original result store.
- Ping text, coordinates, color thresholds, and FPS sampling.
- Balanced DC acquisition/release, enable flags and native option toggles.
- Actual slash dispatch, settings option lookup, unknown-command fallback,
  and inactive callbacks after removal.
- Unchanged PE imports and correct hook restoration.

The probe tracks successful operations separately from WARP's selection state:
a selected patch can be in an error state. Every expected runtime state is checked
against the exported bytes and executed dispatcher.

Installer checks cover exact Ping source dependencies, QJS encoding, deterministic
archives, dry runs, idempotent installation, preserving existing registrations,
cumulative upgrades, version mismatches, tampering and conflicts.

A separate integration build loads the current complete repository's scripts in
an isolated copy and executes the combined telemetry bridges. These checks do not
establish live Ragexe rendering acceptance. Before a customer release, check the
actual overlay in game, /ping or /fps, font/position, map transitions and exit.

## Following migrations

Extend the catalog after extracting each feature's real dependencies:

1. Move ExtNameStaticAsm out of CustomExtName.qjs; separate neutral text
   infrastructure from the extended-name adapters.
2. Extract AutoUILanguage from AutoCombatUI and consolidate the shared
   0x0BEF router used by Auto Hunt, Auto Support, PIN and Collection.
3. Separate item-title rendering from item-color, grade-color and label policies.
   This migration must preserve the normative item/grade contract and repeat its
   complete two-client/live visual acceptance matrix.
4. Register the remaining UI, theme, payload and asset dependencies explicitly.

Optional cross-feature callbacks must not force distribution of another product.
A package being syntactically complete is insufficient: validate the exported
subset in isolation and validate combined ownership before adding it to the catalog.
