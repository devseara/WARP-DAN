# Louis customer patch packages

Release **1.1.0** supports **Ping**, **FPS**, **Fluent Emoji**, **Player Name Colors**,
and **128-byte Entity Names**, individually or in cumulative packages, on the
profiled **2025-07-16 Ragexe**. Item colors/grade policies and Auto UI products
are not yet registered. The existing full WARP distribution remains compatible.

The user confirmed that the 2026-02-19 client is no longer in their current scope.
This migration is verified for 2025-07-16 only. Existing 2026 profile definitions
remain available, but this release makes no new 2026 validation claim.

## Seller workflow

Run from the WARP repository:

~~~powershell
python tools/package_louis_patches.py --feature ping --output Outputs/customer-packages/Louis-Ping-1.1.0.zip
python tools/package_louis_patches.py --feature fps --output Outputs/customer-packages/Louis-FPS-1.1.0.zip
python tools/package_louis_patches.py --feature ping --feature fps --output Outputs/customer-packages/Louis-FPS-Ping-1.1.0.zip
python tools/package_louis_patches.py --feature emoji --output Outputs/customer-packages/Louis-Emoji-1.1.0.zip
python tools/package_louis_patches.py --feature player-colors --output Outputs/customer-packages/Louis-Player-Colors-1.1.0.zip
python tools/package_louis_patches.py --feature extended-names --output Outputs/customer-packages/Louis-Extended-Names-1.1.0.zip
python tools/package_louis_patches.py --feature ping --feature emoji --output Outputs/customer-packages/Louis-Ping-Emoji-1.1.0.zip
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

An Emoji-only sale contains FluentEmoji.qjs, ExtNameTextStatic.qjs,
Class_StaticAsm.qjs and LouisRuntime.qjs, its generated category, and the declared
Images/BohEmoji/fluent asset tree. It excludes CustomExtName.qjs, EntityTextStatic,
CustomPacketDispatch, NamePackets128Static and the 23 native name-adapter files.
WARP copies the 3,145 PNGs and accompanying manifest/license beside the client.

Player Name Colors adds the shared entity map and EXTN/ICOL dispatch support but
still excludes the 128-byte name feature and its native adapters. Extended Names
adds those adapters explicitly. Both server-driven features require their matching
server protocol; customer ZIPs contain client code and do not install server changes.

## Customer installation and upgrades

Extract the ZIP outside the customer's WARP folder, close WARP, and run:

~~~powershell
python install.py --warp "C:/path/to/WARP" --check
python install.py --warp "C:/path/to/WARP"
~~~

Python 3.10+ is sufficient; the installer has no third-party dependencies.
The first command performs the complete preflight without changing the destination.

The stable Patches/LouisTelemetry.yml filename is retained for upgrades from 1.0.0;
its category now displays all purchased custom products. The installer merges
the category include into Patches.yml and patch IDs into
Tables/Patch.yml. IDs 45000 through 45004 are reserved for these customer products;
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

## Text module contract

Class_StaticAsm.qjs owns the x86 assembler previously embedded in CustomExtName.
The existing ExtNameStaticAsm name is retained so all current consumers keep their
API. The assembler implementation is unchanged.

ExtNameTextStatic owns generic TextOut/extent composition and exposes the original
helper entry points. Optional calls delegate to EntityTextStatic for the bounded
EXTN map/frame receiver, and to NamePackets128Static for native 128-byte packet
adaptation. The latter module declares all 23 name-adapter files as dependencies.
These modules expose API 1 / version 1.0.0. Their code-generation algorithms and
allocation order are preserved.

LouisRuntime.qjs runs after the normal initializer and fills missing 2025 profile,
allocation and static-refresh helpers on the clean upstream base. It preserves
existing definitions in the full distribution and performs no EXE writes.

The item/grade verifier reads the relocated entity-map code in addition to the
shared bridge. Its behavioral assertions remain intact. The matrix runner still
requires both clients by default; --only-2025 explicitly selects the eleven-case
matrix appropriate to the user's current client scope.

## Verification

~~~powershell
python tools/verify_louis_package_installer.py --output Outputs/customer-packages/installer-check
python tools/verify_text_package_installer.py --output Outputs/customer-packages/text-installer-check --previous-ping Outputs/customer-packages/releases/1.0.0/Louis-ping-1.0.0.zip
.\.venv-target-hud\Scripts\python.exe tools/verify_text_packages.py --base ..\WARP0716 --reference-ref b6584b3 --output Outputs/customer-packages/text-check
.\.venv-target-hud\Scripts\python.exe tools/verify_item_grade_matrix_warp.py --only-2025 --output Outputs/customer-packages/item-grade-check
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

The text package verifier compares complete before/after EXEs against the specified
reference commit, exercises the production emoji match entry and entity text/color
code, checks dark passes and HDC restoration, and verifies copied PNG hashes.
A complete-bundle case also executes the FPS/Ping code alongside all text features.
Live acceptance is recorded as the user's "all working" report on 2026-09-15 for the current 2025-07-16 client.

## Following migrations

Extend the catalog after extracting each feature's real dependencies:

1. Extract AutoUILanguage from AutoCombatUI and consolidate the shared
   0x0BEF router used by Auto Hunt, Auto Support, PIN and Collection.
2. Separate item-title rendering from item-color, grade-color and label policies.
   This migration must preserve the normative item/grade contract and repeat its
   complete two-client/live visual acceptance matrix.
3. Register the remaining UI, theme, payload and asset dependencies explicitly.

Optional cross-feature callbacks must not force distribution of another product.
A package being syntactically complete is insufficient: validate the exported
subset in isolation and validate combined ownership before adding it to the catalog.
