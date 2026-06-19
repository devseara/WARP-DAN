---
name: pincode-ui-approaches
description: What approaches were tried for in-game pincode UI and their outcomes
metadata:
  type: project
---

# Pincode UI — Approaches Tried

## What works
- **Named pipe transport**: Server → `\\.\pipe\BOH_Pincode` → DLL. Reliable.
- **Socket discovery**: `getpeername()` scan handles 1-65535, find port 5121-5130.
- **Encryption**: Algorithm confirmed matching client↔server.
- **Global context**: `*(void**)0x00FC1628` gives valid char-server session.

## What failed
1. **Send 0x08B9 from map server**: Client ignores it — only char-server dispatches it.
2. **CustomPacketDispatch switch table**: 0x08B9 out of bounds; 0x0BD0 dropped pre-dispatch.
3. **Default handler hook (0x00CAA2B7)**: It's a sentinel value, not code.
4. **Native handler with NULL context**: Crashes — handler dereferences `[ctx+0x1CC]` etc.
5. **Native handler with heap buffer context**: Creates UI but game's render loop crashes async.
6. **Native handler with REAL context from global**: Same async crash — threading issue.
7. **Custom UI (GDI painted)**: Black square — `CreateFontW` fails on ANSI build.

## Critical insight
The native handler creates windows that integrate with the game's UI render loop. Calling from a foreign thread causes the game's main loop to crash at `0x00dbd288`. The handler MUST run on the game's main thread.

## Next approach
Standalone Windows button controls (`BS_PUSHBUTTON`) with `CreateFontA`/`LoadCursorA` (ANSI-compatible). Or dispatch to game's main thread via window message hook.
