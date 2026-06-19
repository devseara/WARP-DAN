---
name: pincode-ui-addresses
description: Key addresses and RE findings for 2025-07-16 Ragexe pincode system
metadata:
  type: reference
---

# Pincode UI Key Addresses (2025-07-16 Ragexe 175220998)

- Native 0x08B9 handler: VA `0x00D21210`, RVA `0x00921210` — `__thiscall (void* ctx, void* pkt)`
- State jump table: `0x00D21464` — 8 DWORDs for states 0-7
- Global char-session pointer: `*(void**)0x00FC1628` (RVA `0x00BC1628`)
- Global UI manager: `0x0131F4E8` (RVA `0x00F1F4E8`)
- Map-server switch table: `0x00CAA2E0`
- Map-server default handler sentinel: `0x00CAA2B7`
- Packet buffer: `0x015E8198`
- Packet registration func: `0x00A9FF30`
- Pincode callback: `0x00FDA1A0`
- UI element creation: `0x00A31A30`
- Char dispatch func: `0x00D27190` — loads `edi` from `[0xFC1628]`

## Encryption
Seed-based Fisher-Yates: `tab[0..9]`, iter 1..9: `seed = 0x881234 + seed*0x3498`; `pos = seed%(i+1)`; `swap(tab[i], tab[pos])`. Encrypt maps plain digit d → `tab[d]`.
