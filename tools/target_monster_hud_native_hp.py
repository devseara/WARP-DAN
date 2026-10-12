"""Independent cache of authoritative native 0x0977 monster-HP packets."""

def emit(assemble,base,cache,world_slot):
    ensure=base+0x2800;mirror=base+0x2900;lookup=base+0xa800
    assemble(ensure,f'''
    cmp dword ptr [{world_slot}],ecx; je done
    push eax; push ecx; push edi
    mov dword ptr [{world_slot}],ecx
    mov edi,{cache}; mov ecx,2048; xor eax,eax; cld; rep stosd
    pop edi; pop ecx; pop eax
    done: ret
    ''')
    # The stock dispatch case has already read the complete fixed-size packet.
    # Preserve all caller state; continue stock except for a new full-HP gauge,
    # which would add a world bar to an otherwise untouched monster.
    assemble(mirror,f'''
    push ebp; mov ebp,esp; sub esp,4; mov dword ptr [ebp-4],0
    pushfd; pushad
    cmp dword ptr [ecx],0x10904b8; jne forward
    mov esi,[ebp+8]; cmp word ptr [esi],0x977; jne forward
    mov edi,[ecx+0xcc]; test edi,edi; jz forward
    mov ebx,[esi+2]; test ebx,ebx; jz forward
    mov eax,[esi+6]; mov edx,[esi+10]; test edx,edx; jz forward; cmp eax,edx; ja forward
    mov ecx,edi; call {ensure}
    mov eax,ebx; and eax,511; mov ecx,16
    probe: mov edx,eax; shl edx,4; add edx,{cache}
    cmp dword ptr [edx],ebx; je store; cmp dword ptr [edx],0; je store
    inc eax; and eax,511; dec ecx; jnz probe
    mov edx,ebx; and edx,511; shl edx,4; add edx,{cache}
    store: mov eax,[esi+6]; mov [edx+4],eax; mov eax,[esi+10]; mov [edx+8],eax; mov [edx],ebx
    mov eax,[esi+6]; cmp eax,[esi+10]; jne forward
    push ebx; mov ecx,edi; call 0xa69eb0; test eax,eax; jz forward
    cmp byte ptr [eax+0x314],5; jne forward
    cmp dword ptr [eax+0x300],0; jne forward
    mov dword ptr [ebp-4],1
    forward: cmp dword ptr [ebp-4],0; jne cached_full
    popad; popfd; mov esp,ebp; pop ebp; jmp 0xcf33f0
    cached_full: popad; popfd; mov esp,ebp; pop ebp; ret 4
    ''')
    assemble(lookup,f'''
    push ebx; push esi; push edi
    mov ebx,eax; and eax,511; mov esi,eax; mov edi,16
    probe: mov eax,esi; shl eax,4; add eax,{cache}
    cmp dword ptr [eax],ebx; je found; cmp dword ptr [eax],0; je absent
    inc esi; and esi,511; dec edi; jnz probe
    absent: xor eax,eax; xor edx,edx; jmp done
    found: mov edx,[eax+8]; mov eax,[eax+4]
    done: pop edi; pop esi; pop ebx; ret
    ''')
    return {'ensure':ensure,'mirror':mirror,'lookup':lookup}
