"""Independent, bounded reader for the existing 0x0BB7 Show Mob Info stream."""
def emit(assemble,base,meta,cache,info_db,info_parse):
 drain=base+0x2000;parse=base+0xa000;lookup=base+0xa800
 assemble(parse,r'''
 push ebp; mov ebp,esp; sub esp,8; push ebx; push esi; push edi
 mov esi,[ebp+8]; mov edi,esi; add edi,[ebp+12]
 mov dword ptr [ebp-4],-1
 token:
 cmp esi,edi; jae finish
 cmp byte ptr [esi],0; je finish
 cmp byte ptr [esi],32; jne token_begin
 inc esi; jmp token
 token_begin:
 call number; test edx,edx; jz skip_token
 cmp byte ptr [esi],47; jne percent
 mov ebx,eax; inc esi; call number; test edx,edx; jz skip_token
 test eax,eax; jz skip_token; cmp ebx,eax; ja skip_token
 cmp byte ptr [esi],0; je pair_done
 cmp byte ptr [esi],32; jne skip_token
 pair_done: mov edx,eax; mov eax,ebx; mov ecx,1; jmp done
 percent:
 cmp byte ptr [esi],37; jne skip_token
 cmp eax,100; ja skip_token
 inc esi; cmp esi,edi; jae finish
 cmp byte ptr [esi],0; je save_percent
 cmp byte ptr [esi],32; jne skip_token
 save_percent: mov [ebp-4],eax; jmp token
 skip_token:
 cmp esi,edi; jae finish
 cmp byte ptr [esi],0; je finish
 cmp byte ptr [esi],32; je token
 inc esi; jmp skip_token
 finish:
 mov eax,[ebp-4]; cmp eax,-1; je missing
 mov edx,100; mov ecx,2; jmp done
 missing: xor eax,eax; xor edx,edx; xor ecx,ecx
 done: pop edi; pop esi; pop ebx; mov esp,ebp; pop ebp; ret 8
 number:
 xor eax,eax; xor ecx,ecx
 digit:
 cmp esi,edi; jae invalid
 movzx edx,byte ptr [esi]; sub edx,48; cmp edx,9; ja number_end
 cmp eax,429496729; ja invalid; jne multiply
 cmp edx,5; ja invalid
 multiply: imul eax,eax,10; add eax,edx; inc esi; inc ecx; jmp digit
 number_end: test ecx,ecx; jz invalid
 mov edx,1; ret
 invalid: xor edx,edx; ret
 ''')
 assemble(lookup,f'''
 push ebx; push esi; push edi
 mov ebx,eax; and eax,511; mov esi,eax; mov edi,16
 lookup_loop:
 mov eax,esi; shl eax,4; add eax,{cache}
 cmp dword ptr [eax],ebx; je found
 cmp dword ptr [eax],0; je absent
 inc esi; and esi,511; dec edi; jnz lookup_loop
 absent: xor eax,eax; xor edx,edx; xor ecx,ecx; jmp lookup_done
 found: mov edx,[eax+8]; mov ecx,[eax+12]; mov eax,[eax+4]
 lookup_done: pop edi; pop esi; pop ebx; ret
 ''')
 assemble(drain,f'''
 push ebp; mov ebp,esp; sub esp,48; push ebx; push esi; push edi
 cmp dword ptr [{meta+8}],ecx; je same_world
 mov dword ptr [{meta+8}],ecx
 mov edi,{cache}; mov ecx,2048; xor eax,eax; cld; rep stosd
 mov edi,{info_db}; mov ecx,32768; rep stosd
 same_world:
 mov ebx,dword ptr [{meta}]; test ebx,ebx; jz drain_done
 cmp dword ptr [ebx],0x4558544e; jne drain_done
 cmp dword ptr [ebx+8],0x474e4952; jne drain_done
 cmp dword ptr [ebx+12],1024; jne drain_done
 mov eax,[ebx+4]; mov [ebp-4],eax
 mov edx,dword ptr [{meta+4}]; sub eax,edx; cmp eax,1024; jbe sequence_ok
 mov edx,[ebp-4]; sub edx,1024
 sequence_ok: mov [ebp-8],edx; mov dword ptr [ebp-12],64
 packet_loop:
 mov eax,[ebp-8]; cmp eax,[ebp-4]; je publish
 and eax,1023; shl eax,10; lea esi,[ebx+eax+16]
 mov ecx,[esi]; add esi,4
 cmp word ptr [esi],0x0bb7; jne next_packet
 movzx eax,word ptr [esi+2]; cmp eax,ecx; jne next_packet
 cmp dword ptr [esi+4],0x4558544e; jne next_packet
 cmp eax,653; je v4
 cmp eax,657; je v4
 cmp eax,773; je v3
 cmp eax,777; je v3
 cmp eax,233; je legacy
 cmp eax,237; jne next_packet
 legacy: cmp byte ptr [esi+232],1; jne next_packet
 lea eax,[esi+36]; mov dword ptr [ebp-48],31; cmp byte ptr [eax],0; jne legacy_name
 lea eax,[esi+12]; mov dword ptr [ebp-48],24
 legacy_name: mov [ebp-44],eax
 mov ecx,31; lea edx,[esi+129]; jmp title
 v3: cmp byte ptr [esi+772],1; jne next_packet
 lea eax,[esi+36]; mov dword ptr [ebp-48],128; cmp byte ptr [eax],0; jne v3_name
 lea eax,[esi+12]; mov dword ptr [ebp-48],24
 v3_name: mov [ebp-44],eax
 mov ecx,128; lea edx,[esi+548]; jmp title
 v4: cmp byte ptr [esi+652],1; jne next_packet
 lea eax,[esi+12]; mov [ebp-44],eax; mov dword ptr [ebp-48],128
 mov ecx,128; lea edx,[esi+524]
 title:
 mov [ebp-36],edx; mov [ebp-40],ecx
 mov eax,[esi+8]; test eax,eax; jz next_packet; mov [ebp-16],eax
 push ecx; push edx; call {parse}
 mov [ebp-20],eax; mov [ebp-24],edx; mov [ebp-28],ecx
 mov esi,[ebp-16]; and esi,511; mov ecx,16
 cache_probe:
 mov edi,esi; shl edi,4; add edi,{cache}
 mov eax,[ebp-16]; cmp [edi],eax; je store
 cmp dword ptr [edi],0; je store
 inc esi; and esi,511; dec ecx; jnz cache_probe
 mov edi,[ebp-16]; and edi,511; shl edi,4; add edi,{cache}
 store:
 mov eax,[ebp-16]; mov [edi],eax
 mov eax,[ebp-20]; mov [edi+4],eax
 mov eax,[ebp-24]; mov [edi+8],eax
 mov eax,[ebp-28]; mov [edi+12],eax
 sub edi,{cache}; shl edi,4; add edi,{info_db}
 mov eax,[ebp-16]; mov [edi],eax
 push dword ptr [ebp-48]; push dword ptr [ebp-44]; push dword ptr [ebp-40]; push dword ptr [ebp-36]; push edi
 call {info_parse}
 mov eax,[ebp-8]; inc eax; mov [edi+52],eax
 next_packet: inc dword ptr [ebp-8]; dec dword ptr [ebp-12]; jnz packet_loop
 publish: mov eax,[ebp-8]; mov dword ptr [{meta+4}],eax
 drain_done: pop edi; pop esi; pop ebx; mov esp,ebp; pop ebp; ret
 ''')
 return drain,parse,lookup
