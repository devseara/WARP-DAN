"""Comma grouping, native group-icon placement, and option refresh bridges."""

def emit(assemble,base,icon_state,icon_path,element_row,options,info_text,dirty,world,hover,width,height):
    comma=base+0x9200;icon_prepare=base+0x9400;icon_draw=base+0x9600;option_refresh=base+0x9b00;tier_gate=base+0x9e00
    assemble(comma,r'''
    push ebp; mov ebp,esp; sub esp,32; push ebx; push esi; push edi
    mov [ebp-32],edx; lea esi,[ebp-1]; mov byte ptr [esi],0; mov ebx,10; xor ecx,ecx
    digit: xor edx,edx; div ebx; add dl,48; dec esi; mov [esi],dl; inc ecx
    test eax,eax; jz copy; cmp ecx,3; jne digit
    dec esi; mov byte ptr [esi],44; xor ecx,ecx; jmp digit
    copy: mov edi,[ebp-32]
    copy_byte: lodsb; stosb; test al,al; jnz copy_byte
    mov eax,[ebp-32]; pop edi; pop esi; pop ebx; mov esp,ebp; pop ebp; ret
    ''')
    # EAX is the original CNameInfo, read only. Icon resources remain owned by
    # the native manager and are reacquired for each redraw, never held stale.
    assemble(icon_prepare,f'''
    xor edx,edx; test eax,eax; jz have_id
    cmp byte ptr [eax+0x98],1; jne have_id
    mov edx,[eax+0x94]; test edx,edx; jns have_id; xor edx,edx
    have_id: cmp dword ptr [{icon_state}],edx; je done
    mov dword ptr [{icon_state}],edx; mov dword ptr [{dirty}],1
    done: ret
    ''')
    # stdcall(window, top). Text and the original 24px icon are centered as one
    # row. Both native path normalization and bitmap lookup are used unchanged.
    assemble(icon_draw,f'''
    push ebp; mov ebp,esp; sub esp,32; push ebx; push esi; push edi
    mov esi,[ebp+8]
    cmp dword ptr [{icon_state}],0; je plain
    push dword ptr [{icon_state}]; push 0x1090ec8; push {icon_path}; call 0x529850; add esp,12
    call 0xa90350; mov edi,eax; test edi,edi; jz plain
    push {icon_path}; mov ecx,edi; call 0xa8e500; test al,al; jz plain
    push {icon_path}; call 0xa9f030; add esp,4; test eax,eax; jz plain
    push eax; mov ecx,edi; call 0xa8d4a0; test eax,eax; jz plain
    mov ebx,eax; mov eax,[ebx+0x114]; cmp eax,1; jb plain; cmp eax,64; ja plain; mov [ebp-4],eax
    mov eax,[ebx+0x118]; cmp eax,1; jb plain; cmp eax,64; ja plain; mov [ebp-8],eax
    push {info_text+128}; push {element_row+128}; push {element_row}; call 0x529850; add esp,12
    push 0; push 0; push 12; push 1; push 0; push {element_row}; mov ecx,esi; call 0xa21c90
    mov [ebp-12],eax; add eax,[ebp-4]; cmp eax,{width}; ja plain
    mov edx,{width}; sub edx,eax; sar edx,1; mov dword ptr [{icon_state+12}],edx
    add edx,[ebp-12]; mov [ebp-16],edx
    mov eax,12; sub eax,[ebp-8]; sar eax,1; add eax,[ebp+12]; test eax,eax; js plain
    mov [ebp-20],eax; add eax,[ebp-8]; cmp eax,{height}; ja plain
    push 4; push dword ptr [ebp+12]; push {element_row}; push esi; call {base+0x4000}
    push 1; push ebx; push dword ptr [ebp-20]; push dword ptr [ebp-16]; mov ecx,esi; call 0xa1d260
    mov eax,[esi+0x24]; test eax,eax; jz done; mov byte ptr [eax+0x28],1
    mov edi,[eax+0x18]; test edi,edi; jz done
    mov eax,[ebp-20]; imul eax,eax,{width}; add eax,[ebp-16]; lea edi,[edi+eax*4]
    mov edx,[ebp-8]
    row: mov ecx,[ebp-4]
    pixel: mov eax,[edi]; and eax,0x00ffffff; cmp eax,0xff00ff; je key_pixel
    cmp dword ptr [edi],0; je next_pixel; cmp byte ptr [edi+3],0; jne next_pixel
    or dword ptr [edi],0xff000000; jmp next_pixel
    key_pixel: mov dword ptr [edi],0
    next_pixel: add edi,4; dec ecx; jnz pixel
    mov eax,{width}; sub eax,[ebp-4]; lea edi,[edi+eax*4]; dec edx; jnz row; jmp done
    plain: push 3; push dword ptr [ebp+12]; push {info_text+128}; push esi; call {base+0x4000}
    done: pop edi; pop esi; pop ebx; mov esp,ebp; pop ebp; ret 8
    ''')
    # Refresh the active hovered monster immediately on either option edge.
    # The source dictionary is still intact, so OFF rebuilds the original rows.
    assemble(option_refresh,f'''
    push ebx; push esi; push edi
    mov esi,ecx; movzx ebx,al
    cmp dword ptr [{options}],ebx; jne changed
    cmp dword ptr [{options+4}],esi; jne changed
    mov eax,dword ptr [{world}]; cmp dword ptr [{options+8}],eax; je done
    changed: mov dword ptr [{options}],ebx; mov dword ptr [{options+4}],esi
    mov eax,dword ptr [{world}]; mov dword ptr [{options+8}],eax
    cmp dword ptr [{hover}],esi; jne done
    mov eax,dword ptr [{hover+4}]; test eax,eax; jz done
    push eax; mov ecx,[esi+0xcc]; call 0xa69eb0; test eax,eax; jz done
    cmp byte ptr [eax+0x314],5; jne done; cmp dword ptr [eax+0x70],3; je done; mov edi,eax
    push dword ptr [edi+0x110]; lea ecx,[esi+0x160]; call 0x5a1460
    test eax,eax; jz done; cmp byte ptr [eax+0x98],1; jne done
    push edi; mov ecx,esi; call 0xc6d1d0
    done: mov eax,ebx; pop edi; pop esi; pop ebx; ret
    ''')
    return {'comma':comma,'icon_prepare':icon_prepare,'icon_draw':icon_draw,'option_refresh':option_refresh,'tier_gate':tier_gate}
