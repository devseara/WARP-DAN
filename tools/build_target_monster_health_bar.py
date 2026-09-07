"""Generate relocatable QJS target HUD from reviewable x86 assembly (2025-07-16)."""
from pathlib import Path
import json, struct
import capstone
from capstone.x86 import X86_OP_IMM,X86_OP_MEM
from keystone import Ks,KS_ARCH_X86,KS_MODE_32
ROOT=Path(__file__).resolve().parents[1]
BASE=0x2000000; STATE=BASE+0xe000; NAME=STATE+64; VT=BASE+0xe100
UPDATE=BASE+0x100; DRAW=BASE+0x1000; LOAD=BASE+0x6000; BLIT=BASE+0x7000; DTOR=BASE+0xd000
MANIFEST=json.loads((ROOT/'Assets/TargetMonsterHUD/assets.json').read_text(encoding='utf8'))
from target_monster_hud_layout import make_layout
W,H=MANIFEST['canvas']; layout=make_layout(W,H,BASE)
BMP_SIZE=layout['bmp_size']; BUFFER_STRIDE=layout['buffer_stride']; BUFFERS=layout['buffers']
INFO_DB=layout['info_db']; INFO_TEXT=layout['info_rows']; INFO_CURRENT=layout['current']
HP_TEXT=layout['hp_text']; NUMBERS=layout['number_buffers']; ICON_STATE=layout['icon_state']
OPTIONS=layout['options']; ICON_PATH=layout['icon_path']; ELEMENT_ROW=layout['element_row']
INFO_CONST=layout['constants']; TOTAL=layout['allocation_size']
PATHS=BASE+0xe200; STATUS=BASE+0xf000; PERCENT=HP_TEXT
HOVERSTATE=BASE+0xe0e0; TARGETSTATE=BASE+0xe0d0
TIERLABELS=BASE+0xf280; RINGMETA=BASE+0xe0c0; HPCACHE=BASE+0xb000
FILENAMES=[t[k] for t in MANIFEST['tiers'] for k in ('empty','full')]
ks=Ks(KS_ARCH_X86,KS_MODE_32); cs=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32);cs.detail=True
chunks=[]; relocs=[]
def assemble(at,source):
 code=bytes(ks.asm(source,at)[0])
 for i in cs.disasm(code,at):
  if i.imm_size and any(o.type==X86_OP_IMM for o in i.operands):
   value=next(o.imm for o in i.operands if o.type==X86_OP_IMM)&0xffffffff
   if i.mnemonic in ('call','jmp') or i.mnemonic.startswith('j'):
    if not BASE<=value<BASE+TOTAL:relocs.append([i.address-BASE+i.imm_offset,-1])
   elif BASE<=value<BASE+TOTAL:relocs.append([i.address-BASE+i.imm_offset,1])
  if i.disp_size and BASE<=i.disp<BASE+TOTAL:relocs.append([i.address-BASE+i.disp_offset,1])
 chunks.append((at-BASE,code))
# The displaced call is executed exactly once; preserve its return registers/flags.
# Observe native A797B0's hit-test descriptor in EDI after the UI blocker lookup.
# Replay A47B90 exactly once with its original argument/ECX, preserve its result,
# all registers/flags, and the original thiscall ret-4 stack cleanup.
assemble(BASE,f"""
push dword ptr [esp+4]; call 0xa47b90
pushfd; pushad
mov dword ptr [{HOVERSTATE}],esi
mov dword ptr [{HOVERSTATE+4}],0
cmp dword ptr [esi],0x10904b8; jne observe_done
test eax,eax; jnz observe_done
test ebx,ebx; jnz observe_done
test edi,edi; jz observe_done
mov eax,[edi+0x18]; mov dword ptr [{HOVERSTATE+4}],eax
observe_done: mov ecx,esi; call {UPDATE}
popad; popfd; ret 4
""")
assemble(DTOR,f'''cmp dword ptr [{STATE}],ecx; jne stock; mov dword ptr [{STATE}],0; stock: jmp 0x83bd30''')
from target_monster_hud_showmobinfo import emit as emit_info
from target_monster_hud_text import emit as emit_text
from target_monster_hud_metadata import emit as emit_metadata
from target_monster_hud_presentation import emit as emit_presentation
PRESENT=emit_presentation(assemble,BASE,ICON_STATE,ICON_PATH,ELEMENT_ROW,OPTIONS,INFO_TEXT,STATE+12,RINGMETA+8,HOVERSTATE,W,H)
METADATA=emit_metadata(assemble,BASE,INFO_DB,INFO_TEXT,INFO_CURRENT,INFO_CONST,STATE+12,RINGMETA+8,PRESENT['comma'],NUMBERS)
DRAIN,PARSE,LOOKUP=emit_info(assemble,BASE,RINGMETA,HPCACHE,INFO_DB,METADATA['parse'])
TEXT=emit_text(assemble,BASE,W,H,ICON_STATE+12)
# Publish visibility only after target validation. A name refresh may reuse the
# previous title only for the exact same world, actor instance, and GID.
# Genuine target loss invalidates that identity immediately, without a timer.
# Player death disables stale attack fallback, but never blocks a valid hover.
assemble(UPDATE,f"""
push ebp; mov ebp,esp; sub esp,24; push ebx; push esi; push edi
mov esi,ecx
mov dword ptr [{STATE+12}],0

mov dword ptr [ebp-20],0; mov dword ptr [ebp-24],0
cmp dword ptr [esi],0x10904b8; jne done

mov ecx,[esi+0xcc]; test ecx,ecx; jz done
push ecx; call {DRAIN}; pop ecx

mov edx,[ecx+0x2c]; test edx,edx; jz done
mov [ebp-12],edx
push 0xd5; call 0x68ea70; add esp,4; mov ecx,esi; call {PRESENT['option_refresh']}
test eax,eax; jz done

mov edx,[ebp-12]

mov dword ptr [ebp-16],0
mov eax,[edx+0x500];
cmp dword ptr [edx+0x70],3; je check_hover
cmp eax,1; je save_attack
cmp eax,5; je save_attack
cmp eax,3; jne check_hover
save_attack: mov eax,[edx+0x514]; mov [ebp-16],eax
check_hover:

cmp dword ptr [{HOVERSTATE}],esi; jne attack_fallback
mov eax,dword ptr [{HOVERSTATE+4}]; test eax,eax; jz attack_fallback

push eax; mov ecx,[esi+0xcc]; call 0xa69eb0; test eax,eax; jz attack_fallback
cmp byte ptr [eax+0x314],5; jne attack_fallback
mov edi,eax; jmp selected
attack_fallback:
mov eax,[ebp-16]; test eax,eax; jz done

push eax; mov ecx,[esi+0xcc]; call 0xa69eb0; test eax,eax; jz done
cmp byte ptr [eax+0x314],5; jne done
mov edi,eax
selected:
mov [ebp-20],edi; mov eax,[edi+0x110]; mov [ebp-24],eax

cmp dword ptr [edi+0x70],3; je done
mov dword ptr [ebp-4],0; mov dword ptr [ebp-8],0
mov dword ptr [{INFO_CURRENT+12}],0

mov ebx,[edi+0x300]; test ebx,ebx; jz name_lookup

cmp dword ptr [ebx],0x102be50; jne name_lookup

cmp dword ptr [ebx+0xa4],0; je name_lookup
cmp dword ptr [ebx+0xa4],-1; je name_lookup
cmp dword ptr [ebx+0xa0],0; je done
cmp dword ptr [ebx+0xa0],-1; je name_lookup
mov eax,[ebx+0xa0]; mov [ebp-4],eax
mov eax,[ebx+0xa4]; mov [ebp-8],eax
mov dword ptr [{INFO_CURRENT+12}],1
name_lookup:
cmp dword ptr [ebp-8],0; jne info_ready
mov eax,[edi+0x110]; call {LOOKUP}; test edx,edx; jz info_ready
mov [ebp-4],eax; mov [ebp-8],edx; mov dword ptr [{INFO_CURRENT+12}],ecx; test eax,eax; jz done
info_ready:
movzx eax,byte ptr [edi+0x304]; cmp eax,2; jbe tier_ok
xor eax,eax
tier_ok: mov dword ptr [{STATE+4}],eax

mov eax,[edi+0x110]; call {METADATA["prepare"]}; push edx
push dword ptr [edi+0x110]; lea ecx,[esi+0x160]; call 0x5a1460
push eax; call {PRESENT['icon_prepare']}; pop eax; pop edx
test edx,edx; jnz inline_name
test eax,eax; jz name_unavailable
cmp byte ptr [eax+0x98],1; jne name_unavailable
lea edx,[eax+4]; cmp dword ptr [eax+0x18],16; jb inline_name
mov edx,[eax+4]
inline_name: test edx,edx; jz name_unavailable
cmp byte ptr [edx],0; je name_unavailable
mov edi,{NAME}; xor ecx,ecx; jmp copy_name
name_unavailable:
mov eax,[esi+0xcc]; cmp eax,dword ptr [{TARGETSTATE}]; jne done
mov eax,[ebp-20]; cmp eax,dword ptr [{TARGETSTATE+4}]; jne done
mov eax,[ebp-24]; cmp eax,dword ptr [{TARGETSTATE+8}]; jne done
cmp byte ptr [{NAME}],0; je done

jmp copied
copy_name: mov al,[edx+ecx]; cmp al,97; jb copy_upper; cmp al,122; ja copy_upper; sub al,32
copy_upper: cmp [edi+ecx],al; je copy_same
mov dword ptr [{STATE+12}],1
copy_same: mov [edi+ecx],al; test al,al; jz copied
inc ecx; cmp ecx,127; jb copy_name
mov byte ptr [edi+127],0
copied:

mov eax,dword ptr [{STATE+4}]; shl eax,1; push eax; call {LOAD}; pop ecx
test eax,eax; jz done
lea eax,[ecx+1]; call {LOAD}; test eax,eax; jz done

mov ebx,dword ptr [{STATE}]; test ebx,ebx; jnz have_window
push 0xb4; call 0xdbbc4f; add esp,4; test eax,eax; jz done
mov ecx,eax; call 0x8361b0; mov ebx,eax
mov dword ptr [ebx],{VT}; mov dword ptr [{STATE}],ebx
push {H}; push {W}; mov ecx,ebx; call 0xa1cb70
push ebx; mov ecx,0x131f4e8; call 0xa2d240
have_window:
mov eax,dword ptr [0x12515f8]; test eax,eax; jz done
mov eax,[eax+0x28]; sub eax,{W}; sar eax,1
push 24; push eax; mov ecx,ebx; call 0xa23450
mov eax,[ebp-4]; cmp [ebx+0xa0],eax; jne refresh
mov eax,[ebp-8]; cmp [ebx+0xa4],eax; jne refresh
cmp dword ptr [{STATE+12}],0; jne refresh
mov eax,dword ptr [{INFO_CURRENT+12}]; cmp eax,dword ptr [{INFO_CURRENT+16}]; jne refresh
mov eax,dword ptr [{STATE+4}]; cmp dword ptr [{STATE+24}],eax; je show_hud
refresh:
push dword ptr [ebp-8]; push dword ptr [ebp-4]; mov ecx,ebx; call 0x863f10
mov eax,dword ptr [{STATE+4}]; mov dword ptr [{STATE+24}],eax
mov eax,dword ptr [{INFO_CURRENT+12}]; mov dword ptr [{INFO_CURRENT+16}],eax
mov dword ptr [ebx+0x58],1
show_hud:
mov eax,[esi+0xcc]; mov dword ptr [{TARGETSTATE}],eax
mov eax,[ebp-20]; mov dword ptr [{TARGETSTATE+4}],eax
mov eax,[ebp-24]; mov dword ptr [{TARGETSTATE+8}],eax
mov dword ptr [ebx+0x28],1

jmp update_done
done:
mov dword ptr [{TARGETSTATE}],0
mov dword ptr [{TARGETSTATE+4}],0
mov dword ptr [{TARGETSTATE+8}],0
mov eax,dword ptr [{STATE}]; test eax,eax; jz update_done
mov dword ptr [eax+0x28],0
update_done:
pop edi; pop esi; pop ebx; mov esp,ebp; pop ebp; ret
""")
# Native CFile uses the same CFileMgr as stock assets. Open(path,0,1,0)
# prepends the configured data root and obeys existing folder/GRF priority.
# The initialized 44-byte stack object is destroyed on every opened path.
assemble(LOAD,f"""
push ebp; mov ebp,esp; sub esp,48; push ebx; push esi; push edi
mov ebx,eax; cmp ebx,5; ja failure
cmp dword ptr [{STATUS}+ebx*4],1; je success
cmp dword ptr [{STATUS}+ebx*4],2; je failure
mov dword ptr [{STATUS}+ebx*4],2
lea edi,[ebp-48]; xor eax,eax; mov ecx,11; cld; rep stosd
mov dword ptr [ebp-48],0xfd3074
mov dword ptr [ebp-44],-1
mov dword ptr [ebp-8],15
mov eax,ebx; shl eax,8; add eax,{PATHS}
push 0; push 1; push 0; push eax; lea ecx,[ebp-48]; call 0x573750
test al,al; jz close_fail
cmp dword ptr [ebp-32],{BMP_SIZE}; jne close_fail
imul esi,ebx,{BUFFER_STRIDE}; add esi,{BUFFERS}
push {BMP_SIZE}; push esi; lea ecx,[ebp-48]; call 0x573980
test al,al; jz close_fail
cmp word ptr [esi],0x4d42; jne close_fail
cmp dword ptr [esi+10],122; jne close_fail
cmp dword ptr [esi+14],108; jne close_fail
cmp dword ptr [esi+18],{W}; jne close_fail
cmp dword ptr [esi+22],{H}; jne close_fail
cmp dword ptr [esi+26],0x00200001; jne close_fail
cmp dword ptr [esi+30],3; jne close_fail
cmp dword ptr [esi+54],0x00ff0000; jne close_fail
cmp dword ptr [esi+58],0x0000ff00; jne close_fail
cmp dword ptr [esi+62],0x000000ff; jne close_fail
cmp dword ptr [esi+66],0xff000000; jne close_fail
push 0; lea ecx,[ebp-48]; call 0x519200
mov dword ptr [{STATUS}+ebx*4],1
success: mov eax,1; jmp load_done
close_fail: push 0; lea ecx,[ebp-48]; call 0x519200
failure: xor eax,eax
load_done: pop edi; pop esi; pop ebx; mov esp,ebp; pop ebp; ret
""")
# stdcall(window, BMP, left, right, top, bottom), V4 BGRA32 bottom-up -> native ARGB, preserving the source alpha.
assemble(BLIT,f"""
push ebp; mov ebp,esp; sub esp,24; push ebx; push esi; push edi
mov eax,[ebp+8]; test eax,eax; jz blit_done
mov eax,[eax+0x24]; test eax,eax; jz blit_done
cmp dword ptr [eax+4],{W}; jne blit_done
mov edi,[eax+0x18]; test edi,edi; jz blit_done
mov byte ptr [eax+0x28],1
mov eax,[ebp+16]; test eax,eax; js blit_done
mov ecx,[ebp+20]; cmp ecx,{W}; ja blit_done
sub ecx,eax; jle blit_done; mov [ebp-4],ecx
mov ecx,[ebp+24]; test ecx,ecx; js blit_done
mov edx,[ebp+28]; cmp edx,{H}; ja blit_done
sub edx,ecx; jle blit_done; mov [ebp-8],edx
imul edx,ecx,{W}; add edx,eax; lea edi,[edi+edx*4]; mov [ebp-12],edi
mov edx,{H-1}; sub edx,ecx; imul edx,edx,{W*4}
shl eax,2; add edx,eax
mov esi,[ebp+12]; add esi,122; add esi,edx; mov [ebp-16],esi
blit_row: mov edi,[ebp-12]; mov esi,[ebp-16]; mov ecx,[ebp-4]
blit_pixel: mov eax,[esi]; test eax,0xff000000; jz blit_skip
mov [edi],eax
blit_skip: add esi,4; add edi,4; dec ecx; jnz blit_pixel
add dword ptr [ebp-12],{W*4}; sub dword ptr [ebp-16],{W*4}; dec dword ptr [ebp-8]; jnz blit_row
blit_done: pop edi; pop esi; pop ebx; mov esp,ebp; pop ebp; ret 24
""")
s=['push ebp; mov ebp,esp; push ebx; push esi; push edi; mov esi,ecx',
   'push 0; call 0xa1cb30',f'mov eax,dword ptr [{STATE+4}]; cmp eax,2; je mvp; cmp eax,1; je mini; jmp normal']
for index,tier in enumerate(MANIFEST['tiers']):
 label=tier['name'];l,t,r,b=tier['fill'];empty=BUFFERS+index*2*BUFFER_STRIDE;full=empty+BUFFER_STRIDE
 s.append(f"""{label}:
push {H}; push 0; push {W}; push 0; push {empty}; push esi; call {BLIT}
cmp dword ptr [esi+0xa4],0; je text
mov eax,[esi+0xa0]; cmp eax,[esi+0xa4]; jbe {label}_clamp; mov eax,[esi+0xa4]
{label}_clamp: mov ecx,{r-l}; mul ecx; div dword ptr [esi+0xa4]; add eax,{l}
push {b}; push {t}; push eax; push {l}; push {full}; push esi; call {BLIT}
jmp text""")
s.append(f"""text:
mov eax,dword ptr [{STATE+4}]; imul eax,eax,16; add eax,{TIERLABELS}
mov edx,{MANIFEST['tiers'][0]['label_top']}
cmp dword ptr [{STATE+4}],0; je label_ready
mov edx,{MANIFEST['tiers'][1]['label_top']}
cmp dword ptr [{STATE+4}],1; je label_ready
mov edx,{MANIFEST['tiers'][2]['label_top']}
label_ready: push 2; push edx; push eax; push esi; call {TEXT}
push 0; push {MANIFEST['name_top']}; push {NAME}; push esi; call {TEXT}
cmp dword ptr [esi+0xa4],0; je pct_unknown
mov eax,[esi+0xa0]; cmp eax,[esi+0xa4]; jbe pct_clamp; mov eax,[esi+0xa4]
pct_clamp: mov ecx,100; mul ecx; div dword ptr [esi+0xa4]
cmp dword ptr [{INFO_CURRENT+12}],2; je pct_only
push eax
mov eax,[esi+0xa0]; mov edx,{NUMBERS}; call {PRESENT['comma']}
mov eax,[esi+0xa4]; mov edx,{NUMBERS+16}; call {PRESENT['comma']}
pop eax
push eax; push {NUMBERS+16}; push {NUMBERS}; push {METADATA['hp_format']}; push {PERCENT}; call 0x529850; add esp,20; jmp pct_draw
pct_only: push eax; push {STATE+16}; push {PERCENT}; call 0x529850; add esp,12; jmp pct_draw
pct_unknown:
mov dword ptr [{PERCENT}],0x75205048
mov dword ptr [{PERCENT+4}],0x6f6e6b6e
mov dword ptr [{PERCENT+8}],0x00006e77
pct_draw:
mov eax,dword ptr [{STATE+4}]
mov edx,{MANIFEST['tiers'][0]['percent_top']}; test eax,eax; jz pct_ready
mov edx,{MANIFEST['tiers'][1]['percent_top']}; cmp eax,1; je pct_ready
mov edx,{MANIFEST['tiers'][2]['percent_top']}
pct_ready: push 1; push edx; push {PERCENT}; push esi; call {TEXT}
mov eax,dword ptr [{STATE+4}]; mov ebx,108; test eax,eax; jz details_ready
mov ebx,124; cmp eax,1; je details_ready; mov ebx,153
details_ready:
cmp byte ptr [{INFO_TEXT}],0; je second_detail
push 3; push ebx; push {INFO_TEXT}; push esi; call {TEXT}
second_detail: add ebx,24
cmp byte ptr [{INFO_TEXT+128}],0; je third_detail
push ebx; push esi; call {PRESENT['icon_draw']}
third_detail: add ebx,24
cmp byte ptr [{INFO_TEXT+256}],0; je details_done
push 3; push ebx; push {INFO_TEXT+256}; push esi; call {TEXT}
details_done: pop edi; pop esi; pop ebx; pop ebp; ret""")
assemble(DRAW,'\n'.join(s))
assemble(METADATA['strip'],f"""
push dword ptr [esp+4]; call 0xd8e9d0
pushfd; pushad
cmp byte ptr [edi+0x314],5; jne leave_name
push 0xd5; call 0x68ea70; add esp,4; test al,al; jz leave_name
movzx eax,byte ptr [edi+0x304]; cmp eax,2; jbe strip_tier; xor eax,eax
strip_tier: shl eax,1; push eax; call {LOAD}; pop ecx; test eax,eax; jz leave_name
lea eax,[ecx+1]; call {LOAD}; test eax,eax; jz leave_name
push 0; push {METADATA['empty']}; lea ecx,[ebp-0x1d8]; call 0x4f1940
push 0; push {METADATA['empty']}; lea ecx,[ebp-0x160]; call 0x4f1940
mov dword ptr [ebp-0x148],0
leave_name: popad; popfd; ret 4
""")
# With no group ID, native balloons would otherwise fall back to a boss badge.
# Clear only this producer's tier argument while relocation is enabled.
assemble(PRESENT['tier_gate'],f"""
push dword ptr [esp+4]; call 0xc43230
pushfd; pushad
cmp byte ptr [edi+0x314],5; jne leave_tier
push 0xd5; call 0x68ea70; add esp,4; test al,al; jz leave_tier
movzx eax,byte ptr [edi+0x304]; cmp eax,2; jbe tier_index; xor eax,eax
tier_index: shl eax,3; cmp dword ptr [{STATUS}+eax],1; jne leave_tier
cmp dword ptr [{STATUS+4}+eax],1; jne leave_tier
mov byte ptr [ebp-0x1e4],0
leave_tier: popad; popfd; ret 4
""")
assert max(off+len(b) for off,b in chunks)<0xe000
chunks.extend(METADATA["chunks"])
chunks.append((ELEMENT_ROW+128-BASE,"%s ♦ \0".encode("utf8")))
for index,tier in enumerate(MANIFEST['tiers']):chunks.append((TIERLABELS-BASE+index*16,(tier['label']+'\0').encode('ascii')))
chunks.append((STATE+16-BASE,b'%u%%\0'))
for index,name in enumerate(FILENAMES):
 relative=MANIFEST['resource_root'].removeprefix('data/').replace('/',chr(92))+chr(92)+name
 encoded=(relative+'\0').encode('latin1');assert len(encoded)<256
 chunks.append((PATHS-BASE+index*256,encoded))
# Fail generation if a helper outgrows its reserved cave or initialized data.
ordered=sorted((off,off+len(data)) for off,data in chunks)
for prior,nxt in zip(ordered,ordered[1:]):
 assert prior[1]<=nxt[0],('overlapping HUD chunks',prior,nxt)
blob=bytearray(TOTAL)
for off,b in chunks:blob[off:off+len(b)]=b
# copy native vtable at patch time, then substitute only draw/destructor.
chunks_json=json.dumps([[o,b.hex(' ').upper()] for o,b in chunks])
qjs='''/*
 * TargetMonsterHealthBar: top-center native HP HUD for 2025-07-16 Ragexe.
 * Description: Replace monster nameplates with a native target HUD while
 * hovering or attacking. /monsterhp restores the stock presentation when off.
 * Target: 2025-07-16 Ragexe; guarded static hooks, no runtime code patching.
 * Generated from tools/build_target_monster_health_bar.py. See the contract
 * in docs/target-monster-health-bar.md for ABI evidence and live acceptance.
 */
TargetMonsterHealthBar = function(_) {
\tif (Exe.BuildDate !== 20250716) throw Error("TargetMonsterHealthBar: requires 2025-07-16");
\tconst check = (va, hex) => {
\t\tconst phy = Exe.Vir2Phy(va);
\t\tif (Exe.GetHex(phy, hex.replace(/ /g, '').length / 2).replace(/ /g, '').toUpperCase() !== hex.replace(/ /g, '').toUpperCase())
\t\t\tthrow Error("TargetMonsterHealthBar: profile mismatch at " + va.toString(16));
\t};
\tcheck(0xC76591, "E8 FA 15 DD FF");
\tcheck(0xC6D308, "E8 C3 16 12 00");
\tcheck(0xC6D355, "E8 D6 5E FD FF");
\tcheck(0xC76580, "E8 2B 32 E0 FF");
\tcheck(0x8361B0, "55 8B EC 6A FF 68 D5 C3 E9 00");
\tcheck(0x573750, "55 8B EC 6A FF 68 45 AB E1 00");
\tcheck(0x573980, "55 8B EC 51 56 8B F1");
\tcheck(0xCF33F0, "55 8B EC 8B 89 CC 00 00 00");
\tcheck(0x102BEA0, "80 48 85 00");
\tcheck(0xD43414, "8B 97 00 05 00 00");
\tcheck(0xCF3E4C, "88 87 04 03 00 00");
\tCustomPacketDispatch.install(`${_}.Info`, ["EXTN"]);
\tconst ring = CACHE.get("CustomPacketDispatch.Routes").routes.EXTN;
\tif (!ring || ring.transport !== "ring-v2") throw Error("TargetMonsterHealthBar: EXTN ring is unavailable");
\tconst [phy, vir] = Exe.Allocate(ALLOCSIZE, 0x10);
\tExe.SetHex(phy, "00 ".repeat(ALLOCSIZE).trim());
\tfor (const [off, hex] of CHUNKS) Exe.SetHex(phy + off, hex);
\tconst delta = vir - 0x02000000;
\tfor (const [off, sign, original] of RELOCS)
\t\tExe.SetUint32(phy + off, (original + sign * delta) >>> 0);
\tExe.SetUint32(phy + 0xE0C0, ring.blockVir);
\tExe.SetHex(phy + 0xE0FC, Exe.GetHex(Exe.Vir2Phy(0x102BE4C), 4));
\tExe.SetHex(phy + 0xE100, Exe.GetHex(Exe.Vir2Phy(0x102BE50), 0xD4));
\tExe.SetUint32(phy + 0xE100, vir + 0xD000);
\tExe.SetUint32(phy + 0xE150, vir + 0x1000);
\tAutoHook(Exe.Vir2Phy(0xC76591), "E9" + Filler(1), {isCall: true, targets: {1: vir}});
\tAutoHook(Exe.Vir2Phy(0xC6D308), "E9" + Filler(1), {isCall: true, targets: {1: vir + 0x5B00}});
\tAutoHook(Exe.Vir2Phy(0xC6D355), "E9" + Filler(1), {isCall: true, targets: {1: vir + 0x9E00}});
\treturn true;
};
TargetMonsterHealthBar.validate = () => Exe.BuildDate === 20250716;
'''.replace('ALLOCSIZE',str(TOTAL)).replace('CHUNKS',chunks_json).replace('RELOCS',json.dumps([[off, sign, struct.unpack_from('<I', blob, off)[0]] for off, sign in relocs]))
asset_dir=MANIFEST['resource_root']
qjs += "\nTargetMonsterHealthBar.onApplied = function() {\n\tif (Warp.TestMode) return;\n"
qjs += "\tconst relative = " + json.dumps(asset_dir) + ";\n"
qjs += "\tconst source = Warp.Path + '/' + relative;\n\tconst target = System.DirPath(Warp.TgtExe) + '/' + relative;\n"
qjs += "\tif (source.toLowerCase() === target.toLowerCase()) return;\n"
qjs += "\tif (!System.MkDir(target)) throw Error('TargetMonsterHealthBar: cannot create ' + target);\n"
qjs += "\tfor (const file of " + json.dumps(FILENAMES) + ") {\n"
qjs += "\t\tif (!System.Copy(source + '/' + file, target + '/' + file, true))\n\t\t\tthrow Error('TargetMonsterHealthBar: cannot copy ' + file);\n\t}\n};\n"
(ROOT/'Scripts/Patches/TargetMonsterHealthBar.qjs').write_bytes(qjs.replace('\n','\r\n').encode())
print('Generated',sum(len(b) for _,b in chunks),'code bytes;',len(relocs),'relocations')
