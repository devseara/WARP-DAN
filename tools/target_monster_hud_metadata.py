"""Typed Show Mob Info fields and bounded presentation for the target HUD."""

def emit(assemble,base,db,texts,current,consts,dirty,world,comma,numbers):
    lookup=base+0x4500;parse=base+0x4800;prepare=base+0x5200;strip=base+0x5b00
    chunks=[];cursor=consts
    def literal(value):
        nonlocal cursor
        at=cursor;data=value.encode('utf8')+b'\0';chunks.append((at-base,data));cursor+=len(data);return at
    empty=literal('')
    formats={k:literal(v) for k,v in {
        'both':'Mob Level: %s ♦ Mob ID: %u','level':'Mob Level: %s','id':'Mob ID: %u',
        'element':'Mob Element: %s Level: %s','race':'Mob Race: %s','hp':'%s/%s ♦ %u%%'
    }.items()}
    elements=[literal(s) for s in ('Neutral','Water','Earth','Fire','Wind','Poison','Holy','Dark','Ghost','Undead')]
    races=[literal(s) for s in ('Formless','Undead','Brute','Plant','Insect','Fish','Demon','Demi-Human','Angel','Dragon')]
    # Token parser: validated fields only, and copied packet-owned name bytes.
    src=f'''
    push ebp; mov ebp,esp; sub esp,16; push ebx; push esi; push edi
    mov ebx,[ebp+8]; lea edi,[ebx+4]; xor eax,eax; mov ecx,63; cld; rep stosd
    lea edi,[ebx+64]; mov esi,[ebp+20]; mov ecx,[ebp+24]; cmp ecx,127; jbe name_bound; mov ecx,127
    name_bound: test ecx,ecx; jz name_done
    name_byte: lodsb; stosb; test al,al; jz name_done; dec ecx; jnz name_byte
    mov byte ptr [edi],0
    name_done:
    mov esi,[ebp+12]; mov eax,[ebp+16]; add eax,esi; mov [ebp-4],eax
    token: cmp esi,[ebp-4]; jae parsed; cmp byte ptr [esi],0; je parsed
    cmp byte ptr [esi],32; jne token_start; inc esi; jmp token
    token_start: mov edi,esi
    token_end: cmp esi,[ebp-4]; jae token_ready; cmp byte ptr [esi],0; je token_ready
    cmp byte ptr [esi],32; je token_ready; inc esi; jmp token_end
    token_ready: mov eax,esi; sub eax,edi; mov [ebp-8],eax; mov [ebp-12],esi
    cmp byte ptr [edi],35; jne check_level
    lea edx,[edi+1]; call number; test ecx,ecx; jz next_token
    test eax,eax; jz next_token; mov [ebx+8],eax; or dword ptr [ebx+4],1; jmp next_token
    check_level:
    cmp dword ptr [ebp-8],3; jbe check_element
    cmp word ptr [edi],0x764c; jne check_element; cmp byte ptr [edi+2],46; jne check_element
    lea edx,[edi+3]; call number; test ecx,ecx; jz next_token
    test eax,eax; jz next_token; mov [ebx+12],eax; or dword ptr [ebx+4],2; jmp next_token
    check_element:
    '''
    # Element tokens qualify only when immediately followed by their Lv.N token;
    # this disambiguates element Undead from race Undead and optional mob level.
    for addr in elements:
        src+=f'mov edx,{addr}; call equal; test eax,eax; jnz element_match\n'
    src+='jmp check_race\nelement_match: mov [ebp-16],edx; mov edx,[ebp-12]\n'
    src+='''
    element_space: cmp edx,[ebp-4]; jae check_race; cmp byte ptr [edx],32; jne element_level
    inc edx; jmp element_space
    element_level: lea eax,[edx+3]; cmp eax,[ebp-4]; jae check_race
    cmp word ptr [edx],0x764c; jne check_race; cmp byte ptr [edx+2],46; jne check_race
    add edx,3; mov esi,edx
    level_end: cmp esi,[ebp-4]; jae level_ready; cmp byte ptr [esi],0; je level_ready
    cmp byte ptr [esi],32; je level_ready; inc esi; jmp level_end
    level_ready: call number; test ecx,ecx; jz element_bad
    cmp eax,1; jb element_bad; cmp eax,4; ja element_bad
    mov [ebx+16],eax; or dword ptr [ebx+4],4
    mov [ebp-12],esi; mov esi,[ebp-16]; lea edi,[ebx+20]; call copy_word
    jmp next_token
    element_bad: mov [ebp-12],esi; jmp next_token
    check_race:
    '''
    for addr in races:
        src+=f'mov edx,{addr}; call equal; test eax,eax; jnz race_match\n'
    src+='''
    jmp next_token
    race_match: mov esi,edx; lea edi,[ebx+36]; call copy_word; or dword ptr [ebx+4],8
    next_token: mov esi,[ebp-12]; jmp token
    parsed: pop edi; pop esi; pop ebx; mov esp,ebp; pop ebp; ret 20
    copy_word: mov ecx,15
    copy_byte: lodsb; stosb; test al,al; jz copy_done; dec ecx; jnz copy_byte
    mov byte ptr [edi],0
    copy_done: ret
    equal: push ecx; push esi; xor ecx,ecx
    equal_byte: cmp ecx,[ebp-8]; jae equal_end
    mov al,[edi+ecx]; cmp al,[edx+ecx]; jne unequal
    inc ecx; jmp equal_byte
    equal_end: cmp byte ptr [edx+ecx],0; jne unequal
    mov eax,1; jmp equal_done
    unequal: xor eax,eax
    equal_done: pop esi; pop ecx; ret
    number: xor eax,eax; xor ecx,ecx
    digit: cmp edx,esi; jae number_end
    movzx ecx,byte ptr [edx]; sub ecx,48; cmp ecx,9; ja invalid
    cmp eax,429496729; ja invalid; jne multiply; cmp ecx,5; ja invalid
    multiply: imul eax,eax,10; add eax,ecx; inc edx; jmp digit
    number_end: mov ecx,1; ret
    invalid: xor ecx,ecx; ret
    '''
    assemble(parse,src)
    assemble(lookup,f'''
    push ebx; push esi; push edi
    mov ebx,eax; and eax,511; mov esi,eax; mov edi,16
    probe: mov eax,esi; shl eax,8; add eax,{db}
    cmp [eax],ebx; je found; cmp dword ptr [eax],0; je absent
    inc esi; and esi,511; dec edi; jnz probe
    absent: xor eax,eax
    found: pop edi; pop esi; pop ebx; ret
    ''')
    # Reformat only when this GID's packet revision changes (not every frame).
    assemble(prepare,f'''
    push ebx; push esi; push edi
    mov edi,eax; call {lookup}; mov esi,eax; xor ebx,ebx
    test esi,esi; jz revision; mov ebx,[esi+52]
    revision: cmp dword ptr [{current}],edi; jne changed
    cmp dword ptr [{current+4}],ebx; jne changed
    mov eax,dword ptr [{world}]; cmp dword ptr [{current+8}],eax; je ready
    changed: mov dword ptr [{current}],edi; mov dword ptr [{current+4}],ebx
    mov eax,dword ptr [{world}]; mov dword ptr [{current+8}],eax
    mov dword ptr [{dirty}],1
    mov byte ptr [{texts}],0; mov byte ptr [{texts+128}],0; mov byte ptr [{texts+256}],0
    test esi,esi; jz ready
    mov eax,[esi+12]; mov edx,{numbers}; call {comma}
    mov eax,[esi+16]; mov edx,{numbers+32}; call {comma}
    mov eax,[esi+4]; and eax,3; cmp eax,3; jne single
    push dword ptr [esi+8]; push {numbers}; push {formats['both']}; push {texts}; call 0x529850; add esp,16; jmp element
    single: cmp eax,2; jne id_only
    push {numbers}; push {formats['level']}; push {texts}; call 0x529850; add esp,12; jmp element
    id_only: cmp eax,1; jne element
    push dword ptr [esi+8]; push {formats['id']}; push {texts}; call 0x529850; add esp,12
    element: test dword ptr [esi+4],4; jz race
    push {numbers+32}; lea eax,[esi+20]; push eax; push {formats['element']}; push {texts+128}; call 0x529850; add esp,16
    race: test dword ptr [esi+4],8; jz ready
    lea eax,[esi+36]; push eax; push {formats['race']}; push {texts+256}; call 0x529850; add esp,12
    ready: xor edx,edx; test esi,esi; jz done; cmp byte ptr [esi+64],0; je done; lea edx,[esi+64]
    done: pop edi; pop esi; pop ebx; ret
    ''')
    return {'parse':parse,'lookup':lookup,'prepare':prepare,'strip':strip,'chunks':chunks,'empty':empty,'hp_format':formats['hp']}
