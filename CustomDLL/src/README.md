# BOH Visual DLL Builds

Two packaging modes are supported.

## Combined build

Run `build.bat` to produce `boh.dll`. Select the default `boh.dll` value in
every WARP feature prompt.

## Dedicated builds

Run `build_split.bat` to produce:

| DLL | Features | WARP export |
|-----|----------|-------------|
| `boh_text.dll` | Item colors and extended names | `ColoredItemNameVisualInit`, `ExtNameVisualInit` |
| `boh_npc_names.dll` | Always-show NPC names | `NpcNameOverlayInit` |
| `boh_rune.dll` | Rune visuals | `RuneVisualInit` |
| `boh_fps.dll` | FPS and ping overlays | `FpsPingOverlayInit` |
| `boh_inventory_tabs.dll` | Image inventory tabs | `InventoryTabsInit` |

Each WARP patch has its own saved DLL-name prompt. The output files may be
renamed as long as the matching filename is entered when patching the client.

Item colors and extended names intentionally remain together in
`boh_text.dll`. Both features intercept the same GDI text APIs, so loading two
independent hook owners would reintroduce ordering and double-hook problems.
Their packet consumers are separate: ICOL is handled by `item_color/`, while
EXTN transport and substitution state live in `extended_name/`.

## Extended-name behavior

The server's `@showmobinfo` setting is carried in the mob fields of the
extended-name packet. It does not change unrelated atcommands. On the client,
mob substitution is limited to an exact nameplate match. For example, `Poring`
can become `Poring | HP: ...`, but `Poring Card` is left untouched.

Run the focused regression test from a Visual Studio x86 command prompt:

```bat
cl.exe /nologo /O2 /MT /EHa /I. ^
  extended_name\extended_name_test.cpp extended_name\extended_name.cpp ^
  /Fe:extended_name_test.exe /link kernel32.lib user32.lib
extended_name_test.exe
```
