"""Execute the actual patched DRUI v4 x86 receive, render and reveal paths."""
import argparse,struct
from pathlib import Path
from test_daily_rewards_ui import DailyMachine,snapshot

def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    m=DailyMachine(args.exe);s=m.c['state'];a=m.c['animation'];assert m.daily_version>=4
    def begin(count=None):
        if m.r(s+28):m.click(906,11)
        m.invoke(m.c['toggle'],0)
        assert struct.unpack_from('<II',m.sent[-1],16)==(0x35555244 if m.daily_version>=5 else 0x34555244,0x32555244)
        m.reply(six=True,total=20);m.click(338,44)
        m.preview(args.output/'six-ready.png')
        assert sum(t[0]=='Ready' for t in m.texts)==6
        m.click(790,366);assert struct.unpack_from('<HH',m.sent[-1],8)==(4,4)
        if count is not None:m.reply(six=True,total=20,roll=count)
    for count in range(1,7):
        begin(count);sent=len(m.sent)
        for frame in range(11+3*(count-1)):m.advance(100)
        assert not m.r(s+52) and m.r(a+m.anim_revealed)==count
        m.preview(args.output/f'roll-{count}.png')
        assert sum(t[0]=='Received' for t in m.texts)==count
        assert sum(t[0]=='No reward' for t in m.texts)==6-count
        assert len(m.sent)==sent,'reveals sent extra requests'
    # The sixth result is separate from the five-item prefix and pool page.
    assert any(item==506 and y<350 for item,x,y in m.icons)
    obj=m.r(s);m.invoke(m.c['move'],obj,(260,300));m.preview(args.output/'sixth-tooltip.png')
    assert [t[0] for t in m.texts[-2:]]==['Reward 506','Quantity: 5']
    m.invoke(m.c['rightdown'],obj,(260,300));m.invoke(m.c['rightup'],obj,(260,300));assert m.described[-1]==506
    # Six independent cosmetic cards, delayed reply, then skip/motion-off.
    begin();icons=lambda:tuple(m.r(a+m.anim_icons+i*4) for i in range(6))
    for _ in range(10):m.advance(100);assert len(set(icons()))==6
    m.reply(six=True,total=20,roll=6);m.click(160,370);m.preview(args.output/'six-skip.png');assert sum(t[0]=='Received' for t in m.texts)==6
    begin();m.click(60,370);m.reply(six=True,total=20,roll=6);m.preview(args.output/'six-motion-off.png');assert sum(t[0]=='Received' for t in m.texts)==6
    # Malformed counts, absent sixth item and version/length mismatches fail closed.
    for mutate in [lambda p:struct.pack_into('<I',p,44,7),lambda p:struct.pack_into('<I',p,9364,0),lambda p:struct.pack_into('<H',p,8,3),lambda p:struct.pack_into('<H',p,2,9419)]:
        m.click(815,43);p=snapshot(seq=m.r(s+4),six=True,total=20,roll=6);mutate(p);m.receive(p);assert m.r(s+8);m.reply(six=True,total=20,roll=6)
    m.click(815,43);m.reply(catalog=True,total=20,roll=5);m.preview(args.output/'v3-compatibility.png');assert sum(t[0]=='Received' for t in m.texts)==5
    m.click(190,44);m.click(815,43);p=snapshot(seq=m.r(s+4),six=True,total=20)
    for i in range(5):
        off=592+i*420;struct.pack_into('<5I',p,off,5,0,1+i%3,0,0)
        for j in range(i+1,6):p[off+84+j*56:off+84+(j+1)*56]=bytes(56)
    m.receive(p);m.preview(args.output/'quests-variable-rewards.png');assert len(m.icons)==15
    m.click(906,11);print('PASS: emitted v4 x86, 1..6 reveals, sixth item tooltip/inspection, six cosmetic streams, skip/motion, malformed packets, old-server compatibility and variable quest rewards')

if __name__=='__main__':main()
