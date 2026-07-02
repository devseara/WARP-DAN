# WARP QJS Patch Architecture — Improvement Proposal

## Problem Statement

The current QJS patching system requires authors to manually encode raw x86 machine code via
string concatenation. This is fragile, error-prone, and wastes development time on low-level
details instead of logic. The dual-wield weapon sprite patch effort exposed systematic gaps:

1. **No runtime memory access** — QJS sees the EXE file on disk, not process memory.
   Cannot read character state, item IDs, or action flags at render time.

2. **No game function calling** — Cannot call `d8a1d0(itemId)` or `0xC43230` from QJS.
   Must build entire call sequences in raw hex.

3. **Assembly via string concatenation** — `" 8B 87 44 04 00 00" + " B9 C0 A3 5F 01"`.
   One wrong byte = silent failure or crash. No validation.

4. **Only static hooks** — `SetCALL`/`SetJMP` write to the EXE file at patch time.
   Cannot intercept at runtime, cannot modify return values without full stub.

5. **Shared state between hooks** — Requires manual `Exe.Allocate` for slots plus
   `dwordLE()` helpers to embed addresses in raw hex. CACHE object exists but is
   in-process only (QJS side, not game side).

---

## Proposed Architecture

Three layers, all implemented in WARP's C++ engine. Layers build on each other.

```
┌──────────────────────────────────────────────────┐
│ Layer 3: Declarative Hooks                       │
│   Exe.Detour(addr, { onEntry, onReturn })        │
│   Generates stubs via Layer 1, installs via      │
│   Layer 2                                        │
├──────────────────────────────────────────────────┤
│ Layer 2: Process Memory Bridge                   │
│   Exe.ReadMemory / Exe.WriteMemory               │
│   Exe.Call(addr, ...args)                        │
│   Exe.AllocShared(size)                          │
│   Communicates via WARP↔boh.dll shared memory    │
├──────────────────────────────────────────────────┤
│ Layer 1: Build-Time Improvements                 │
│   Real assembler (Keystone or Xbyak)             │
│   Exe.RelativeOffset(from, to)                   │
│   Exe.ToBytesLE(value, width)                    │
│   Operates on EXE file, no injection needed       │
└──────────────────────────────────────────────────┘
```

---

## Layer 1: Build-Time Improvements

**Zero risk — operates on the EXE file at patch time. No process injection needed.**

### 1.1 Real Assembler

Replace string concatenation with an actual assembler (Keystone or Xbyak):

```javascript
// Current approach (fragile):
let stub = "";
stub += " 51";                   // PUSH ECX
stub += " 56";                   // PUSH ESI
stub += " 8B CF";                // MOV ECX, EDI
stub += " E8" + rel32;           // CALL rel32 (manually computed!)
stub += " FF B7 44 04 00 00";   // PUSH [EDI+0x444]

// Proposed:
let stub = Asm.x86(_ => {
    _.push(ECX);
    _.push(ESI);
    _.mov(ECX, EDI);
    _.call(0xC43230);            // rel32 computed automatically
    _.push(dword [EDI+0x444]);
    _.mov(ECX, 0x15FA3C0);
    _.call(0xD8A1D0);
    _.pop(ESI);
    _.pop(ECX);
    _.ret();
});
let stubBytes = Asm.encode(stub);
```

Benefits:
- Catches encoding errors at patch time (not runtime crash)
- All rel32/abs32 offsets computed automatically
- Operand validation (immediate too large for instruction variant, etc.)
- Readable, maintainable patch code

**Implementation:** Link Keystone (BSD-licensed) into WARP. Add `Asm` object to QJS
bindings. Extend `Exe.SetHex` to accept Asm output natively.

### 1.2 Offset/Encoding Helpers

```javascript
// Relative offset for CALL/JMP instructions
let rel32 = Exe.Rel32(callSiteVA + offset, targetVA);
// Returns 4-byte little-endian hex string

// Absolute address as LE bytes (for MOV [abs32], EAX etc.)
let abs32 = Exe.ToBytesLE(address, 4);

// Write a CALL at physical offset
Exe.WriteCALL(phy, fromVA, targetVA);  // computes rel32 internally
```

### 1.3 Stub Allocation + Writing

```javascript
// Allocate returns { phy, vir, size } object
let stub = Exe.AllocateBuffer(64, 0x10);
Exe.SetHex(stub.phy, Asm.encode(myStub));

// Or combined:
let stub = Exe.PlaceCode(Asm.encode(myStub), 0x10);
Exe.SetCALL(hookPhy, stub.vir);
```

---

## Layer 2: Process Memory Bridge

**Requires extending the WARP↔boh.dll shared memory protocol.**
WARP already injects `boh.dll` and scans for shared blocks. This formalizes it.

### 2.1 Memory Read/Write

```javascript
// Read game process memory at runtime
let handFlag = Exe.ReadU8(0x15FA3C0 + 0x4D0);
let offItem  = Exe.ReadU32(characterObj + 0x444);

// Write to game memory
Exe.WriteU32(slotVir, 0x12345678);
```

**Implementation:** Add a generic shared memory block protocol.
WARP writes requests to a shared block; boh.dll polls and executes them.

Protocol (shared memory block, magic `WARP`):
```
Offset  Size  Field
  0      4    magic (0x50415257 = 'WARP')
  4      4    command (0=idle, 1=read, 2=write, 3=call)
  8      4    status  (0=pending, 1=done, 2=error)
 12      4    result value
 16      4    address (for read/write)
 20      4    size    (1/2/4 for read/write)
 24      4    value   (for write)
 28     ...   extended data (for call args)
```

### 2.2 Game Function Calling

```javascript
// Call any game function by address
// Handles __thiscall (ECX=this), __stdcall, __cdecl automatically
let weaponType = Exe.Call(0xD8A1D0, {
    this: 0x15FA3C0,       // __thiscall: ECX
    args: [itemId],        // stack arguments
    cleanup: 4             // callee cleans N bytes (RET N)
});
```

**Implementation:** boh.dll creates a remote thread in the game process at a
small trampoline that sets up registers/stack, calls the target, and writes
the return value back to the shared block.

### 2.3 Shared Allocations

```javascript
// Allocate in EXE image (current behavior) + register with boh.dll
let slot = Exe.AllocateShared(4, 4);
slot.write(0);              // Initialize
// ... hook writes to slot at runtime ...
let val = slot.read();      // Read via Layer 2 bridge
```

---

## Layer 3: Declarative Hooks

**QJS API that generates stubs via Layer 1 and installs via Layer 2.**

### 3.1 Function Entry/Return Detours

```javascript
Exe.Detour(0x00D72D30, {
    // Called BEFORE the original function executes
    onEntry: function(ctx) {
        // ctx provides access to registers and stack
        ctx.mainItem = ctx.stack(3);   // [ESP+0xC] = arg3
        ctx.offItem  = ctx.stack(4);   // [ESP+0x10] = arg4
    },

    // Called AFTER the original function returns
    onReturn: function(ctx) {
        let combinedType = ctx.eax & 0xFF;
        if (combinedType >= 25 && combinedType <= 30) {
            // Replace combined type with offhand individual type
            let individual = Exe.Call(0xD8A1D0, {
                this: 0x15FA3C0,
                args: [ctx.offItem]
            });
            ctx.eax = individual;
        }
    }
});
```

WARP generates the stub internally:
1. Allocates stub space
2. Uses Layer 1 assembler to emit: save regs, call onEntry, call original,
   call onReturn, restore regs, return
3. Writes JMP at target address
4. QJS callbacks invoked via Layer 2 bridge at runtime

### 3.2 Inline (Mid-Function) Hooks

```javascript
// Hook at any instruction within a function
Exe.Hook(0x00D72D96, {
    onExecute: function(ctx) {
        // ctx.eip = address of this instruction
        // Return false = skip original instruction
        // Return true = execute normally
        if (wantSkipCombiner) {
            ctx.eip = 0x00D72DA3;  // redirect to non-dual path
            return false;
        }
        return true;
    }
});
```

### 3.3 CALL Site Interception

```javascript
Exe.InterceptCall(0x00D424B7, {
    // Called instead of 0xC43230
    replace: function(ctx) {
        let offItem = Exe.ReadU32(ctx.edi + 0x444);
        return Exe.Call(0xD8A1D0, {
            this: 0x15FA3C0,
            args: [offItem]
        });
    }
});
```

---

## Implementation Priority

| # | Feature | Layer | Effort | Risk | Impact |
|---|---------|-------|--------|------|--------|
| 1 | `Exe.Rel32` + `Exe.ToBytesLE` | 1 | ~2 hrs | None | Eliminates manual rel32 bugs |
| 2 | Keystone assembler integration | 1 | ~2 days | None | Eliminates ALL raw hex bugs |
| 3 | `Exe.AllocateBuffer` returning object | 1 | ~4 hrs | None | Cleaner allocation API |
| 4 | Shared memory command protocol (boh.dll) | 2 | ~3 days | Low | Foundation for layers 3+ |
| 5 | `Exe.ReadMemory` / `Exe.WriteMemory` | 2 | ~1 day | Low | Runtime state access |
| 6 | `Exe.Call(addr, args)` | 2 | ~2 days | Medium | Game function calling |
| 7 | `Exe.Detour` — entry/return hooks | 3 | ~2 days | Medium | Replaces manual stub writing |
| 8 | `Exe.InterceptCall` — call replacement | 3 | ~1 day | Medium | Most common use case |
| 9 | `Exe.Hook` — inline hooks | 3 | ~2 days | Medium | Conditional control flow |

**Layers 1-3 combined:** ~2 weeks of full-time work. Funded once, benefits every
patch forever.

---

## Concrete Example: Dual-Wield Patch Rewritten

**Current approach:** ~90 lines of QJS with raw hex, manual rel32 computation,
shared slot workarounds, guard bypassing, and repeated crash debugging.

**With all three layers:**

```javascript
Exe.InterceptCall(0x00D424B7, {
    replace: function(ctx) {
        let offItem = Exe.ReadU32(ctx.edi + 0x444);
        return Exe.Call(0xD8A1D0, {
            this: 0x15FA3C0,
            args: [offItem]
        });
    }
});
```

That's it. The InterceptCall generates the stub, computes all offsets, installs the
JMP at patch time, and the replace callback runs at render time via Layer 2 bridge.

---

## Backward Compatibility

All existing QJS APIs (`SetHex`, `SetCALL`, `SetJMP`, `Allocate`, `Vir2Phy`,
assembly macros) remain unchanged. New APIs are additive. Existing patches
continue to work. New patches can adopt the declarative APIs incrementally.
