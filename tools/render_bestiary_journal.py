"""Render the emitted journal x86 using a marked packet fixture (not live).

Graphics and portrait boundaries are substituted. The actual UI draw code
owns text clipping, coordinates, tabs, resource formatting and composition.
"""
from pathlib import Path
import argparse,base64,configparser,io,json,re,struct
from PIL import Image,ImageDraw,ImageFont
import pefile
from verify_bestiary_journal import JournalVM,packet
from dual_weapon_formats.grf_reader import GrfFile
from dual_weapon_formats.spr_reader import Spr
from dual_weapon_formats.act_reader import parse_act
from bestiary_sprite_geometry import frame_bounds

ROOT=Path(__file__).resolve().parents[1]


def render(directory,game,tab=0,detail=0,popup=False,info_page=0,randgris=False,info_section=0,filters=False,personal_view=0):
    m=json.loads((directory/'native-manifest.json').read_text())['bestiary']
    v=JournalVM(pefile.PE(str(directory/'bestiary-preview.exe'),fast_load=True),m)
    v.ready();v.state32(4,tab);v.state32(140,detail);v.state32(124,int(popup))
    v.state32(148,v.now);v.state32(160,info_page)
    if m.get('protocolVersion',2)>=3:
        v.state32(204,info_section);v.state32(208,int(filters))
        v.u.mem_write(m['payload']['vir']+3414,struct.pack('<H',3))
        for i,line in enumerate(['A small pink wanderer whose cheerful bounce is a familiar sight to new adventurers.',
                                 'Its soft appearance is a poor reason to leave belongings unattended.',
                                 'These preview packets demonstrate the journal layout.']):
            v.u.mem_write(m['payload']['vir']+4288+i*112,line.encode()+b'\0')
        v.u.mem_write(m['payload']['vir']+4736,b'Bestiary editorial field journal\0')
        v.u.mem_write(m['payload']['vir']+3420,struct.pack('<H',1))
        v.u.mem_write(m['payload']['vir']+4808,b'Poring\0')
        v.u.mem_write(m['payload']['vir']+4856,b'Example follower summon\0')
    if m.get('layoutVersion',0)>=9 and tab:
        from verify_bestiary_research_native import personal
        ps=m['personalState']['vir'];v.write32(ps,1);v.write32(ps+4,personal_view);v.write32(ps+24,1002)
        data=bytearray(personal(1,tab=tab,view=personal_view))
        def put(off,size,value):data[off:off+size]=value.encode()[:size-1].ljust(size,b'\0')
        put(64,64,'Poring' if tab==1 and personal_view==0 else 'Monster Research' if tab==1 else 'Research Rewards')
        put(384,128,'Journal points: 73 | Next milestone: 100')
        if tab==1 and personal_view==0:
            struct.pack_into('<H',data,36,5)
            for i,(name,goal,points) in enumerate([('Discovered',1,1),('Observed',25,2),('Studied',100,3),('Documented',500,5),('Mastered',1500,10)]):
                row=512+i*256;struct.pack_into('<4I',data,row,i+1,0,int(i<2),min(1000,25000//goal))
                put(row+16,64,f'Tier {i+1} - {name}');put(row+80,96,f'25 / {goal:,} lifetime kills');put(row+176,48,'Completed' if i<2 else f'{goal-25:,} remaining');put(row+224,32,f'{points} journal points')
        elif tab==1 and personal_view==1:
            put(128,128,'Group progress follows the lowest required member tier.')
            struct.pack_into('<H',data,36,3)
            for i,(name,mob) in enumerate([('Poring Family','Poporing'),('Meadow Neighbors','Pupa'),('Cave Dwellers','Familiar')]):
                row=512+i*256;put(row+16,64,name);put(row+80,96,'Limiting member: '+mob);put(row+176,48,'Tier 1 / 5');put(row+224,32,'10 points per tier')
        elif tab==1:
            put(128,128,'Your favorite hunting targets. Select a row to research it.')
            struct.pack_into('<H',data,36,3)
            for i,name in enumerate(['Poring','Lunatic','Fabre']):
                row=512+i*256;put(row+16,64,name);put(row+80,96,'25 eligible kills');put(row+176,48,'Tier 2 / 5');put(row+224,32,'Tracked' if i==0 else 'Favorite')
        elif personal_view==3:
            put(128,128,'Cabinet: trophies and cosmetic titles earned by this account.')
            struct.pack_into('<H',data,36,3)
            for i,(name,description) in enumerate([('Beginner','Cosmetic title awarded at 100 journal points.'),('Poring Mastery','Master all five Poring research tiers.'),('Poring Family','Complete the first tier for every group member.')]):
                row=512+i*256;struct.pack_into('<I',data,row+8,8 if i==0 else 4);put(row+16,64,name);put(row+80,96,description);put(row+176,48,'Click to equip title' if i==0 else 'Account collectible');put(row+224,32,'')
        else:
            put(128,128,'Account-wide progress | Cosmetics, titles and field supplies')
            for i,name in enumerate(['First Field Kit','Apprentice Supplies','Beginner Title','Travel Supplies','Specialist Title','Poring Family Trophy']):
                row=512+i*256;flag=1 if personal_view==2 else 2 if personal_view==1 or i<2 else 0
                struct.pack_into('<I',data,row+8,flag);put(row+16,64,name);put(row+80,96,'A permanent journal milestone for this account.');put(row+176,48,'Claimed' if flag==1 else 'Available - click to claim' if flag==2 else 'Requires 100 journal points');put(row+224,32,'Field supplies' if i<2 else 'Cosmetic reward')
        v.receive(bytes(data))
    canvas=Image.new('RGB',(760,500),'white');fontcache={};resources={};bounds=[]
    data=json.loads((ROOT/'tools/fixtures/bestiary/native-sprites.json').read_text())
    sprites={name:Image.open(io.BytesIO(base64.b64decode(data[name].split(',')[1]))).convert('RGBA') for name in ['poring','lunatic','fabre','pupa','drops','poporing']}
    roster=[(1002,'Poring'),(1063,'Lunatic'),(1007,'Fabre'),(1008,'Pupa'),(1113,'Drops'),(1031,'Poporing')]
    for i,(id,name) in enumerate(roster):
        off=m['payload']['vir']+64+i*128
        v.u.mem_write(off,struct.pack('<II',id,id));v.u.mem_write(off+20,name.encode()+b'\0')
    for i,(level,element,element_level,label) in enumerate([(1,1,1,'Water 1'),(3,0,3,'Neutral 3'),(2,2,1,'Earth 1'),(2,2,1,'Earth 1'),(3,3,1,'Fire 1'),(14,5,1,'Poison 1')]):
        off=m['payload']['vir']+64+i*128
        v.u.mem_write(off+8,struct.pack('<HHH',level,element,element_level))
        v.u.mem_write(off+84,('Lv. '+str(level)).encode()+b'\0')
        v.u.mem_write(off+104,label.encode()+b'\0')
    d=m['payload']['vir']+832
    v.u.mem_write(d+50,struct.pack('<HHHH',3,1,1,1))
    if randgris:
        roster[0]=(1751,'Valkyrie Randgris')
        v.state32(28,1751)
        v.u.mem_write(m['payload']['vir']+64,struct.pack('<II',1751,1751))
        v.u.mem_write(m['payload']['vir']+84,b'Valkyrie Randgris\0')
        v.u.mem_write(m['payload']['vir']+148,b'Lv. 99\0')
        v.u.mem_write(m['payload']['vir']+168,b'Holy 4\0')
        v.u.mem_write(m['payload']['vir']+74,struct.pack('<H',6))
        v.u.mem_write(d,struct.pack('<II',1751,1751))
        v.u.mem_write(d+50,struct.pack('<HHHH',8,6,4,2))
        for off,value in [(64,'Valkyrie Randgris'),(128,'No. 1751 / Lv. 99'),(176,'3567200'),(200,'71372500'),(224,'77863000'),(248,'Holy 4'),(272,'Angel'),(296,'Large'),(320,'Aggressive / Detector')]:
            v.u.mem_write(d+off,value.encode()+b'\0')
        # These values reproduce the user's supplied case; the packet remains
        # a fixture, not a captured live response from the new server build.
        values=[100,120,30,120,220,210,3567200,1,5560,9980,409,696,25,42,319,219,0,0,30,135,3,10,12,100,576,576,480,0]+[0]*12
        for i,value in enumerate(values):v.u.mem_write(m['payload']['vir']+2432+i*24,str(value).encode()+b'\0')
    names={id:('randgris' if id==1751 else name.lower()) for id,name in roster}
    v.stub(0xD5BB40,8,lambda ecx,a:v.string(names[a[0]]))
    iteminfo=(game/'System/LuaFiles514/itemInfo.lua').read_bytes()
    stems={}
    for id in [909,713,1201,4001]:
        block=iteminfo.split(('['+str(id)+'] = {').encode(),1)[1].split(b'\n\t[',1)[0]
        stems[id]=re.search(rb'\n\s*identifiedResourceName\s*=\s*"([^"]*)"',block)[1]
    v.stub(m['itemResolver']['vir'],4,lambda ecx,a:v.string(stems[a[0]]))
    config=configparser.ConfigParser();config.read(game/'DATA.INI',encoding='utf-8-sig')
    grfs=[GrfFile(game/file) for _,file in sorted(config['Data'].items(),key=lambda pair:int(pair[0])) if (game/file).exists()]
    def native_image(name):
        own=directory/'data/texture'/name
        if own.exists():
            im=Image.open(own).convert('RGBA')
            if any(name.startswith('bestiary/journal/'+kind+'_') for kind in ['element','race','size']):
                im.putdata([(r,g,b,0 if (r,g,b)==(255,0,255) else a) for r,g,b,a in im.getdata()])
            return im
        key='data/texture/'+name
        raw=None
        for grf in grfs:
            raw=grf.read(key.lower())
            if raw:break
        if not raw:return None
        im=Image.open(io.BytesIO(raw)).convert('RGBA')
        if '/item/' in name or name.startswith('bestiary/journal/element_') or name.startswith('bestiary/journal/race_') or name.startswith('bestiary/journal/size_'):
            im.putdata([(r,g,b,0 if (r,g,b)==(255,0,255) else a) for r,g,b,a in im.getdata()])
        return im
    def font(size,bold):
        key=(size,bold)
        if key not in fontcache:fontcache[key]=ImageFont.truetype('C:/Windows/Fonts/'+('tahomabd.ttf' if bold else 'tahoma.ttf'),size)
        return fontcache[key]
    def label(ptr,count):
        raw=v.cstring(ptr)
        return (raw[:count] if count else raw).decode('cp1252',errors='replace')
    def measure(ecx,a):return round(font(a[3],a[4]).getlength(label(a[0],a[1])))
    def text(ecx,a):
        x,y,ptr,count,_,size,color,bold,_=a;value=label(ptr,count);f=font(size,bold);width=f.getlength(value)
        assert x>=0 and y>=0 and x+width<=760 and y+size<=500,(value,x,y,width)
        bounds.append([value,x,y,width]);ImageDraw.Draw(canvas).text((x,y),value,font=f,fill=(color&255,(color>>8)&255,(color>>16)&255),anchor='lt')
    def fill(ecx,a):
        _,x,y,w,h,color=a
        assert 0<=x<=x+w<=760 and 0<=y<=y+h<=500,a
        ImageDraw.Draw(canvas).rectangle((x,y,x+w-1,y+h-1),fill=((color>>16)&255,(color>>8)&255,color&255))
    def load(ecx,a):
        name=v.cstring(a[0]).decode('cp949',errors='replace').replace('\\','/')
        r=v.alloc(32);resources[r]=name;return r
    def bitmap(ecx,a):
        x,y,r,_=a;name=resources[r];im=native_image(name)
        if im is None:raise AssertionError('Missing layout resource: '+name)
        assert x+im.width<=760 and y+im.height<=500,(name,x,y,im.size)
        canvas.paste(im,(x,y),im)
    def sprite(ecx,a):
        window,spr,act,x,y,w,h,cycle=a;name=resources[spr].split('/')[-1].split('.')[0]
        if name=='randgris':
            def read_sprite(suffix):
                key='data/sprite/몬스터/randgris'+suffix
                loose=game/key
                if loose.is_file():return loose.read_bytes()
                for grf in grfs:
                    raw=grf.read(key)
                    if raw:return raw
                raise FileNotFoundError(key)
            ss=Spr(read_sprite('.spr'));aa=parse_act(read_sprite('.act'))
            f=aa['actions'][0].frames[0];bbox=frame_bounds(ss,f)
            im=Image.new('RGBA',(round(bbox[2]-bbox[0]),round(bbox[3]-bbox[1])))
            for layer in f.layers:
                if layer.sprite_index<0:continue
                rgba,ww,hh=ss.get_rgba(layer.sprite_index,layer.sprite_type)
                piece=Image.frombytes('RGBA',(ww,hh),rgba)
                if layer.mirror:piece=piece.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                im.alpha_composite(piece,(round(layer.x-ww/2-bbox[0]),round(layer.y-hh/2-bbox[1])))
        else:im=sprites[name]
        scale=min(1,w/im.width,h/im.height);im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.NEAREST)
        canvas.paste(im,(x+(w-im.width)//2,y+(h-im.height)//2),im)
    v.stub(0xA21C90,24,measure);v.stub(0xA25A70,36,text);v.stub(m['fill']['vir'],24,fill)
    v.stub(0xA1CB30,4,lambda ecx,a:None);v.stub(0xA8D4A0,4,load);v.stub(0xA1D260,16,bitmap);v.stub(m['colorKeyBlit']['vir'],16,lambda ecx,a:bitmap(ecx,[a[2],a[3],a[1],0]));v.stub(m["preview"]["vir"],32,sprite)
    v.run('draw')
    for grf in grfs:grf.close()
    dest=directory/(f'journal-qa-tab{tab}-detail{detail}-popup{int(popup)}'+(f'-stats{info_page}' if info_page else '')+('-randgris' if randgris else '')+(f'-section{info_section}' if info_section else '')+('-filters' if filters else '')+(f'-view{personal_view}' if tab else '')+'.png');canvas.save(dest)
    dest.with_suffix('.json').write_text(json.dumps({'source':'emitted x86 with synthetic BSUI fixture, not a live screenshot','bounds':bounds},indent=2))
    return dest


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('build_directory',type=Path);ap.add_argument('--game',type=Path,required=True);args=ap.parse_args()
    for tab,detail,popup in [(0,0,False),(0,1,False),(0,2,False),(0,0,True),(1,0,False),(2,0,False)]:
        print(render(args.build_directory,args.game,tab,detail,popup))
    for page in range(1,4):print(render(args.build_directory,args.game,0,1,False,page))
    print(render(args.build_directory,args.game,0,1,False,0,True))

    if json.loads((args.build_directory/'native-manifest.json').read_text())['bestiary'].get('protocolVersion',2)>=3:
        for section in [1,2]:print(render(args.build_directory,args.game,0,1,False,info_section=section))
        print(render(args.build_directory,args.game,filters=True))

    if json.loads((args.build_directory/'native-manifest.json').read_text())['bestiary'].get('layoutVersion',0)>=9:
        for tab,view in [(1,1),(1,2),(2,1),(2,2),(2,3)]:print(render(args.build_directory,args.game,tab=tab,personal_view=view))
