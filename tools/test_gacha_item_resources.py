"""Check real client item resolution after removing gachaui/item_* overrides."""
import argparse
from pathlib import Path
import struct
from test_gacha_ui import GachaMachine, snapshot, step_snapshot
from test_gacha_events import wallet

def run(exe, game):
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready();m.client_artwork(game)
    data=m.pe.get_memory_mapped_image()
    assert b'gachaui\\item_' not in data
    assert b'item\\%s.bmp' in data
    assert not list((Path(__file__).resolve().parents[1]/'Assets/GachaUI').glob('item_*.bmp'))
    # The boundary substitutes the current native item DB, never a server name
    # or fixed exported artwork list. Arbitrary future IDs follow this same path.
    new_id=999001
    m.item_nodes[new_id]=m.item_nodes[501]
    p=snapshot();struct.pack_into('<I',p,656,new_id);struct.pack_into('<I',p,672,new_id)
    m.receive(p);q=wallet();struct.pack_into('<I',q,60,new_id);m.receive(q)
    def draw():
        m.lookups=[];m.texture_requests=[];m.invoke(c['draw'],obj)
        assert not any('gachaui\\item_' in path for path in m.texture_requests)
        return [path for path in m.texture_requests if '\\item\\' in path]
    before=draw()
    assert m.lookups.count(new_id)==3, 'Featured/reward/ticket must all resolve current ItemId'
    assert len(before)>=3
    # Remapping the same ItemId in the native DB changes all three image paths.
    m.item_nodes[new_id]=m.item_nodes[1161]
    after=draw()
    assert before!=after and sum(a!=b for a,b in zip(before,after))==3
    # Actual dimensions still center within the supplied featured/reward boxes.
    calls=[]
    m.stub(c['blit'],lambda:(calls.append(m.args(4)),m.ret(16)))
    draw()
    for x,y,w,h in [(182,88,34,34),(183,150,36,35)]:
        assert any(px==x+(w-m.r(tex+0x114))//2 and py==y+(h-m.r(tex+0x118))//2
                   for window,tex,px,py in calls), (x,y,calls)
    # Cosmetic rolling icons also use stock resources, without hidden rewards.
    m.receive(step_snapshot(5,m.r(s+44),12,0));draw()
    assert len(m.lookups)>=12 and all(id_!=0 for id_ in m.lookups)
    print('PASS: native featured/reward/ticket/rolling item lookups, arbitrary future ItemIds, changed native resource mapping, exact bitmap centering; no bundled or requested gachaui/item_* images')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('exe');p.add_argument('--game',type=Path,required=True)
    a=p.parse_args();run(a.exe,a.game)
