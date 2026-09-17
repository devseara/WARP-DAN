"""Execute native VIP quest confirmation/window and exact item-icon helper."""
import argparse
import io
import re
import struct
from pathlib import Path
from PIL import Image
from test_vip_ui import VipMachine,snapshot

def quest(token=101,ready=False,opened=True):
    p=snapshot(flags=1|4|8|32|(128 if ready else 0)|(2 if opened else 0),token=token)
    struct.pack_into('<II',p,2272,3000000,2)
    note=b'Requirements complete. Submit to upgrade.' if ready else b'Collect the listed items and required Zeny.'
    p[2280:2344]=note.ljust(64,b'\0')
    for i,(item,amount,name) in enumerate([(909,150,'Jellopy'),(914,100,'Fluff'),(606,300,'Aloe Vera')]):
        struct.pack_into('<III48s',p,2344+i*60,item,amount,amount if ready else i*10,name.encode())
    return p

def artwork(m,game):
    from dual_weapon_formats.grf_reader import GrfFile
    data=(game/'System/itemInfo.lua').read_bytes()
    archives=[GrfFile(game/name) for name in ('pdata.grf','mdata.grf','maindata.grf','data.grf') if (game/name).is_file()]
    nodes={};images={};prefix=bytes.fromhex('c0afc0fac0cec5cdc6e4c0ccbdba')
    try:
        for item in (909,914,606):
            block=re.search(rb'\n\t\['+str(item).encode()+rb'\] = \{(.*?)(?=\n\t\[\d+\] = |\Z)',data,re.S)
            assert block,item
            key=re.search(rb'identifiedResourceName = "([^"]+)"',block[1])[1]
            path=(b'data/texture/'+prefix+b'/item/'+key+b'.bmp').decode('cp949').lower()
            raw=next((raw for archive in archives if (raw:=archive.read(path)) is not None),None)
            assert raw,(item,path)
            images[key.decode('latin1')+'.bmp']=Image.open(io.BytesIO(raw)).convert('RGBA')
            node=m.alloc(0xB0);nodes[item]=node
            if len(key)<16:m.u.mem_write(node+0x58,key+b'\0');capacity=15
            else:
                ptr=m.alloc(len(key)+1);m.u.mem_write(ptr,key+b'\0');m.w(node+0x58,ptr);capacity=len(key)
            m.w(node+0x68,len(key));m.w(node+0x6C,capacity)
    finally:
        for archive in archives:archive.close()
    lookups=[];m.w(0x159C088,m.alloc(32))
    def lookup():
        item=m.r(m.args(1)[0]);lookups.append(item);m.ret(4,nodes.get(item,0))
    m.stub(0xA7E780,lookup)
    def format_path():
        dest,fmt,key=m.args(3);value=m.cstr(fmt).replace('%s',m.cstr(key)).encode('latin1')
        m.u.mem_write(dest,value+b'\0');m.ret(0,len(value))
    m.stub(0x529850,format_path)
    def texture():
        key=m.cstr(m.args(1)[0]).split('\\')[-1]
        if key.endswith('.png'):m.ret(4,m.load_texture(key));return
        if key not in images:m.ret(4,0);return
        if key not in m.textures:
            image=images[key];w,h=image.size;descriptor=m.alloc(0x130);pixels=m.alloc(w*h*4)
            m.u.mem_write(pixels,image.tobytes('raw','BGRA'))
            for off,value in [(0x110,1),(0x114,w),(0x118,h),(0x11C,pixels)]:m.w(descriptor+off,value)
            m.textures[key]=descriptor
        m.ret(4,m.textures[key])
    m.stub(0xA8D4A0,texture)
    return lookups

def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True);ap.add_argument('--game',type=Path)
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    m=VipMachine(args.exe);c=m.c;qs=c['quest_state']
    looks=artwork(m,args.game) if args.game else None
    if looks is None:m.w(0x159C088,0) # Explicitly missing client item DB; safe no-image path.
    obj=m.ready(snapshot(flags=1|2|4));before=len(m.sent)
    m.click(obj,260,303);assert not m.r(qs+16) and len(m.sent)==before,'incomplete EXP opened Upgrade'
    obj=m.ready(snapshot());m.click(obj,260,303);q=m.r(qs)
    assert q and m.r(qs+16)==1 and len(m.sent)==before
    assert (m.r(q+0x14),m.r(q+0x18))==(360,118)
    m.preview(q,args.output/'vip-upgrade-confirm.png')
    assert any('Do you want to upgrade your VIP?' in row[0] for row in m.texts)
    m.click(q,193,86);assert not m.r(qs+16) and len(m.sent)==before,'No changed server state'
    m.click(obj,260,303);m.click(q,134,86)
    assert struct.unpack_from('<H',m.sent[-1],10)[0]==4 and not m.r(q+0x28)
    count=len(m.sent);m.click(q,134,86);assert len(m.sent)==count,'duplicate Yes'
    obj=m.ready(quest());q=m.r(qs);assert m.r(qs+16)==2
    assert (m.r(q+0x14),m.r(q+0x18))==(360,270)
    m.preview(q,args.output/'vip-upgrade-quest.png')
    for name in ('Jellopy','Fluff','Aloe Vera','3,000,000'):assert any(name in row[0] for row in m.texts),name
    if looks is not None:assert looks[-3:]==[909,914,606],'wrong/missing required item images'
    m.click(q,132,248);assert len(m.sent)==count,'incomplete quest submitted'
    m.click(q,205,248);assert not m.r(q+0x28) and len(m.sent)==count
    m.click(obj,260,303);assert m.r(qs+16)==2 and len(m.sent)==count,'saved quest rerolled or reconfirmed'
    m.receive(quest(ready=True,opened=False));assert m.r(qs+16)==2
    m.preview(q,args.output/'vip-upgrade-ready.png')
    m.invoke(c['down'],q,(50,8));assert m.r(qs+12)==1
    m.invoke(c['drag'],q,(60,8));m.invoke(c['up'],q,(60,8));assert not m.r(qs+12)
    m.click(q,132,248);assert struct.unpack_from('<H',m.sent[-1],10)[0]==7
    count=len(m.sent);m.click(q,132,248);assert len(m.sent)==count and not m.r(obj+0x28)
    obj=m.ready(quest(token=115));q=m.r(qs)
    m.invoke(c['destroy'],q,(1,));assert not m.r(qs) and m.r(obj+0x28) and m.r(c['state'])==obj
    m.click(obj,260,303);assert m.r(qs) and m.r(qs)!=q
    m.invoke(c['destroy'],obj,(1,));assert not m.r(m.r(qs)+0x28) and not m.r(qs+16)
    print('PASS: EXP-gated Upgrade, native Yes/No, no action on No, saved quest popup/reopen/no reroll, exact 3 item IDs/images, Zeny/counts, incomplete/ready submission, replay guard, independent drag/capture/close/destroy; no live mutation.')

if __name__=='__main__':main()
