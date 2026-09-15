"""Execute v16's emitted x86 layout/interaction helpers; offline evidence only."""
import argparse
from pathlib import Path
import struct
from PIL import Image
from unicorn.x86_const import UC_X86_REG_EAX
from test_gacha_ui import GachaMachine, snapshot

def run(exe,preview=None,game=None):
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready()
    if game:m.client_artwork(game)
    p=snapshot(admin=True)
    def text(off,size,value):p[off:off+size]=value.encode()[:size-1].ljust(size,b'\0')
    for off,name in [(3528,'Epic'),(3552,'Rare'),(3576,'Common'),(3636,'Legendary')]:text(off,24,name)
    for off,value in [(432,'1.00%'),(464,'5.00%'),(496,'93.90%'),(3604,'0.10%')]:text(off,32,value)
    struct.pack_into('<3I',p,40,100,500,9390);struct.pack_into('<I',p,3600,10);struct.pack_into('<I',p,3660,4)
    text(1840,96,'Legendary: 37/100 | Epic+: 3/10');text(3728,48,'Featured Legendary prizes')
    text(528,128,'Legendary guaranteed within 100 pulls; Epic or better within 10. Pity saves per character.')
    struct.pack_into('<I',p,656,1161)
    for off in (660,664,3472,3476):struct.pack_into('<I',p,off,0)
    struct.pack_into('<4I',p,672,1161,1,3,4)
    text(688,48,'Balmung');text(736,32,'MAIL | Legendary')
    for i in range(1,12):
        tier=struct.unpack_from('<I',p,680+i*96)[0]
        text(736+i*96,32,('FREE | ' if i>=10 else 'x1 | ')+['Epic','Rare','Common'][tier])
    def draw(suffix):
        m.texts=[];m.text_colors=[];m.invoke(c['draw'],obj)
        if preview:
            pix,w,h=m.pixels(obj)
            Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA').save(preview.with_name(preview.stem+'-'+suffix+'.png'))
    m.receive(p);draw('four-tiers')
    expected=[('Common','93.90%'),('Rare','5.00%'),('Epic','1.00%'),('Legendary','0.10%')]
    rate_x=331+int(m.font.getlength('Legendary'))
    for i,(name,rate) in enumerate(expected):
        assert any(t==name and (x,y)==(323,66+i*13) for t,x,y,_ in m.texts)
        assert any(t==rate and (x,y)==(rate_x,66+i*13) for t,x,y,_ in m.texts)
    renamed=any(v in m.pe.get_memory_mapped_image() for v in (b'GachaUI.v19\0',b'GachaUI.v20\0'))
    tabs=[(2,'Zeny Gacha',10,77),(3,'Show Prizes',91,78),(4,'History',173,51),
          (5,'Top Spenders',228,87),
          (6,'Legendary Winners' if renamed else 'Grand Winners',319,116 if renamed else 93),
          (9,'Admin',439 if renamed else 416,48)]
    for id_,label,x,width in tabs:
        hit=next(t for t in m.texts if t[0]==label and t[2]==26)
        measured=int(m.font.getlength(label));assert width==measured+14
        assert hit[1]==x+7,(label,hit)
        for xy in [(x,22),(x+width-1,41),(x+width//2,30)]:
            m.invoke(c['hit'],0,xy);assert m.u.reg_read(UC_X86_REG_EAX)==id_
    assert any(t=='1,000,000 per pull' and (x,y)==(20,368) for t,x,y,_ in m.texts)
    assert any(t=='54,321,000 Zeny' and (x,y)==(531,53) for t,x,y,_ in m.texts)
    assert b'genericsui\\gacha\\itembox_000.png' not in m.pe.get_memory_mapped_image()
    assert sum(t=='54,321,000 Zeny' for t,_,_,_ in m.texts)==1
    assert any(t=='MAIL | Legendary' for t,_,_,_ in m.texts)
    assert any(t=='Featured Legendary prizes' for t,_,_,_ in m.texts)
    if renamed:
        assert b'Grand Winners' not in m.pe.get_memory_mapped_image()
        assert b'Legendary Winners' in m.pe.get_memory_mapped_image()
    # Same total balance remains in the HEADER, never in the confirmation panel.
    struct.pack_into('<H',p,10,3);struct.pack_into('<I',p,20,123);m.receive(p);draw('four-tier-confirmation')
    assert sum(t=='54,321,000 Zeny' for t,_,_,_ in m.texts)==1
    assert not any(t=='54,321,000 Zeny' and y>=176 for t,x,y,_ in m.texts)
    assert any('inventory, or mail' in t for t,_,_,_ in m.texts)
    for page,pages in [(1,10),(10,10),(100,100)]:
        q=snapshot(view=1,page=page,pages=pages);m.receive(q);draw('centered-page-'+str(page))
        label=f'Page {page} / {pages}';span=int(m.font.getlength(label))
        assert any(t==label and x==622+(103-span)//2 and y==360 for t,x,y,_ in m.texts)
    for count in (0,2,5,0xffffffff):
        q=snapshot();struct.pack_into('<I',q,3660,count);before=bytes(m.u.mem_read(s,3856));m.receive(q);assert bytes(m.u.mem_read(s,3856))==before
    print('PASS: four named/rated tiers, Legendary card + mail label, six text-fit tab hitboxes, plain balance/per-pull text with no itembox asset, no modal balance, exact centered 1/10/100-page text and invalid tier-count rejection')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--preview',type=Path);ap.add_argument('--game',type=Path);a=ap.parse_args();run(a.exe,a.preview,a.game)
