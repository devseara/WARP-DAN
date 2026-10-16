"""Reproduce the v2 culled-scenery crash and check the corrected native path."""
import argparse,json
from pathlib import Path
from unicorn import UcError
from unicorn.x86_const import UC_X86_REG_EIP,UC_X86_REG_ESP,UC_X86_REG_EBP,UC_X86_REG_EDX,UC_X86_REG_EDI,UC_X86_REG_EAX
from verify_graymap import Machine


def run(path):
    v=Machine(path)
    # In the bad span a stray ADD addresses EAX(-2)+0x4D8B9090. Supply the
    # same mapped-memory condition so execution reaches the observed bad CALL.
    v.u.mem_map(0x4D8B9000,0x1000)
    bp=v.sp+0x400;obj=v.alloc(0x180);scratch=v.alloc(32)
    v.put(bp-20,0)
    for reg,value in [(UC_X86_REG_EBP,bp),(UC_X86_REG_ESP,v.sp),(UC_X86_REG_EDX,obj),(UC_X86_REG_EDI,scratch)]:v.u.reg_write(reg,value)
    error=None
    try:v.u.emu_start(0xA7B2D6,0xA7B301,count=1000)
    except UcError as e:error=str(e)
    return dict(path=str(path),eip=hex(v.u.reg_read(UC_X86_REG_EIP)),error=error,
                stack_balanced=v.u.reg_read(UC_X86_REG_ESP)==v.sp,
                renderer_restored=v.u.reg_read(UC_X86_REG_EAX)==v.renderer)


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--broken',type=Path,required=True);ap.add_argument('--fixed',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    before,after=run(args.broken),run(args.fixed)
    assert before['eip']=='0x35b7c2fb' and before['error'],before
    assert after['eip']=='0xa7b301' and not after['error'] and after['stack_balanced'] and after['renderer_restored'],after
    report=dict(exact_reported_crash_reproduced=True,corrected_native_skip_path_passed=True,before=before,after=after,live_accepted=False)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
