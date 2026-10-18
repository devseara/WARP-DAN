"""Outlined native client text for every target HUD label."""
def emit(assemble,base,width,height,override_x):
 draw=base+0x4000
 # GDI writes RGB with zero alpha. Pure black would be indistinguishable from
 # untouched transparent pixels, so use #010101 for the outline, then promote
 # its alpha below. Eight neighbours give a complete one-pixel dark contour.
 outline='\n'.join(f'''
 lea eax,[ebx{dx:+d}]; mov edx,[ebp+16]; add edx,{dy}
 push 0; push 0; push 0x00010101; push dword ptr [ebp-4]; push 1; push 0; push dword ptr [ebp+12]; push edx; push eax
 mov ecx,esi; call 0xa25a70
 ''' for dy in (-1,0,1) for dx in (-1,0,1) if dx or dy)
 assemble(draw,f'''
 push ebp; mov ebp,esp; sub esp,12; push ebx; push esi
 mov esi,[ebp+8]; mov eax,[ebp+20]
 mov dword ptr [ebp-4],12
 mov dword ptr [ebp-8],0x00ffffff
 cmp eax,1; je measure
 mov dword ptr [ebp-8],0x00d7e7ee
 cmp eax,3; je measure
 cmp eax,4; je measure
 mov dword ptr [ebp-8],0x00b7d7e7
 cmp eax,2; je measure
 mov dword ptr [ebp-4],14
 mov dword ptr [ebp-8],0x00d7e7ee
 measure:
 push 0; push 0; push dword ptr [ebp-4]; push 1; push 0; push dword ptr [ebp+12]
 mov ecx,esi; call 0xa21c90
 mov ebx,{width}; sub ebx,eax; sar ebx,1
 cmp dword ptr [ebp+20],4; jne positioned
 mov ebx,dword ptr [{override_x}]
 positioned:
 {outline}
 push 0; push 0; push dword ptr [ebp-8]; push dword ptr [ebp-4]; push 1; push 0; push dword ptr [ebp+12]; push dword ptr [ebp+16]; push ebx
 mov ecx,esi; call 0xa25a70
 mov eax,[esi+0x24]; test eax,eax; jz done
 mov byte ptr [eax+0x28],1
 mov eax,[eax+0x18]; test eax,eax; jz done
 mov edx,[ebp+16]; dec edx; test edx,edx; jns band_top; xor edx,edx
 band_top: cmp edx,{height}; jae done
 mov ecx,[ebp+16]; add ecx,[ebp-4]; add ecx,9
 mov ebx,{height}; cmp ecx,ebx; cmovg ecx,ebx
 sub ecx,edx; jle done
 imul edx,edx,{width*4}; add eax,edx; imul ecx,ecx,{width}
 alpha: cmp dword ptr [eax],0; je transparent
 cmp byte ptr [eax+3],0; jne transparent
 or dword ptr [eax],0xff000000
 transparent: add eax,4; dec ecx; jnz alpha
 done: pop esi; pop ebx; mov esp,ebp; pop ebp; ret 16
 ''')
 return draw
