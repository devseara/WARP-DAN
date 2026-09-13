"""Canonical x86 body-only perspective bridge; shared by WARP and native tests."""
import keystone

def bridge(origin, target=None):
    # At this profiled boundary ESI is the completed quad and EBP is the
    # original CActor::Draw frame. Its +0xC argument is the SPR palette.
    # Native head, headgear, weapons, NPCs and UI draws fail these guards.
    asm = '''
        pushfd
        pushad
        mov eax, dword ptr [ebp-0x28]
        test eax, eax
        jz done
        cmp dword ptr [eax], 0x1094810
        jne done
        mov edx, dword ptr [eax+0x4ac]
        test edx, edx
        jz done
        cmp edx, dword ptr [eax+0x4b0]
        jae done
        mov edx, dword ptr [edx]
        test edx, edx
        jz done
        lea ecx, [edx+0x110]
        cmp ecx, dword ptr [ebp+0xc]
        jne done
        cmp dword ptr [edx+20], 0x69727073
        jne done
        cmp dword ptr [edx+24], 0x635c6574
        jne done
        cmp dword ptr [edx+28], 0x5f6e616c
        jne done
        cmp dword ptr [edx+32], 0x6e696b73
        jne done
        cmp word ptr [edx+36], 0x5c73
        jne done
        lea edx, [edx+38]
        xor ecx, ecx
        mov ebx, 3
    digit:
        movzx eax, byte ptr [edx]
        cmp eax, 0x5c
        je valid_id
        sub eax, 0x30
        cmp eax, 9
        ja done
        imul ecx, ecx, 10
        add ecx, eax
        inc edx
        dec ebx
        jnz digit
        cmp byte ptr [edx], 0x5c
        jne done
    valid_id:
        dec ecx
        cmp ecx, 254
        ja done
        test esi, esi
        jz done
        mov eax, dword ptr [esi+0xc]
        test eax, eax
        jle done
        cmp eax, 0x3f800000
        ja done
        mov dword ptr [esi+0x2c], eax
        mov dword ptr [esi+0x4c], eax
        mov dword ptr [esi+0x6c], eax
    done:
        popad
        popfd
    '''
    asm += 'ret' if target is None else f'jmp {target:#x}'
    code, _ = keystone.Ks(keystone.KS_ARCH_X86, keystone.KS_MODE_32).asm(asm, addr=origin)
    return bytes(code), asm
