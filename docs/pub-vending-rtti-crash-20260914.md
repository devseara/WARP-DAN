# Pub/vending crash: missing RTTI on custom windows

The supplied `0xE06D7363` report is explained by missing native RTTI metadata on cloned custom top-level window vtables. Creating a pub/chat room or vending shop runs the native window-placement check at `0x00A38C60`; its `__RTtypeid` call at `0x00A38CF9` returns to the first client frame in the log, `0x00A38CFE`.

## Exact deployed artifact

- Client: `C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes/2025-07-16_Ragexe_175220998_clientinfo_patched.exe`
- Before SHA-256: `48c7cece98b8dc723bd5ac6cf11773f6ddbbe724e2bc33b1ffaedcb3b1823023`
- The repository's existing patched EXE has the same hash.
- An isolated rebuild using the saved LastSession selections and original sources reproduced this file byte for byte.
- Fixed SHA-256: `73a3a6e28ea8c4a5ccd14d5a8fed85ae15c05e148c3910ad7c18e04718622350`.

## Failure mechanism

The native checker traverses the WindowManager list at `0x0131F4E8 + 0x17C`. For each node, it calls `__RTtypeid(node->window)` and compares its type with `UIMerchantShopTitle` and `UIChatRoomTitle`.

The imported helper is:

```text
00A38CF9  CALL 00E07DB1
00E07DB1  JMP DWORD PTR [00FC1784]  ; VCRUNTIME140!__RTtypeid
```

The actual bundled x86 runtime reads:

```asm
mov eax, [eax]       ; object's vtable
mov eax, [eax-4]     ; MSVC Complete Object Locator
mov eax, [eax+0Ch]   ; type descriptor
```

Custom window clones copied only virtual methods starting at slot zero. They omitted the Complete Object Locator pointer at slot -1. Six tables had a zero preceding DWORD; Item Collection had `0xFE`. The RTTI lookup faults, the runtime's SEH filter handles that access violation, and it throws `std::__non_rtti_object` as a C++ exception. In the bundled DLL, the corresponding ThrowInfo is RVA `0xE2C4`; the log includes its relocated address `0x7356E2C4`.

Microsoft documents [the MSVC C++ exception code](https://devblogs.microsoft.com/oldnewthing/20100730-00/?p=13273). The diagnosis here additionally uses the deployed EXE, its bundled runtime, and the actual failed RTTI reads; the exception code alone would not identify the cause.

| Window | Old cloned vtable | Old slot -1 | Expected native locator |
| --- | --- | --- | --- |
| AutoCombat main (`0x3F0`) | `0x01C77874` | `0` | `0x010C2ACC` |
| AutoCombat controller (`0x3F1`) | `0x01DB7020` | `0` | `0x010C2ACC` |
| AutoSupport main (`0x3F6`) | `0x01DD71D4` | `0` | `0x010C2ACC` |
| AutoSupport controller (`0x3F7`) | `0x01FB6360` | `0` | `0x010C2ACC` |
| Item Collection (`0x3F3`) | `0x01FCC9E4` | `0xFE` | `0x010C2ACC` |
| Bestiary (`0x3FA`) | `0x0248372C` | `0` | `0x010C2ACC` |
| RO Global EXP bar | `0x01FCFF04` | `0` | `0x010CE590` |

Any of these instances in the checked list can trigger the same failure. The text log does not identify which instance was visited first.

## Introduction

Historical source inspection confirms the omission in these introducing revisions:

| Revision | Date (UTC+8) | Feature |
| --- | --- | --- |
| `8bd71ba` | 2026-07-20 07:05 | RO Global EXP bar; earliest affected emitter |
| `60855e5` | 2026-07-20 13:29 | AutoCombat UI; later reused for its controller |
| `be4de5e` | 2026-09-01 | Item Collection UI |
| `21260af` | 2026-09-04 | AutoSupport UI and controller |
| `6ec304a` | 2026-09-12 | Bestiary UI |

This defect predates the September 14 automation session-text commit `9a10e8b`.

## Fix and invariant

Each affected emitter now allocates one extra DWORD, copies the original vtable including its slot -1 locator, and exposes the virtual-method table at allocation +4. Existing virtual method indices, native base-class identity, window state layout and custom overrides are preserved. An unmapped native locator causes patch generation to fail.

A custom object created with a native constructor must retain that native vtable's RTTI locator when its methods are cloned. Do not overwrite the DWORD before an existing clone: that word can belong to another allocation, as the Item Collection example shows.

Changed emitters: AutoCombatUI, AutoSupportUI, ItemCollectionUI, ROGlobalZeroExpBar, and the already-present BestiaryUI. No new optional feature is introduced.

## Validation

- The original EXE is a negative control: all seven native RTTI pointer lookups fail.
- The rebuilt EXE has seven valid locators and all seven runtime pointer-load sequences return the expected native type descriptor.
- The native pub/vending checker, its input-handler path, and RTTI import thunks remain byte-identical.
- Both isolated baseline and fixed full-profile builds report no patch errors.
- The final `cps.dll` import audit reports zero stale bridge operands.
- The existing 134-asset AutoSupport UI contract and changed-QJS syntax/CRLF/no-BOM checks pass.

The verifier executes the exact runtime pointer-load instructions with synthetic objects. It does not simulate the entire game or claim live pub/vending acceptance.

```powershell
python tools/verify_custom_window_rtti.py <fixed.exe> --runtime <VCRUNTIME140.dll> --expected-count 7 --report <report.json>
```

Use `--expect-broken` only for a deliberate old-EXE negative control. The expected count depends on selected custom UI patches. Evidence is stored in `docs/evidence/pub-vending-rtti-20260914.json`.

## Deployment

The verified fixed EXE and matching EPI/hash sidecars are installed in both the reported Banquet of Heroes game folder and the repository's client-output folder. Originals are preserved under `Outputs/pub-vending-rtti-20260914/deployment-backup/game` and `deployment-backup/repository`.

Five focused creation/reapplication cases pass after checking complete emitted callback bodies. Four Bestiary native menu/toggle check groups also pass. The lifecycle verifier's outdated fixed toggle-prologue check was replaced by a complete emitted-function comparison.

The user confirmed successful live pub and vending creation on 2026-09-14. The RTTI correction is accepted for the deployed build.
