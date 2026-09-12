# HD Job Sprite Previews — implementation and local reference

Updated: 2026-09-12. Target: **2025-07-16 Ragexe, 32-bit x86**.

This is the consolidated session reference for the diagnosis, generated assets,
local implementations, deployment, verification and renderer alternative.
**PR preparation is stopped at the user's request.** No PR was opened and the
prepared branch was not pushed. The local checkout and recovered assets remain
available for use; they have not been merged into the main checkout.

## Diagnosis and current approach

World rendering honors ACT layer scaling, while the native Equipment (Alt+Q)
and Skill Tree (Alt+S) blits ignore it. A SPR with four times the pixel dimensions
and ACT scale 0.25 therefore looks correctly sized in the world but four times
too large in these previews. The supplied male/female clan Swordman pairs use
4x pixels and ACT scale 0.25. The supplied male Monk high pair uses 2x pixels and
ACT scale 0.5.

The implemented solution preserves the HD world SPR/ACT pair and generates
separate native-size preview and stock-fallback pairs. Only the nine profiled
UI resource-load calls are redirected. There is no runtime sprite resizer.

The conversion is generalized by **actual ACT layer scale**, not by a fixed
job-ID table or an assumed 4x resolution. It supports nonuniform axes,
noninteger factors and per-frame scale changes. It cannot infer an intended
world size if the source ACT's own scale is incorrect. Camera zoom and other
runtime world transformations are not reproduced in UI windows.

## Why Assets/HDJobUI is required

Removing generated assets from Git did not remove the patch's dependency on
those assets. The pack contains `manifest.json` plus native-size preview and
fallback SPR/ACT files. The missing-pack error is an active precondition, not
a stale diagnostic. Removing that check would leave the patch without its
resource map and required files.

Each affected job/sex resource pair discovered in the supplied source chain
gets a manifest entry. Already-native pairs do not require a route. Identical
preview/fallback sets can be shared by several resource paths. This does not
automatically cover future HD additions:

- New resource paths require regenerating the pack and reapplying the patch.
- Artwork or ACT changes at existing paths require regenerating and deploying
  the corresponding pack files, then restarting the client. The cleaned
  implementation needs no QJS rebuild when only the pack changes.
- Generate all intended resources together; generation replaces the manifest.
  Packaging and routing use its referenced files.

The existing local audit resolved **2,206 complete body pairs**: 61 with
non-unit ACT scales and 2,145 with native scales. The generated pack has
**61 resource mappings, 18 unique preview/fallback sets and 72 SPR/ACT files**.
These are resource counts, not 61 distinct HD jobs. Some non-unit scales belong
to stock animations. Ten ACT-only paths lacked a matching SPR in the supplied
chain and were reported as unpaired rather than assigned substitute artwork.

The pack was retained in the main checkout and Downloads WARP installation,
and has now been restored into the cleaned local checkout. All 72 restored
file hashes, visible ACT scales of 1.0 and image references were checked.
`Assets/HDJobUI/` remains Git-ignored.

## Local copies and implementation differences

| Copy | Resource mapping | Supported starting layout |
| --- | --- | --- |
| Main checkout: `Scripts/Patches/HDJobSpritePreviews.qjs` | Earlier generated QJS embeds the pack's mapping/file lists; rebuild QJS after changing that map | Stock or the specifically verified ClanBodySkins v11 bridges |
| Cleaned local checkout: `Outputs/hd-job-ui-pr/` | Reads `Assets/HDJobUI/manifest.json` at WARP apply time; no deployment-specific map is built into QJS | Verified stock UI CALLs only; changed calls or native prologues are rejected |

The cleaned copy is retained on local branch
`codex/hd-job-sprite-previews-upstream`, commit `c2856b8`, based on upstream
commit `48dde10`. Its folder name reflects the earlier preparation; no PR is
being pursued. It still contains the patch, converter, native source and
verification tools. The existing main-checkout implementation was not replaced.

The sections below describe the cleaned copy unless explicitly marked as
legacy. Run its commands from `Outputs/hd-job-ui-pr/`. Its generated pack is
at `Outputs/hd-job-ui-pr/Assets/HDJobUI/` relative to the main checkout.

## Generate and deploy a pack

Use Python 3.10+. Install `tools/requirements-hd-job-ui.txt` for the full build
and verification workflow; asset conversion itself requires Pillow.

```powershell
python tools/hd_job_ui_assets.py --source-grf HD.grf --source-grf data.grf --stock-grf stock.grf --output Assets/HDJobUI --write-config Outputs/hd-job-ui/resolved.json
```

Repeat `--source-grf` and `--stock-grf` in their respective highest-first
priority orders. Supply the archives that the client actually loads. SPR and
ACT resolve independently, so an ACT override can pair with a SPR from a
lower-priority archive. Native overrides shadow lower-priority scaled assets.
Archive tables remain open during generation and close afterward.

Optional `--sprite-root data/sprite` roots take precedence over source GRFs;
omit them for archive-first clients. Discovery recognizes species/body
`*/몸통/` paths, including human, Doram and prefixed body resources, and excludes
the generated preview namespace. It requires a complete stock fallback for
every selected body. Loose filenames may use decoded Korean or supported
legacy Latin-1 mojibake names. Unpaired ACT paths appear in the saved config.

For aliases, custom layouts or explicit artwork assignments, use an explicit
map based on `Inputs/HDJobSpritePreviews.example.json`:

```powershell
python tools/hd_job_ui_assets.py --config my-job-sprites.json --output Assets/HDJobUI
```

Source/fallback specifications support a local `path` stem, a `grf` plus `stem`,
or separate `spr` and `act` specifications when files come from different
sources. Stems omit extensions. The earlier normal-Monk test used an explicit
artwork alias because the client requested `몽크_남` while the supplied HD file
was named `몽크_h_남`; this was a resource-map decision, not special scaling code.

Select **Native-size HD Job Previews (Alt+Q / Alt+S)** in WARP. The cleaned
patch reads the manifest, validates version, bounds, unique routes and complete
file lists, and checks file presence before changing the EXE. It copies the
referenced files beside the output EXE under `data/sprite/hd_job_ui/`.
Reapply from a compatible original input when changing the resource map.

The converter validates fallback scales and image references. WARP validates
manifest structure and file presence; it does not recompute file hashes.
Deploy the converter's preview and stock files together. Keep the namespace
unique so a stale copy in a higher-priority GRF cannot take precedence.

For archive deployment, package the same generated UI files:

```powershell
python tools/package_hd_job_ui_grf.py --assets Assets/HDJobUI --output Outputs/hd-job-ui/hd_job_ui.grf
```

Register this archive through the client's active GRF loading mechanism.
The cleaned UI patch and packager do not edit DATA.INI or an embedded archive
list, and the UI pack contains no world artwork. Install the original HD world
resources separately. An external DATA.INI change alone is ineffective if the
client uses an embedded archive list.

## Conversion and alignment contract

For every visible ACT layer, generate:

```text
UI width  = max(1, floor(source width  * scaleX + 0.5))
UI height = max(1, floor(source height * scaleY + 0.5))
UI scaleX = UI scaleY = 1.0
```

Reused images with different logical dimensions receive additional variants;
only the referring image indices change. Integer raster rounding can differ
by half a pixel per axis. Action/frame ordering, frame headers, timing, sounds,
head anchors, mirror, rotation and color are preserved. ACT 2.5 dimension
fields are updated to match the generated images.

The profiled loader computes:

```text
loaded_offset = trunc(file_offset / layer_scale)
                - floor(source_image_dimension / 2)
```

World geometry subsequently applies the layer scale. Exported UI ACT X/Y
coordinates therefore remain the original logical offsets. **Do not multiply
them by the HD multiplier again**; doing so double-applies the conversion and
breaks head/body alignment.

Resampling uses premultiplied-alpha Lanczos. Truecolor SPR pixels are bottom-up
ABGR. Indexed sprites retain the original palette and reserved transparent
index zero; resampling is quantized back to that palette with binary alpha.
Stock fallback ACT scaling, if present, is baked into its separate native-size
copy using the same rules. Original world files remain unchanged.

Supported formats are SPR 2.0/2.1/2.2 and ACT 2.4/2.5. Invalid indices,
unsupported formats, nonpositive/nonfinite scales and excessive dimensions
fail generation. Limits are 2,048 resource routes, 65,535 variants per image
type, 4,096 pixels per output axis and 64 million output pixels per pair.
The generated manifest records mappings, scales and source/output hashes.

## Native resource routing and ABI

Only the four Equipment and five Skill Tree CALL sites below are redirected.
The cleaned patch checks their original bytes and six native function
prologues before allocation or mutation. Other client builds need independent
function identification, ABI profiling and byte verification.

| UI | CALL addresses | Native loader and ABI |
| --- | --- | --- |
| Equipment | `0x7ACD71`, `0x7ACDB1`, `0x7AEC6B`, `0x7AED3F` | `0xA8D9F0`; thiscall, owned 24-byte MSVC string by value, callee pops 24 |
| Skill Tree | `0x974B20`, `0x974B56`, `0x974B76`, `0x974D35`, `0x974E04` | `0xA8D4A0`; thiscall, const char pointer, callee pops 4 |

Bridges preserve ECX and callee-saved registers. Equipment reassigns its owned
string and transfers it exactly once to the native loader for destruction.
Unlisted paths delegate unchanged. CP949 lead/trail bytes survive ASCII case
and slash normalization. The hook has no fixed job-ID or resolution table.

Both members of a listed preview pair must exist through the native VFS before
either is selected. Otherwise both SPR and ACT loads use the packaged,
verified native-size stock pair. Both namespaces are distinct from world paths:
`hd_job_ui/preview/` and `hd_job_ui/stock/`. The choice is cached per route for
the process lifetime; restart after changing resource availability. Resource
object pointers are not cached. Complete stock fallback files are mandatory.

The profiled CFile object is 44 bytes: vtable `0xFD3074`, initial handle -1,
embedded 24-byte string at offset 20. Open is `0x573750` with `(path, 0, 1, 0)`;
Close is `0x573060`; string destruction is `0x4F08F0`; assignment is `0x4F1940`.
Native path buffers are bounded to 384 bytes.

Reference EXE SHA-256:
`73349f3606de8e9535d91b73e0177813c38369f06795f5a91200715a177f1a9f`.
The cleaned profile's original bytes are in
`tools/native/hd_job_ui_20250716.json`.

## Maintained source and generated payload

`tools/native/hd_job_ui.cpp` is the maintained runtime source and
`tools/native/hd_job_ui.qjs.in` is the WARP template.
`Scripts/Patches/HDJobSpritePreviews.qjs` is generated and ready to load in WARP.
Its `blob` contains x86 machine code and static data, not sprite pixels.
The cleaned payload contains no server-specific resource map. Its validation,
CALL-site metadata and payload relocation data are required implementation
parts, not leftover debug variables.

The cleaned builder strips linker export/debug metadata and records a source
hash. MSVC 14.51.36231 produced the checked-in payload. Rebuild from an x86
MSVC developer prompt or pass `--compiler` pointing to x86 `cl.exe` with
`link.exe` alongside it. A different compiler version may produce different
machine code and needs verification. Applying the generated QJS does not
require a native compiler or deployed DLL.

```powershell
python tools/build_hd_job_ui.py
python tools/build_hd_job_ui.py --check
python tools/verify_hd_job_ui_assets.py
python tools/verify_hd_job_ui_native.py
python tools/verify_hd_job_ui_warp.py --profile-client path/to/original-2025-07-16.exe
```

The builder also accepts `--profile-client` to check the original EXE against
the recorded profile. Cleaned tests use synthetic images/maps rather than
requiring the local game assets. QJS uses CRLF and UTF-8 without BOM.

## Legacy client and retained evidence

The main-checkout implementation also accepts the specifically verified v11
bridges `0x01967BF0` / `0x01967C30`. Its reference SHA-256 is
`f0d962c64c0449eaec24010c75a331ee087a4807fb8bdd42e3d097680e99709c`.
That compatibility is absent from the cleaned copy; do not apply its stock-only
profile to the prepatched v11 client.

The legacy `tools/rebuild_hd_job_ui_test.py` in the main checkout repaired the
v11 embedded archive list after verifying its exact hash and loader structure.
The profiled startup call is `0x00DB98B6`, old stub `0x0181F2F0`, AddPak
`0x00A88890`, and manager `0x0159D410`. Original archive order was preserved.
This fixture-specific repair is separate from the UI preview fix and was not
carried into the cleaned copy. The main-checkout packager's `--world-config`
option likewise belongs to the earlier world-fixture workflow.

The retained v4 client and `hd_job_ui_v4_world.grf` form the visually accepted
male-Monk fixture. V5 expanded coverage to the 61 mapped paths. The main client
EXE was not replaced during that work. The [coverage inventory](evidence/hd-job-ui/coverage.json)
and [verification record](evidence/hd-job-ui/verification.json) remain supporting
evidence rather than separate usage documentation.

## Verification and live acceptance

The cleaned copy passed seven asset tests, four x86 ABI/routing tests, eight
real upstream-WARP export/rejection cases, deterministic payload regeneration,
and standalone GRF packaging. Coverage includes arbitrary scales, alpha and
palette handling, metadata preservation, archive priority, split SPR/ACT
sources, fallback baking, both native ABIs, string ownership, CP949 boundaries,
missing pair members, cached choices, replacement manifests, restricted
existing-code writes, and invalid/missing input rejection.

The user supplied [this live screenshot](evidence/hd-job-ui/v4-monk-equipment-skill.png)
and reported success for the earlier male Monk: HD world body, native-size
standing Equipment and seated Skill Tree previews, with aligned heads in the
shown poses. Preview-versus-fallback selection was not independently captured
afterward. This evidence does not establish the full matrix or validate the
cleaned build visually.

Outstanding live checks are the cleaned build, other jobs, both sexes, all
relevant directions and animations, head/body alignment, missing-SPR and
missing-ACT fallback after restart, and repeated window reopening. Automated
checks do not replace those visual results.

## Alternative: apply ACT scaling in the native UI renderers

The alternative is to modify the Equipment/Skill Tree renderers to honor ACT scaling directly, eliminating generated previews. That requires additional reverse engineering and live validation.

This alternative is not implemented. It would draw from the existing HD
resources using their ACT transforms instead of generating a separate preview
pack. The work would need to identify the actual draw paths for both windows,
preserve offsets and head anchors, handle their native image/palette behavior,
and verify the same direction, animation, alignment and reopening cases.

The current implementation continues to use generated native-size pairs and
requires `Assets/HDJobUI`. Documenting the renderer alternative does not remove
that dependency or change the client implementation.
