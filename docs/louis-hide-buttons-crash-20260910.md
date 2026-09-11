# Louis hide/show buttons crash — 2026-09-10

The supplied EXE contains stale Auto Hunt and AutoSupport menu callbacks.
The logged crash is reproduced by executing the Auto Hunt mouse-up fragment
in Unicorn: it reads address `0x00000005` at `0x02872163`, exactly matching
the logged instruction address and `EDI=5`.

The report about hiding In-Game Settings, Discord Channel, and Battleground
is reproduction context. It does not by itself establish a native visibility
or layout defect. No patching instructions were taken from that quotation.

## Inputs

- EXE: `C:/Users/chris/Downloads/2025-07-16_Ragexe_175220998_clientinfo_patched.exe`
- EXE SHA-256: `F4E3B07B0B8A8D971C68E6FD2831633EEC1488921A83037B9D425DD94A3CB2AA`
- Log: `C:/Users/chris/Downloads/louis.logs`
- Log SHA-256: `28557783861C4C950A7A8D7E6ADF6106D39EAED5A59F4C9293533D0EB5060CFA`
- PE32, x86 (`Machine=0x14C`), preferred image base `0x00400000`.
- PE timestamp `0x68779440` matches the log. Linker version 14.29 is
  consistent with the MSVC toolchain.
- The relevant injected code is in `.xdiff`, with read/write/execute
  characteristics `0xE0000060`.

## Proven failing path

```text
Native UI mouse dispatcher
  00A46F49  call dword ptr [eax+7Ch]
  00A46F4C  return address reported in louis.logs

EAX = 02A782A4: cloned Auto Hunt UIButton vtable
  vtable[31] = 02A78210
  native child ID = 03F2 (verified in its ensure-button code)

02A78210  push ebp
02A78211  mov  ebp,esp
02A78213  call 02872070       ; stale request callback

02872070  00 00              ; ADD BYTE PTR [EAX],AL, not a callback
  ... zero bytes continue as instructions ...
02872154  01 00              ; ADD DWORD PTR [EAX],EAX
  ...
02872160  mov edi,[ebp+8]     ; reads the mouse-up x argument (5)
02872163  cmp byte ptr [edi],2Fh
                            ; access violation reading address 5
```

`0x02872160` contains an older custom slash-command dispatcher whose first
comparison is for `/itemcollection`. It is reached by sequential execution
through the invalid callback region. This is not evidence that the Item
Collection button was clicked. The currently hooked slash dispatcher at
`0x00D5CDF4` actually jumps to `0x0314A840`.

The zero-filled instructions write through EAX into the cloned vtable before
the read fault. In the isolated reproduction its first dword changes from
`0x02A781D0` to `0x054F04B0`. Adding a low-pointer check to the slash parser
would therefore leave the initiating defect and memory corruption intact.

## Other routes in this EXE

| Button | Child ID | Mouse-up handler | Emitted request target | Current request target |
| --- | --- | --- | --- | --- |
| Auto Hunt | `0x3F2` | `0x02A78210` | `0x02872070`, zero entry bytes | `0x02F4B130` |
| AutoSupport | `0x3F5` | `0x02A78D60` | `0x02A71690`, zero entry bytes | `0x0314A750` |
| Item Collection | `0x3F4` | `0x02A787B0` | cell `0x02A7769C` → `0x022F7BA0` | expected toggle entry present |

The current request functions were identified by their complete deferred
toggle signature and matched to the pending-state operands of the currently
installed bootstrap hooks:

- Auto Hunt: `0x00C74FE1` → `0x02F4B150`, pending state `0x02F4B124`.
- AutoSupport: `0x00C74FCC` → `0x0314A770`, pending state `0x0314A738`.

Item Collection's route is populated, its visibility cell is 1, and its
target starts with the expected PUSHFD/PUSHAD toggle sequence. This is an
entry-path check, not acceptance of its complete UI or packet flow.

## Source-level explanation

`Scripts/Patches/ROGlobalZeroMenu.qjs:2290` embeds
`autoHuntBridge.requestVir` in a direct CALL. Line 2356 does the same for
`autoSupportRequestVir`. Those operands are fixed when the menu is generated.

`Scripts/Patches/AutoCombatUI.qjs:6851` publishes newly allocated addresses
through `AutoCombatUI.MenuButton.v1`. Publishing a new CACHE record cannot
update an already-emitted menu CALL. AutoSupport has a route-cell refresh at
`Scripts/Patches/AutoSupportUI.qjs:7167`, but the menu's direct AutoSupport
CALL does not consume that cell.

The binary therefore proves a mismatch between the menu consumers and the
current Auto Hunt/AutoSupport producers. Producer deselection/reapplication
without regenerating their consumers is consistent with the stale, cleared
callback locations. The EXE and text log do not contain the WARP GUI history,
so the exact selection sequence and allocator event remain inferred.

## Remediation scope

Regenerate from a clean client with the final feature selection, building
AutoCombatUI and AutoSupportUI before ROGlobalZeroMenu. If either producer
is regenerated, rebuild its consumers too. Retain the desired native
hide/show choices while testing; this evidence does not justify removing
those choices as the underlying fix.

A durable source fix should enforce dependency invalidation/rebuild or give
the menu stable, correctly owned route cells refreshed when producers change.
It must cover callback, visibility, and peer-state references and validate
the emitted PE after GUI reapplication. Merely retargeting the two observed
CALLs would not establish that all other cached references are valid.

Acceptance should exercise both initial selection orders and feature
disable/re-enable with all three native buttons hidden, then click each
custom button in Classic and New menu layouts. No live acceptance or
production source fix is claimed by this investigation.

## Reproduction

From the repository root:

```powershell
.\.venv\Scripts\python.exe docs\evidence\louis-menu-crash-20260910.py 'C:\Users\chris\Downloads\2025-07-16_Ragexe_175220998_clientinfo_patched.exe'
```

The hash-bound script reads the PE, verifies the stale entries, resolves the
current bootstrap/request pairs, and emulates the actual Auto Hunt mouse-up
bytes. It asserts the exact faulting EIP and read address. The stack is
synthetic: x=5 follows the log, while y and the caller frame are supplied for
the fragment. This is not a full process dump or live game reproduction.
The EXE and production patch scripts were not modified.
