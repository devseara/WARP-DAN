"""Native currency skins: white idle, gold selection/press, safe fallbacks."""
import argparse
import struct
from pathlib import Path
from PIL import Image
from test_gacha_ui import GachaMachine, snapshot
from test_gacha_events import wallet

def run(exe, game=None, preview=None):
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready()
    if game:m.client_artwork(game)
    def empty(message=1, request=0):
        p=snapshot(message,request);struct.pack_into('<I',p,52,0)
        for off in [656,660,664,3472,3476,3776,3780,3784]:struct.pack_into('<I',p,off,0)
        return p
    m.receive(empty())
    def draw(selected, pressed=None, shot=None):
        m.texts=[];m.invoke(c['draw'],obj);pix,w,h=m.pixels(obj)
        for currency,(x,width) in enumerate([(664,136),(806,104)]):
            gold=currency==selected or currency==pressed
            assert m.r(pix+4*(360*w+x+40))==(0xfffff3d5 if gold else 0xffffffff),(currency,gold)
            assert m.r(pix+4*(357*w+x+20))==(0xffd0a03c if gold else 0xffd4dfe9)
        if preview and shot:
            preview.mkdir(parents=True,exist_ok=True)
            Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA').save(preview/(shot+'.png'))
    for currency in [0,1]:
        m.receive(wallet(currency=currency));draw(currency,shot='selected-'+str(currency))
    # Mere hover does not select; held pointer paints gold, leaving cancels.
    m.invoke(c['move'],obj,(710,369));draw(1)
    before=len(m.sent);m.invoke(c['down'],obj,(710,369));draw(1,pressed=0,shot='pressed')
    assert m.r(s+7648+56)==1 and len(m.sent)==before
    m.invoke(c['move'],obj,(620,330));draw(1)
    m.invoke(c['up'],obj,(620,330));assert len(m.sent)==before
    # A proper click sends only currency selection. The server owns the choice.
    m.invoke(c['move'],obj,(710,369));m.invoke(c['down'],obj,(710,369));m.invoke(c['up'],obj,(710,369))
    assert len(m.sent)==before+1
    fields=struct.unpack('<HHIHH5I',m.sent[-1]);assert fields[4]==11 and fields[8]==0
    seq=m.r(s+44);m.receive(empty(2,seq));m.receive(wallet(request=seq,currency=0));draw(0)
    # Currency controls remain locked during an active roll; no fake highlight.
    m.w(s+3852,1);before=len(m.sent);m.invoke(c['move'],obj,(850,369));m.invoke(c['down'],obj,(850,369));draw(0)
    m.invoke(c['up'],obj,(850,369));assert len(m.sent)==before;m.w(s+3852,0)
    # Missing textures use the same white/gold native fallback, without changing
    # item-resource resolution or making skin availability a payment authority.
    load=m.load_texture;m.load_texture=lambda key:0 if key.startswith('currency_') else load(key)
    for currency in [0,1]:
        m.receive(wallet(request=seq,currency=currency));draw(currency)
    print('PASS native white idle/gold selection, pressed-only preview, hover/outside cancellation, server-owned choice, rolling input lock and missing-art fallback')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('exe');p.add_argument('--game',type=Path);p.add_argument('--preview',type=Path)
    a=p.parse_args();run(a.exe,a.game,a.preview)
