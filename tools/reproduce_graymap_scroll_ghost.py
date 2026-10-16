"""Matched old/new emitted UI events and the real native parent repaint gate.

Execute the real root lookup and recursive invalidation. Probe CUIWindow's
native compositor through its root OnDraw decision, mocking only that draw.
This proves cached-parent clearing, not full live pixel/input acceptance.
"""
import argparse
import json
from pathlib import Path
import struct
from unicorn.x86_const import UC_X86_REG_ECX,UC_X86_REG_ESP
from verify_graymap_native_ui import Harness

def clear_flags(h):
    for w in [h.root,h.page,*h.native,*h.rows,h.bar,h.popup]:h.vm.put(w+0x58,0)

def compositor_clears_root(h):
    vm=h.vm
    try:vm.u.mem_map(0,4096)
    except Exception:pass
    vm.put(0,0);draws=[]
    # Test root uses the native Graphics vtable. Only the OnDraw boundary is
    # replaced: CE10..CE59 is the unmodified 2025 native composition code.
    vm.stub(0x9EDE30,0,lambda args:draws.append(vm.u.reg_read(UC_X86_REG_ECX)))
    vm.u.reg_write(UC_X86_REG_ECX,h.root);vm.u.reg_write(UC_X86_REG_ESP,vm.sp)
    vm.u.mem_write(vm.sp,struct.pack('<II',vm.stop,0))
    vm.u.emu_start(0xA1CE10,0xA1CE59,count=1000)
    return draws==[h.root]

def check(folder):
    h=Harness(folder);h.attach();results={}
    clear_flags(h);h.call('@GrayWheel@12',[(-120)&0xFFFFFFFF],h.bar)
    results['scroll_offset']=h.scroll()
    results['scroll_parent_invalidated']=h.vm.get(h.root+0x58)==1
    results['scroll_native_root_draw']=compositor_clears_root(h)
    h.bottom();h.open_preset()
    clear_flags(h);h.click(h.popup,h.menu_x+10,h.vm.get(h.ui+52)+4)
    results['popup_hidden']=h.mode()==0 and h.vm.get(h.popup+0x28)==0
    results['dismiss_parent_invalidated']=h.vm.get(h.root+0x58)==1
    results['dismiss_native_root_draw']=compositor_clears_root(h)
    clear_flags(h);h.call('@GrayDown@16',[5,80],h.bar)
    h.call('@GrayMove@16',[5,0],h.bar);h.call('@GrayUp@16',[5,0],h.bar)
    results['reverse_drag_parent_invalidated']=h.vm.get(h.root+0x58)==1
    results['reverse_drag_native_root_draw']=compositor_clears_root(h)
    results['mouse_released']=h.captured==0
    return results

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--broken',type=Path,required=True);ap.add_argument('--fixed',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    old,new=check(a.broken),check(a.fixed)
    for key in ['scroll_parent_invalidated','scroll_native_root_draw','dismiss_parent_invalidated','dismiss_native_root_draw','reverse_drag_parent_invalidated','reverse_drag_native_root_draw']:
        assert old[key] is False,('old bug not reproduced',key)
        assert new[key] is True,('fixed repaint missing',key)
    assert new['mouse_released'] and new['popup_hidden']
    report=dict(before=old,after=new,old_cached_parent_ghost_reproduced=True,native_parent_clear_verified=True,live_accepted=False)
    a.output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
