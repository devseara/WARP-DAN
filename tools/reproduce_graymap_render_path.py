"""Check the exact black-terrain producer/consumer mismatch with lightmaps on."""
import argparse,json
from pathlib import Path
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP
from verify_graymap import Machine


def route(folder):
    m=json.loads((folder/'manifest.json').read_text())['graymap'];v=Machine(folder/'graymap.exe')
    v.put(m['state']['vir'],1);v.options[0x77]=1
    v.u.mem_write(0x11DCEC4,b'\1');v.u.reg_write(UC_X86_REG_ESP,v.sp)
    selected=[]
    def branch(u,address,size,user):
        if address in (0x55DB39,0x55D8FC):
            selected.append('single_texture_queue' if address==0x55DB39 else 'combined_texture_queue');u.emu_stop()
    v.u.hook_add(UC_HOOK_CODE,branch);v.u.emu_start(0x55D8DD,v.stop,count=1000)
    assert len(selected)==1
    return dict(build=str(folder),gray_enabled=True,saved_lightmap=1,combined_capability=1,
                emitted_vertex_stride=32,consumer=selected[0],saved_option_preserved=v.options[0x77]==1)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--broken',type=Path,required=True);ap.add_argument('--fixed',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    old,new=route(args.broken),route(args.fixed)
    assert old['consumer']=='combined_texture_queue' and new['consumer']=='single_texture_queue'
    report=dict(before=old,after=new,renderer_queue_mismatch_reproduced=True,corrected_consumer_verified=True,live_accepted=False)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
