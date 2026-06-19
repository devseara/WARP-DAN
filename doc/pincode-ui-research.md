# Pincode UI Research — 2025-07-16 Ragexe

## Goal
Trigger the native mouse-driven PIN pad from in-game (map-server connection) instead of only at character-select (char-server connection).

## Key Addresses (2025-07-16 Ragexe 175220998)

| Address | RVA | Name | Description |
|---------|-----|------|-------------|
| `0x00D21210` | `0x00921210` | `HandlePincodePacket` | Native `0x08B9` handler — `__thiscall` (ecx=session, stack=pkt) |
| `0x00D21464` | `0x00921464` | `PincodeJumpTable` | State dispatch table: 8 DWORDs for states 0-7 |
| `0x00D28193` | `0x00928193` | `DispatchCall` | `call 0xD21210` after `mov ecx, edi` |
| `0x00D27190` | `0x00927190` | `CharDispatchFunc` | Char-server packet dispatch function entry |
| `0x00D271C6` | `0x009271C6` | `ContextLoad` | `mov edi, [0xFC1628]` — loads session from global |
| `0x00FC1628` | `0x00BC1628` | `g_pCharSession` | **Global pointer** to char-server session object |
| `0x0131F4E8` | `0x00F1F4E8` | `g_pUIManager` | Global UI manager — used by all pincode UI creation |
| `0x00CAA2E0` | `0x008AA2E0` | `MapSwitchTable` | Map-server packet dispatch switch table |
| `0x00CAA2B7` | `0x008AA2B7` | `DefaultHandler` | Sentinel for unhandled packets |
| `0x00C9E1DD` | `0x0089E1DD` | `MainLoopReturn` | Return point after packet processing |
| `0x015E8198` | `0x011E8198` | `PacketBuffer` | Global packet buffer address |
| `0x00A9FF30` | `0x0069FF30` | `RegisterPacket` | Packet registration function (length table) |
| `0x00A31A30` | `0x00631A30` | `CreateUIElement` | Creates pincode UI buttons/windows |
| `0x00FDA1A0` | `0x00BDA1A0` | `PincodeCallback` | Callback for pincode button clicks |

## Handler Function Signature
```c
typedef void (__thiscall *PincodeHandlerFn)(void* sessionContext, void* packetData);
// packetData: [pktId:2][seed:4][aid:4][state:2] = 12 bytes
// sessionContext: char-server session object (must be valid heap object)
```

## State Jump Table (at 0x00D21464)
| State | Address | Description |
|-------|---------|-------------|
| 0 | `0x00D21281` | PINCODE_OK — already authed |
| 1 | `0x00D2129F` | PINCODE_ASK — verify PIN |
| 2 | `0x00D213C3` | PINCODE_NOTSET — no PIN set |
| 3 | `0x00D212FA` | PINCODE_EXPIRED — must change PIN |
| 4 | `0x00D2131C` | PINCODE_NEW — set new PIN |
| 5 | `0x00D21339` | PINCODE_ILLEGAL — invalid PIN |
| 6 | `0x00D21359` | PINCODE_KSSN — KSSN not supported |
| 7 | `0x00D21379` | PINCODE_PASSED — PIN correct |

## Encryption Algorithm
```cpp
// Seed-based Fisher-Yates shuffle of digits 0-9
void BuildShuffle(uint32_t seed) {
    char tab[10] = {0,1,2,3,4,5,6,7,8,9};
    for (int i = 1; i < 10; i++) {
        seed = 0x881234u + seed * 0x3498u;
        int pos = seed % (i + 1);
        if (i != pos) swap(tab[i], tab[pos]);
    }
}
// "Encryption": digit d maps to tab[d]
// Server decrypts by doing the same shuffle and reverse-mapping
```

## Approaches Tried

### 1. Send 0x08B9 from map server (FAILED)
Server sends `0x08B9` → client ignores it on map-server connection.
Packet only dispatched on char-server connection.

### 2. CustomPacketDispatch switch table patch (FAILED)  
Patch switch table entry for `0x08B9`/`0x0BD0` → entry out of bounds or
packet dropped before dispatch. The switch table formula:
`entry = switchTableVir + (packetId - 0x73) * 4`

### 3. Default handler hook at 0x00CAA2B7 (FAILED)
`0x00CAA2B7` is a sentinel value, not executable code. Writing JMP there
corrupts data.

### 4. Named pipe transport (WORKING)
Server writes `[seed:4][aid:4][state:2]` to `\\.\pipe\BOH_Pincode`.
DLL receives via `CreateNamedPipe` + `ReadFile`. Reliable, low latency.

### 5. Socket discovery via getpeername() (WORKING)
Scan SOCKET handles 1-65535 with `getpeername()`. Look for port 5121-5130.
SOCKET handles can be >2048, so wide scan is needed.

### 6. Calling native handler with NULL context (CRASH)
Handler dereferences session context at various offsets. NULL = access violation.

### 7. Calling native handler with heap buffer context (CRASH)
Handler creates UI, game's main loop crashes rendering it. The handler
writes result to `[ctx+0xC]` — heap buffer handles this. But the created
window integrates with game's UI system and crashes the render loop.

### 8. Calling native handler with REAL context from global (CRASH - THREADING)
Reading `*(void**)0x00FC1628` gives valid char-server session. But calling
handler from our thread creates windows on wrong thread. Game's main loop
crashes asynchronously when trying to render them.

### 9. Standalone custom UI with Windows buttons (NOT SHOWN)
Standard `CreateWindowExW` + `BS_PUSHBUTTON` controls should render on any
Windows system. `CreateFontW` fails on ANSI builds — use `CreateFontA`.
`LoadCursorW` fails — use `LoadCursorA(0, (LPCSTR)32512)`.

## Critical Findings

1. **Global session pointer**: `*(void**)0x00FC1628` contains the char-server session.
   Readable from DLL at any time after char-server connection is established.

2. **Threading is the core problem**: The native handler MUST be called from the
   game's main thread. Window creation on foreign threads causes async crashes
   in the game's render loop (`0x00dbd288` → `0x00a757e4` → ... → CRASH).

3. **Map-server dispatch ignores pincode packets**: `0x08B9` is not in the
   map-server packet dispatch table. Custom packet IDs within range (`0x0BD0`)
   are also dropped — likely due to packet length validation table.

4. **Encryption is fully reverse-engineered**: Same algorithm confirmed working
   between client and server via the `char_pincode_decrypt` source.

## Next Steps

- Use the standalone UI approach with proper Windows controls (buttons)
- OR: Find a way to dispatch the handler call to the game's main thread
  (e.g., via `PostMessage` to the game window with a custom message,
  hooking the game's WndProc, or using a CBT hook)
