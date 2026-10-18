"""Execute the actual native circle input, animation, alpha and cursor paths."""
import argparse,hashlib,json,struct
from pathlib import Path
from PIL import Image,ImageFont
from test_celestial_dial import Machine,ROOT

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('client',type=Path);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    meta=json.loads((ROOT/'Inputs/CelestialDial/runtime.json').read_text());m=Machine(a.client)
    runtime=m.c['api']-meta['exports']['CelestialApi'];e=lambda n:runtime+meta['exports'][n]
    h=e('CelestialHudState');api=e('CelestialHudApi');m.frame();m.receive(m.snapshot(phase=1));m.frame();w=m.r(m.c['state'])
    px=m.r(w+0x1C);py=m.r(w+0x20)
    down=e('@CelestialDown@16');up=e('@CelestialUp@16');move=e('@CelestialMove@16');cursor=e('@CelestialCursorDraw@8')
    def click(x=140,y=35):m.invoke(down,(x,y),ecx=w);m.invoke(up,(x,y),ecx=w)
    assert m.invoke(m.c['hit'],(px+140,py+35),ecx=w)==w
    for x,y in [(0,0),(2,20),(50,45),(140,84),(106,1),(174,69),(279,97)]:
        assert m.invoke(m.c['hit'],(px+x,py+y),ecx=w)==0,(x,y)
    m.draw(a.output/'expanded.png')
    values={t[0]:t for t in m.texts}
    assert values['WORLD'][2]==values['SERVER TIME'][2] and values['Night'][2]==values['21:34:08'][2]
    for value in ['WORLD','Night','SERVER TIME','21:34:08','UTC+08:00']:
        _,x,_,size,_=values[value];used=round(ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',size).getlength(value))
        center=53.5 if value in ['WORLD','Night'] else 226.5
        assert abs(x+used/2-center)<=.5,(value,x,used,center)
    click();assert m.r(h)==1 and m.r(h+28)==1
    progress=[]
    for delta in [0,75,75,75,75,150]:
        m.now+=delta;m.frame();progress.append(m.r(h+8));m.draw(a.output/f'collapse-{sum(progress)%10000}-{m.r(h+8)}.png')
    assert progress==sorted(progress,reverse=True) and progress[-1]==0 and m.r(m.c['top'])==86
    m.draw(a.output/'collapsed.png');surface=m.r(w+0x24);pixels=m.r(surface+0x18)
    image=Image.frombytes('RGBA',(280,98),bytes(m.u.mem_read(pixels,280*98*4)),'raw','BGRA')
    assert all(image.getpixel((x,y))[3]==0 for y in range(98) for x in range(280) if (x-140)**2+(y-35)**2>35**2)
    edge=[image.getpixel((x,y))[3] for y in range(0,71) for x in range(105,176) if 33**2<(x-140)**2+(y-35)**2<35**2]
    assert any(0<v<255 for v in edge),'No antialiased edge'
    for y in range(-35,36):
        for x in range(-35,36):assert image.getpixel((140+x,35+y))[3]==image.getpixel((140-x,35-y))[3]
    # Open, reverse midway, then open fully: no snap or queued animation.
    click();m.now+=100;m.frame();partial=m.r(h+8);assert 0<partial<1000
    click();assert m.r(h+8)==partial;m.now+=450;m.frame();assert m.r(h+8)==0
    click();m.now+=450;m.frame();assert m.r(h+8)==1000 and m.r(m.c['top'])==114
    # Release outside cancels. Losing capture, map reset and hidden windows cancel.
    m.invoke(down,(140,35),ecx=w);m.invoke(move,(0,95),ecx=w);m.invoke(up,(0,95),ecx=w);assert m.r(h)==0 and not m.r(h+4)
    m.invoke(down,(140,35),ecx=w);m.w(0x131F4E8+0x19C,0);m.frame();m.invoke(up,(140,35),ecx=w);assert m.r(h)==0
    # Real bitmap decoding is represented by exact native loader pixels/dimensions.
    textures={};surfaces=[];paths=[];paint=[];fallback=[];hit=[w]
    for name in ['Cursor_Hover.bmp','Cursor_Mouse_Press.bmp']:
        im=Image.open(ROOT/'Assets/BattlepassUI/client'/name).convert('RGB');tex=m.alloc(0x130);buf=m.alloc(im.width*im.height*4)
        raw=b''.join(struct.pack('<I',(r<<16)|(g<<8)|b) for r,g,b in im.getdata())
        m.u.mem_write(buf,raw);m.w(tex+0x114,im.width);m.w(tex+0x118,im.height);m.w(tex+0x11C,buf);textures[name]=(tex,im)
    m.stub(0xA90350,lambda:m.ret(0,0x12345));m.stub(0xA9F030,lambda:m.ret(0,m.args(1)[0]))
    def load():
        ptr=m.args(1)[0];name=bytes(m.u.mem_read(ptr,160)).split(b'\0')[0].split(b'\\')[-1].decode();paths.append(name);m.ret(4,textures[name][0])
    m.stub(0xA8D4A0,load)
    def alloc_surface():
        sw,sh,zero=m.args(3);assert zero==0;s=m.alloc(64);buf=m.alloc(sw*sh*4);table=m.alloc(4);destroy=m.alloc(16)
        m.w(table,destroy);m.w(s,table);m.w(s+4,sw);m.w(s+8,sh);m.w(s+0x18,buf);surfaces.append(s)
        m.stub(destroy,lambda:(surfaces.remove(m.ecx()),m.ret(4)));m.ret(0,s)
    m.stub(0x560E50,alloc_surface);m.stub(0xA336D0,lambda:m.ret(8,hit[0]))
    m.stub(0x53EA90,lambda:(paint.append((m.ecx(),m.args(5))),m.ret(20)))
    m.stub(m.r(api),lambda:(fallback.append(m.ecx()),m.ret(0)))
    m.w(0x11E40D4,px+140);m.w(0x11E40D8,py+35)
    m.invoke(cursor,ecx=0x12345678);assert paths==['Cursor_Hover.bmp'] and paint[-1][1][2:4]==[26,22] and not fallback
    m.invoke(down,(140,35),ecx=w);m.invoke(cursor,ecx=0x12345678);assert paths[-1]=='Cursor_Mouse_Press.bmp' and paint[-1][1][2:4]==[26,21]
    for name,(tex,im) in textures.items():
        s=m.r(h+32+(0 if name=='Cursor_Hover.bmp' else 4));raw=bytes(m.u.mem_read(m.r(s+0x18),im.width*im.height*4))
        for i,(r,g,b) in enumerate(im.getdata()):assert struct.unpack_from('<I',raw,i*4)[0]==(0 if (r,g,b)==(255,0,255) else 0xff000000|(r<<16)|(g<<8)|b)
        Image.frombytes('RGBA',im.size,raw,'raw','BGRA').save(a.output/(name+'.png'))
    m.invoke(up,(0,95),ecx=w)
    for obscured,captured,mx in [(True,0,140),(False,0x9999,140),(False,0,5)]:
        hit[0]=0x9999 if obscured else w;m.w(0x131F4E8+0x19C,captured);m.w(0x11E40D4,px+mx);n=len(paint)
        m.invoke(cursor,ecx=0x12345678);assert len(paint)==n and fallback[-1]==0x12345678
    m.w(0x131F4E8+0x19C,0);m.invoke(down,(140,35),ecx=w);m.invoke(m.c['reset']);assert not m.r(h+4) and not m.r(0x131F4E8+0x19C)
    assert m.invoke(m.c['hit'],(px+140,py+35),ecx=w)==0
    m.invoke(m.c['destroy'],(1,),ecx=w);assert not surfaces
    report={'passed':True,'client_sha256':hashlib.sha256(a.client.read_bytes()).hexdigest(),'payload_sha256':meta['payload_sha256'],
        'checks':['circle hit and click-through','centered text baselines','450ms animation and reversal','symmetric antialiased rim','announcement/monster spacing','capture cancellation and reset','exact hover/press artwork and colorkey','occlusion and unrelated cursor fallback','cursor surface cleanup'],
        'live_visual_accepted':False}
    (a.output/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
