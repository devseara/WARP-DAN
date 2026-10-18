"""Execute emitted texture flags through the native scaling and DX9 mip gates."""
import argparse
import json
from pathlib import Path
import struct
from verify_graymap import Machine
from unicorn.x86_const import UC_X86_REG_ECX,UC_X86_REG_EDI,UC_X86_REG_ESI,UC_X86_REG_EBX,UC_X86_REG_EBP,UC_X86_REG_ESP

def arguments(folder):
    m=json.loads((folder/'manifest.json').read_text())['graymap'];v=Machine(folder/'graymap.exe');calls=[]
    v.put(m['state']['vir'],1);v.stub(0x568760,20,lambda a:calls.append(a) or 0)
    v.stub(m['colors']['exports']['_GrayPrepare@0'],0,lambda a:0);v.stub(0xA63680,12,lambda a:0)
    v.run(m['ground']['vir'],[0,0,0]);assert len(calls)==1
    return calls[0]

def scaled_size(folder,args,factor):
    v=Machine(folder/'graymap.exe');tex=v.alloc(0x160);received=[]
    v.put(tex,0xFD7160);v.put(0x122B3D8,factor)
    v.stub(0x554070,0,lambda a:v.renderer)
    v.stub(0x560F00,20,lambda a:received.append(a) or tex)
    v.stub(0x56A5C0,28,lambda a:0)
    # CTexMgr::Load forwards get arg3 into native noScale and arg4 into mipmaps.
    v.run(0x5685A0,[512,256,v.alloc(4),1,args[1],args[2],args[3],args[4]])
    assert len(received)==1
    return dict(factor=factor,size=received[0][:2],mipmaps=received[0][3],no_scale=v.get(tex+8)&255)

def levels(folder,mips,mip_capability):
    v=Machine(folder/'graymap.exe');tex=v.alloc(0x160);bp=v.sp-0x400
    v.put(tex+0x124,v.renderer);v.put(tex+12,512);v.put(tex+16,256)
    v.u.mem_write(tex+0x12A,bytes([mips,0]));v.u.mem_write(v.renderer+0x688,bytes([mip_capability]))
    device=v.alloc(4);v.put(device,v.alloc(0x60))
    v.put(bp-0x14,0x200);v.put(bp-0x18,device);v.put(bp-0xD,0)
    for off,value in [(8,512),(12,256),(16,1)]:v.put(bp+off,value)
    v.u.reg_write(UC_X86_REG_EDI,tex);v.u.reg_write(UC_X86_REG_EBP,bp)
    v.u.reg_write(UC_X86_REG_EBX,tex+0x12C);v.u.reg_write(UC_X86_REG_ESI,0x1A)
    v.u.reg_write(UC_X86_REG_ESP,v.sp)
    v.stub(0x542A20,4,lambda a:0)
    # Stop at the device CreateTexture boundary after the unmodified DX9 branch.
    v.u.emu_start(0x569B58,0x569BD4,count=1000)
    sp=v.u.reg_read(UC_X86_REG_ESP)
    return v.get(sp+12)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--broken',type=Path,required=True);p.add_argument('--fixed',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    old_args,new_args=arguments(a.broken),arguments(a.fixed)
    assert old_args[1:]==[0,0,1,0] and new_args[1:]==[0,1,0,0]
    old=[scaled_size(a.broken,old_args,f) for f in [1,2,4]]
    new=[scaled_size(a.fixed,new_args,f) for f in [1,2,4]]
    assert old[-1]['size']==[128,64] and all(x['size']==[512,256] and x['mipmaps']==0 and x['no_scale']==1 for x in new)
    matrix=[dict(auto_mip_capability=t,old_levels=levels(a.broken,1,t),fixed_levels=levels(a.fixed,0,t)) for t in [0,1]]
    assert all(x['fixed_levels']==1 for x in matrix) and matrix[1]['old_levels']==0
    from verify_graymap_native_ui import Harness
    for kind in ['scaled','fallback','wrong_name']:
        h=Harness(a.fixed)
        if kind=='scaled':h.vm.put(h.tex+12,128)
        elif kind=='fallback':h.vm.put(h.tex+8,0)
        else:h.vm.u.mem_write(h.tex+0x24,b'other_texture.tga\0')
        h.call('_GrayPrepare@0');assert not h.uploads and h.vm.get(h.state+16)==0
    report=dict(passed=True,before=old,after=new,mip_matrix=matrix,native_scaling_gate_executed=True,native_dx9_mip_gate_executed=True,rejects_scaled_or_shared_textures=True,live_accepted=False)
    a.output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
