# Original announcement item icons

Author: DevSeara. Target: 2025-07-16 Ragexe.

Keeps the original stationary top-screen announcement balloon, background,
position, colors, border, lifetime and message limit. Only an 18px item image is
added immediately before its name, with a 20px text advance. There is no Notice
label, scrolling marquee, custom window or replacement queue.

WARP title: **Original Announcements with Item Icons**. The internal name
`NoticeMarquee` and ID 10007 are retained for compatibility with local saved
profiles from the earlier design; this package does not install that design.

## Install

First install the accepted Battle Pass/Chat/NPC/Gacha package using the README
instructions. Close WARP and back up your working copy, then apply the additional
`install/DevSeara-Announcement-Item-Icons.diff` from this package:

```powershell
git apply --check -- D:/warp/WARP-DAN/install/DevSeara-Announcement-Item-Icons.diff
git apply --whitespace=nowarn -- D:/warp/WARP-DAN/install/DevSeara-Announcement-Item-Icons.diff
```

Do not force a failed check or apply the same upgrade twice. The add-on adds only
the new patch, its source/payload and its menu/ID registration; it does not modify
Battle Pass, Gacha, their shared helpers, or the existing baseline installer.
Restart WARP and select this patch when rebuilding from the original client.
Select **Inline Chat Item Icons** as well to show the same images in chat panes.

Examples in script announcements:

```text
^i[909]Jellopy
^i[1201,0]Dagger
^i[1201,1]Knife
```

The explicit flag selects unidentified (`0`) or identified (`1`) artwork. The
text after the tag is literal; this version does not change that text to the
client's unidentified name. Automatic rare-drop announcements from the matching
server currently send identified catalog art and the public catalog name.
**Automatic identification-aware announcement names/icons remain pending.**

Normal/MVP rare-drop messages in the matching `devseara/Ragnarok` source attach
the real numeric item ID. Install a compatible client before that map-server;
an old client would display the tags literally. No drop probability, rate text,
reward delivery, Gacha behavior, char-server protocol or SQL migration changes.
Unknown/missing artwork retains the name and its spacing. Untagged names are
not guessed or matched against the item database.

## Implementation

`Scripts/Runtime/NoticeMarquee/stock.cpp` is an import-free x86 payload; rebuild
using `uv run --with pefile python tools/build_notice_marquee.py` with MSVC x86
tools installed. The generated version-2 payload and JSON metadata are in
`Inputs/NoticeMarquee/`. No game executable, DLL or private profile is shipped.

The QJS validates size, CRC, relocations and original call targets. Only native
balloon measure/draw/height sites `7890DE`, `78922E`, `7894E2`, `789500` and the
009A wrapping call `CB84ED` are replaced. Both stock broadcast insertion calls
`CB8621` and `CB7943` still reach `788ED0`. No packet-length or shared text hooks
are changed, and the existing 01C3 packet/buffer limits are not extended.

Tagged wrapping treats each icon tag as indivisible, preserving native locale
character boundaries and vector ownership. Plain wrapping uses the original
routine. Both measurement and line advance include the icon height; the stock
four-pixel line gaps remain. Catalog resources use actual numeric IDs and the
identified/unidentified resource keys, not server display-name guesses.

## Verification

```powershell
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_stock_announcement_icons.py path/to/patched.exe
python tools/verify_stable_features.py --manifest docs/stable-battlepass-gacha.json
```

The native boundary suite executes actual emitted x86 helpers and the original
balloon renderer with native tree/list layouts. It covers icon/name placement,
stationary redraw, native background/spacing, multiple lines, identification
flags, malformed/long input, multibyte wrapping, surface clipping, missing art,
burst messages and calling conventions. Font/resource boundaries are explicit
test doubles, not a claim of live in-game acceptance.

The author also verified five chat suites, combined and standalone Battle Pass/
Gacha suites, identical reversed-order builds, and preserved source guards.
The server counterpart passed its production builds, Battle Pass/NPC/compiler,
party/drop and Gacha regressions. Test binaries/backups remain local. The normal
client/map-server were installed for user testing with verified backups; live
visual acceptance is still pending. The September 15 restore tag is untouched.
