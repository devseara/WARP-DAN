"""Native x86 checks for NPC-owned titles, captions and safe custom banner paths."""
import argparse
import struct
from test_gacha_ui import GachaMachine
from test_gacha_banners import catalog

def run(exe):
    m=GachaMachine(exe);obj=m.ready();s=m.c['state'];paths=[]
    def texture():
        path=m.cstr(m.args(1)[0]);paths.append(path);key=path.split('\\')[-1]
        # Simulate an operator-provided PNG without changing packaged artwork.
        m.ret(4,m.load_texture('banner_2.png' if key=='autumn-2026.png' else key))
    m.stub(0xA8D4A0,texture)
    def packet(filename='autumn-2026.png'):
        p=catalog(count=1);struct.pack_into('<I',p,24,8192)
        for off,size,value in [(64,48,'Event Rewards'),(112,128,'Events'),(688,48,'Payon Festival'),(1936,128,filename)]:
            p[off:off+size]=value.encode().ljust(size,b'\0')
        return p
    def draw(p):
        m.receive(p);paths.clear();m.texts=[];m.invoke(m.c['draw'],obj)
    draw(packet())
    assert any(t=='Event Rewards' and (x,y)==(20,3) for t,x,y,_ in m.texts)
    assert any(t=='Events' and (x,y)==(10,32) for t,x,y,_ in m.texts)
    assert any(t=='Payon Festival' for t,x,y,_ in m.texts)
    assert any(path.endswith('gachaui\\autumn-2026.png') for path in paths)
    for bad in ['../escape.png','dir/file.png','C:event.png','bad%u.png','a..png','event.jpg','x'*64+'.png']:
        draw(packet(bad));assert not any('gachaui\\'+bad in path for path in paths),bad
    # Legacy catalogs retain the old labels and numeric filename fallback.
    draw(catalog(count=1))
    assert any(t=='Gacha' for t,x,y,_ in m.texts) and any(t=='Banners' for t,x,y,_ in m.texts)
    assert any(path.endswith('gachaui\\banner_1.png') for path in paths)
    # A stale machine's metadata is not accepted.
    before=bytes(m.u.mem_read(s+3856,3788));p=packet();struct.pack_into('<I',p,16,88);m.receive(p)
    assert bytes(m.u.mem_read(s+3856,3788))==before
    print('PASS native configurable title/sidebar/banner caption, custom PNG filename, path/format/extension/length rejection, legacy fallback and machine isolation')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('exe');a=p.parse_args();run(a.exe)
