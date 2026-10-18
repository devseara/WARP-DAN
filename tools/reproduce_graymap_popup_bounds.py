"""Matched popup bitmap/viewport coverage and native text layout regression."""
import argparse
import json
from pathlib import Path
from verify_graymap_native_ui import Harness

def check(folder):
    h=Harness(folder);h.attach();h.bottom();h.open_preset()
    h.text_calls=[];h.call('@GrayPopupDraw@8',w=h.popup)
    width,height,_=h.surfaces[h.popup]
    surface=h.vm.get(h.popup+0x24)
    return dict(source_size=[width,height],source_position=[h.vm.get(h.popup+0x1C),h.vm.get(h.popup+0x20)],
        full_graphics_page_covered=width==400 and height==272,
        forced_surface_alpha=bool(bytes(h.vm.u.mem_read(surface+0x28,1))[0]),
        text_rows=[h.string(a[2]) for a in h.text_calls],
        text_inside_source=all(0<=a[0]<width and 0<=a[1] and a[1]+a[5]<=height for a in h.text_calls))

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--broken',type=Path,required=True);p.add_argument('--fixed',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    old,new=check(a.broken),check(a.fixed)
    assert old['full_graphics_page_covered'] and old['forced_surface_alpha']
    meta=json.loads((a.fixed/'manifest.json').read_text())['graymap']['ui']
    assert new['source_size']==[meta.get('fieldWidth',272),94] and not new['full_graphics_page_covered'] and not new['forced_surface_alpha'] and new['text_inside_source']
    assert len(new['text_rows'])==5
    report=dict(before=old,after=new,full_page_popup_source_removed=True,live_accepted=False)
    a.output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
