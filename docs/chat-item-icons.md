# Inline chat item icons

Patch: **Inline Chat Item Icons** (`ChatItemIcons`, local ID 10004).
Client profile: **2025-07-16 Ragexe**. Enabled in `profiles/ragnarok_full_install.yml`.

Pickup and dropped-item notifications automatically receive an inline thumbnail
before the original native item name, for example `You got [icon] Red Potion (10).`
and `You dropped [icon] Red Potion (1).`.
The producer reads the actual `CItem` ID, not the displayed name. Items with
the same name therefore remain distinct. Original names, refine/slot text,
quantities, message colors and chat filters are retained.

Version 2 also displays ordinary Shift-click `ITEML` links as **icon + item name**,
without the stock `<Name>` angle brackets. The original encoded item instance
is retained, including its refine, grade, cards and random options; this is
not a conversion of the link to a base-ID-only thumbnail.

Version 3 preserves the actual pickup/drop `CItem` identification flag. An
unidentified item uses its native unidentified icon and tooltip; an identified
item uses its identified icon. Scrollback retains the state at the time of the
notification. Ordinary Shift-click links retain stock behavior: their existing
wire format does not carry an identification flag.

Chat text can also contain the same icon notation emitted by `mesitemicon`:

```text
^i[501]Red Potion
^i[1201]Knife
^i[1201,0]Dagger
^i[1201,1]Knife
```

For an rAthena script, `dispbottom "^i[501]Red Potion";` needs no new server
command. `mesitemicon(501)` can supply the tag when that existing server
feature is enabled. NPC dialog handling itself is unchanged. Other clients
need this patch to render this notation in their chat panes.

## Rendering and lifetime

- Icons use the client's identified or unidentified inventory BMP resource,
  resolved by ID and identification state through the native item-info manager.
  Existing GRFs/artwork are used as-is. Legacy `^i[ID]` defaults to identified;
  the optional flag accepts only `0` (unidentified) or `1` (identified).
- Thumbnails are 18 x 18 pixels; chat rows are 20 pixels high. Eight native
  spaces reserve the inline slot before wrapping (24px with the normal font).
- The native item-link parser owns the icon child and its line position.
  This retains native scrolling, wrapping, history, detached panes and docking.
- Ordinary item links use an icon and their native name, retaining native
  click/hover handlers. Icon-only links inherit those interactions and represent **base item info**,
  not the refine/cards/options of a particular inventory instance.
- Missing item resources leave a blank reserved slot; adjacent text remains.
  Invalid tags remain literal. Tags accept IDs 1 through 9,999,999, at most
  seven decimal digits. Inputs over 1023 bytes or conversions exceeding the
  1536-byte per-buffer limit fall back to the original text.

The conversion is render-local: no outgoing packets, server files, shared
TextOut bridge, inventory/grade renderer, supplied chat PNG or GRF is changed.

## Profiled hooks

`0x83D3F0` is the pre-wrap chat input; `0x83D840` is its line-add path. Both
receive scoped wrappers that convert tags into private, zero-padded `ITEML`
tokens. Converting only at the latter entry is insufficient: stock plain-text
wrapping could split an unrecognized `^i` tag first. Both entry trampolines
replay the exact five-byte `55 8B EC 6A FF` prologue.

The private token is equipment mask `00000`, flag `0`, seven leading zeroes
before the normal base62 ID (eight for unidentified), grade zero and four zero
card values. The native
base62 decoder handles these leading zeroes without changing identity.
The marker is recognized only in main/floating chat pane contexts.

Calls `0x841937` and `0x84AE83` share identical decoration for the measurement
and child-building passes. Synthetic icons get eight spaces. Ordinary links
append the native name using `0xA24EE0` codepage-aware clipping with a limit
of `max(12, pane.width / 2 - 24)`, followed by native `std::string::append` at
`0x4F1610`. No byte slicing or pane-width mutation is used.

Call `0x84AFA7` assigns one of two private vtables (including RTTI and all
native handlers). Icon-only children keep their existing 18px renderer.
Ordinary links retain native `0x85F480` text sizing/display-string behavior,
then resize to 18px high. Their private draw calls stock `0x853730`, preserving
text, hover color and underline, then converts the magenta background to the
chat's translucent gray and overlays the icon in the reserved space.
The embedded `CItem` at child `+0xF8` is not rewritten by either sizing wrapper.
At the private chat call `0x84AE54`, version 3 runs the stock ITEML constructor
`0x85B630`, then restores identification at `CItem+0x5C` for synthetic tokens only,
before native name/tooltip generation and the child CItem copy. Ordinary ITEML
instances are unchanged. Only byte value `1` means identified, matching native.
The private chat resource resolver chooses the native item-info node's string at
`+0x58` (identified) or `+0x1C` (unidentified), including SSO and heap strings.
These layouts and call targets are asserted at patch time. The shared resolver
used by Gacha, Battle Pass and other features is unchanged.

Fifteen profiled pickup-name calls in `0xCC2AB9..0xCC5AC1` and both dropped-item
name calls at `0xCA05EA` and `0xCC5F46` wrap the original `0x6A2CE0` formatter
and use the native `0x5D98A0` ItemId getter. Both drop paths select native
message 1609 (`MSI_DROP_ITEM`) immediately after this name call. The shared
formatter and getter are not modified. Names over 400 bytes are left intact.
All replacement call destinations and entry signatures are checked at build.

## Validation and installation

The full profile built successfully with no skipped patches. These passed:

```powershell
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_chat_item_icons.py Outputs/chat-item-icons-v2.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_ui.py Outputs/chat-item-icons-v2.exe
```

The icon suite executes the emitted x86, native base62 decoder, native item-link
tokenizer, both native chat parsing passes, the native pre-wrap gate, the
`0xCC5EB0` drop packet handler and native item-link text draw. Explicit CRT,
font, item-database/name and window/resource boundary doubles are used;
tests check ABI preservation, malformed/oversized input, same-name distinct IDs,
main/floating scoping, icon/name agreement in both parsing passes, long names,
unchanged full item payloads, native-link handlers, missing artwork and clipped pixels.
The existing chat suite covers PM/public routing, tabs, docking, input and alpha.
Installed GRFs were also checked for the 24px artwork for IDs 501, 502, 1201, 1202.

### Version 3 local installation (September 16, 2026)

After initially requesting staging only, the user explicitly requested
"Update normal Ragnarok.exe and local WARP". The tested version 3 candidate
below was installed as `D:/AAARAGNAROK/Ragnarok Online/Ragnarok.exe`, together
with its matching EPI and checksum report, with Ragnarok closed. Each copy was
SHA-256 verified. The local WARP patch was already version 3 and remains so.

The previous EXE, EPI and checksum report were copied and hash-verified in
`Outputs/chat-item-identification-20260916/before-live-install-20260916/`.
The installed EXE now hashes to
`F470E8067FE1EC2BF87A3EF92D973B36FD90E6ADF5B4E372C65053D078698156`.
This was a user-authorized local installation for in-game confirmation, not a
new accepted baseline. No server binary/configuration, asset, player data, Git
branch or preservation tag was changed. The original accepted EXE remains in
the verified backup. Test newly generated pickup/drop messages: old saved chat
entries without an identification flag cannot recover that missing information.

### Version 3 staged verification (September 16, 2026)

- Candidate: `Outputs/chat-item-identification-20260916/combined-v2/Ragnarok-chat-test.exe`
- SHA-256: `F470E8067FE1EC2BF87A3EF92D973B36FD90E6ADF5B4E372C65053D078698156`
- Reconstructed from the preserved accepted full profile, retaining the user's
  selections. WARP completed with no errors/skipped patches. Reversing BPUI/GCHA
  selection order produces the identical executable.
- Chat icon and ModernChatUI suites passed, including unidentified/identified
  pickup/drop flags, native child/tooltip propagation, resource choice, ordinary
  links, out-of-scope callers and failed native construction.
- Follow-up right-click check executes the real native hover-cache setter
  (`0x831A50`, char* input), both item-click entries (`+0x64` / `+0x68`), the
  native chat pane message route and description message 24. Both main and
  floating chat deliver the same embedded CItem and its original identification
  flag. The description window itself remains an explicit test boundary; final
  visual acceptance is still required. No extra runtime patch was needed.
- Combined Battle Pass/Gacha offline suite passed. The 57-file installed source
  guard passed without changing the preservation manifest.
- Standalone Battle Pass name/routing and standalone Gacha routing plus all five
  Gacha native suites passed. Other selected patches remained in each profile.
- **Initially staged only, per user request.** Before the later installation
  documented above, `Ragnarok.exe` still matched the
  accepted `C6602D9B314D5EE98D2C31F8E0D23696E6EE2627C4510E60D0538101A2DDC1B3`.
  No in-game screenshot acceptance is claimed. Tests must cover unidentified
  pickup/hover, identified pickup, drop, detached chat, history and ordinary links.

Build reproduction: `tools/build_chat_item_icons.py` takes an explicit saved
profile and new output directory. It uses an isolated WARP fixture and never
overwrites the installed game, source client or user's saved profile. Failed
builds remain staged for diagnosis and must not be deployed.

### Historical version 2 build (September 14, 2026)

- Output: `D:\warp\WARP20250716-main\Outputs\chat-item-icons-v2.exe`
- SHA-256: `83270D6F798A975C7C648C7F1029455989509EA9F77F02411C2240B10255B325`
- Both offline suites passed; `SkippedPatches.log` is empty.
- **Not installed.** The pre-install hash check found a newer, user-repatched
  `Ragnarok.exe` (SHA-256
  `20B01E18096ECB907FFC02B702A69EC9755EC4570734008924FA300E54002683`).
  Its EPI lists `ClanBodySkins` and `NativeActJobPreviews` in addition to the
  saved full profile. Installation stopped before any executable overwrite
  or backup copy. Obtain the user's current session profile, or have the user
  repatch with their existing WARP selections, to retain those settings.

### Previous version 1 installation

Installed September 14, 2026, with the client closed (subsequently repatched by
the user; these are historical installation hashes):

- `D:\AAARAGNAROK\Ragnarok Online\Ragnarok.exe`
- SHA-256: `FED1F063F3BB847ECB9E190CEB4B2A32788A48316D9663954F7977185C6E7D1F`
- Previous client: `D:\AAARAGNAROK\Ragnarok Online\Ragnarok.before-chat-item-icons-20260914.exe`
- Previous SHA-256: `F11E80F92956D6F78EACA78D02C81EAA323911114931090DF98F895884603567`

**Status: version 1 pickup icon visually confirmed by the user's screenshot;
version 2 offline acceptance passed, installation and live checks pending.**
After repatching, pick up and drop a Red Potion, and Shift-click an Apple into
chat. Check the icon plus name without angle brackets and click the link.
Also send a refined/card/option item link, verify its original item details,
then detach, resize, scroll and dock the relevant tab and test long names.
To roll back, close the client and copy the previous executable over Ragnarok.exe,
or rebuild with this patch deselected. The backup is not modified by this patch.
