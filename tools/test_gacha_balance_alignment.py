"""Native Gacha countdown color and bounded right-aligned wallet balances."""
import argparse
from pathlib import Path
from PIL import Image
from test_gacha_ui import GachaMachine
from test_gacha_events import wallet

def run(exe, game=None, preview=None):
    m=GachaMachine(exe);obj=m.ready()
    if game:m.client_artwork(game)
    def draw(p):
        m.receive(p);m.texts=[];m.text_colors=[];m.invoke(m.c['draw'],obj)
    for i,(zeny,tickets) in enumerate([('0z','0'),('74,005,000z','30'),('2,147,483,647z','3,000,000')]):
        p=wallet(currency=i%2)
        p[240:272]=zeny.encode().ljust(32,b'\0')
        p[272:336]=tickets.encode().ljust(64,b'\0')
        draw(p)
        for value,left,right in [(zeny,698,788),(tickets,840,898)]:
            spans=[(x,y) for text,x,y,_ in m.texts if text==value and y==363]
            assert len(spans)==1,(value,spans)
            x,y=spans[0]
            assert x>=left and x+int(m.font.getlength(value))==right,(value,x,right)
        assert any(text.startswith('Ends in:') and color==0x2020cc for text,color,x,y in m.text_colors)
        assert not any(text in ('Zeny','Prontera Ticket') for text,x,y,_ in m.texts)
        if i==1 and preview:
            pix,w,h=m.pixels(obj);preview.parent.mkdir(parents=True,exist_ok=True)
            Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA').save(preview)
    draw(wallet(seconds=0))
    assert any(text=='Event ended' and color==0x2020cc for text,color,x,y in m.text_colors)
    assert not m.sent,'Painting balances must not send purchases'
    print('PASS native red countdown/expiry, exact right-edge alignment for zero/normal/max Zeny and ticket counts, full numeric strings, fixed baseline and no extra requests')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('exe');p.add_argument('--game',type=Path);p.add_argument('--preview',type=Path)
    a=p.parse_args();run(a.exe,a.game,a.preview)
