"""Execute emitted sunlight projection, isolated mesh queues and player silhouette scope."""
import argparse
import json
from pathlib import Path
import struct

from test_celestial_dial import Machine, ROOT


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('client',type=Path)
    parser.add_argument('--runtime-meta',type=Path,default=ROOT/'Inputs/CelestialDial/runtime.json')
    args=parser.parse_args();m=Machine(args.client);state=m.c['state']
    meta=json.loads(args.runtime_meta.read_text())
    base=m.c['api']-meta['exports']['CelestialApi']
    export=lambda name:base+meta['exports'][name]
    shadow=export('CelestialShadowState')
    m.frame();m.receive(m.snapshot(map_name=b'prt_fild08\0',flags=3,duration=3600000,remaining=3600000));m.frame()
    m.u.mem_write(m.player+0x10,struct.pack('<3f',0.,-97.,1.))
    ground=m.alloc(0x40);resource=m.alloc(0x140);cells=m.alloc(160*160*20)
    m.w(m.world+0x28,ground);m.w(ground+4,resource);m.w(ground+8,80);m.w(ground+12,80)
    m.u.mem_write(ground+16,struct.pack('<f',10))
    m.w(resource+0x110,160);m.w(resource+0x114,160);m.w(resource+0x11c,cells)
    # Non-walkable terrain remains a valid shadow receiver, with no collision edits.
    terrain=struct.pack('<4fI',-97.,-97.,-97.,-97.,1)*(160*160)
    m.u.mem_write(cells,terrain)
    view=m.alloc(48);matrix=(1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.)
    m.u.mem_write(view,struct.pack('<12f',*matrix))
    actor=m.alloc(0x200);m.w(actor,0x104D450);m.u.mem_write(actor+0x154,b'\1')
    original_calls=[]
    def stock_actor():
        original_calls.append((m.ecx(),m.args(2),m.r(shadow),bytes(m.u.mem_read(actor+0x154,1))))
        m.ret(8)
    m.stub(0xA59D20,stock_actor)
    before=bytes(m.u.mem_read(actor,0x200))
    m.invoke(m.r(0x104D450+7*4),(view,0),ecx=actor)
    assert len(original_calls)==2 and original_calls[0][2:]==(0,b'\1') and original_calls[1][2:]==(1,b'\0')
    assert bytes(m.u.mem_read(actor,0x200))==before and not m.r(shadow)
    # Run the exact patched model projection call with a real elevated mesh vertex.
    projected=[]
    def native_project():
        vertex,transform,output=m.args(3)
        projected.append((struct.unpack('<3f',bytes(m.u.mem_read(vertex,12))),transform))
        m.u.mem_write(output,struct.pack('<4f',1.,2.,.5,1.))
        m.ret(12)
    m.stub(0x554380,native_project)
    vertex=m.alloc(12);output=m.alloc(32)
    m.u.mem_write(vertex,struct.pack('<3f',10.,-130.,20.));m.w(shadow,1)
    target=0xA59EF6+struct.unpack('<i',bytes(m.u.mem_read(0xA59EF2,4)))[0]
    m.invoke(target,(vertex,view,output),ecx=m.renderer)
    dx,dz=struct.unpack('<2f',bytes(m.u.mem_read(shadow+104,8)))
    result=projected[-1][0]
    assert abs(result[0]-(10+33*dx))<1e-3 and abs(result[1]+97.12)<1e-3 and abs(result[2]-(20+33*dz))<1e-3,result
    assert bytes(m.u.mem_read(cells,len(terrain)))==terrain
    # The real phase countdown moves the projection direction across the day.
    m.w(shadow,0);m.now+=1000
    m.receive(m.snapshot(map_name=b'prt_fild08\0',flags=3,duration=3600000,remaining=1800000,push=True));m.frame()
    m.invoke(m.r(0x104D450+7*4),(view,0),ecx=actor)
    middle=struct.unpack('<2f',bytes(m.u.mem_read(shadow+104,8)))
    assert abs(dx-middle[0])>.1 or abs(dz-middle[1])>.1,'Sun direction did not follow phase progress'
    m.w(shadow,1)
    # Fresh mesh vertices keep their UVs/texture and enter native alpha sorting.
    objects=[]
    def submit():
        obj,flags=m.args(2);ptr=m.r(obj)
        objects.append((obj,flags,bytes(m.u.mem_read(ptr,m.r(obj+4)*32))))
        m.ret(8)
    m.stub(0x550B10,submit)
    obj=m.alloc(40);vertices=m.alloc(128);m.w(obj,vertices);m.w(obj+4,4);m.w(obj+8,0x12345678)
    quad=b''.join(struct.pack('<4fII2f',float(i),-100.,.5,1.,0xffffffff,0,0.25,0.75) for i in range(4))
    m.u.mem_write(vertices,quad)
    m.invoke(export('@CelestialShadowSubmit@16'),(obj,0),ecx=m.renderer)
    assert objects[-1][1]==1 and m.r(obj+8)==0x12345678
    for i in range(4):
        assert m.r(vertices+i*32+16)==0x28000000
        assert bytes(m.u.mem_read(vertices+i*32+24,8))==quad[i*32+24:i*32+32]
    m.w(shadow,0)
    # Player draw forwards once and opens a scope only for that exact actor.
    player_calls=[]
    m.stub(0xD3A220,lambda:(player_calls.append(m.r(shadow+112)),m.ret(4)))
    m.invoke(m.r(0x1094810+3*4),(view,),ecx=m.player)
    assert player_calls==[m.player] and not m.r(shadow+112)
    m.w(shadow+112,m.player)
    for offset,value in [(4,1.),(8,1.)]:m.u.mem_write(m.renderer+offset,struct.pack('<f',value))
    m.w(m.renderer+0x30,0);m.w(m.renderer+0x34,0)
    m.u.mem_write(vertices,quad);objects.clear()
    m.invoke(export('@CelestialSpriteShadowSubmit@28'),(obj,6,m.player,0xC42000,0),ecx=m.renderer)
    assert len(objects)==2 and objects[0][0]==obj and objects[1][0]!=obj and objects[1][1]==1
    assert bytes(m.u.mem_read(vertices,128))==quad,'Changed the original character draw'
    assert m.r(objects[1][0]+8)==0x12345678
    objects.clear()
    m.invoke(export('@CelestialSpriteShadowSubmit@28'),(obj,6,m.player+16,0xC42000,0),ecx=m.renderer)
    assert len(objects)==1,'Captured another actor or unrelated effect'
    objects.clear()
    m.invoke(export('@CelestialSpriteShadowSubmit@28'),(obj,6,m.player,0xC49E00,0),ecx=m.renderer)
    assert len(objects)==1,'Projected the stock ground ellipse again'
    objects.clear()
    m.invoke(export('@CelestialSpriteShadowSubmit@28'),(obj,6,m.player,0xC4A6C5,0xD36CC9),ecx=m.renderer)
    assert len(objects)==2,'Discarded an ordinary mirrored character layer'
    objects.clear()
    m.invoke(export('@CelestialSpriteShadowSubmit@28'),(obj,6,m.player,0xC4A6C5,0xC4A098),ecx=m.renderer)
    assert len(objects)==1,'Captured the mirrored native contact ellipse'
    # Exercise the actual naked bridge against the original caller's EBP locals.
    fake_frame=m.alloc(0x80)+0x30;m.w(fake_frame-0x28,m.player);m.w(fake_frame+4,0xC42000)
    bridge=export('CelestialSpriteSubmitBridge');entry=m.alloc(64)
    code=bytearray(b'\x55\xbd'+struct.pack('<I',fake_frame)+b'\x6a\x06\x68'+struct.pack('<I',obj))
    code+=b'\xb9'+struct.pack('<I',m.renderer)+b'\xe8'
    code+=struct.pack('<i',bridge-(entry+len(code)+4))+b'\x5d\xc3'
    m.u.mem_write(entry,bytes(code));objects.clear();m.invoke(entry)
    assert len(objects)==2 and objects[0][0]==obj and objects[1][0]!=obj,'Sprite caller-frame bridge lost context'
    m.w(fake_frame,fake_frame+0x40);m.w(fake_frame+4,0xC4A6C5);m.w(fake_frame+0x44,0xD36941)
    objects.clear();m.invoke(entry);assert len(objects)==2,'Mirrored native head bridge lost parent context'
    m.w(fake_frame+0x44,0xC4A098);objects.clear();m.invoke(entry)
    assert len(objects)==1,'Mirrored ground helper escaped its exclusion'
    # Replay the actual HD-body/native-head quads from the reported live defect.
    # Native depth corrections differ, but overlapping screen layers must still
    # form an overlapping ground silhouette on the common actor plane.
    live=json.loads((ROOT/'tools/fixtures/celestial_shadow_hd_depth.json').read_text())
    large_cells=m.alloc(400*400*20)
    m.u.mem_write(large_cells,struct.pack('<4fI',-97.,-97.,-97.,-97.,1)*(400*400))
    m.w(ground+8,200);m.w(ground+12,200);m.w(resource+0x110,400);m.w(resource+0x114,400);m.w(resource+0x11c,large_cells)
    m.u.mem_write(m.player+0x10,struct.pack('<3f',*live['position']))
    live_view=m.alloc(48);m.u.mem_write(live_view,struct.pack('<12f',*live['view']))
    m.u.mem_write(m.renderer+4,struct.pack('<2f',*live['scale']))
    m.u.mem_write(m.renderer+0x30,struct.pack('<2i',*live['origin']))
    m.invoke(m.r(0x1094810+3*4),(live_view,),ecx=m.player);m.w(shadow+112,m.player)
    silhouettes=[]
    for layer in live['layers']:
        quad_live=bytes.fromhex(layer['quad_hex']);m.u.mem_write(vertices,quad_live)
        projected.clear();objects.clear()
        m.invoke(export('@CelestialSpriteShadowSubmit@28'),(obj,6,m.player,0xD3695C,0),ecx=m.renderer)
        assert len(objects)==2 and len(projected)==4,(layer['name'],'Omitted native sprite layer')
        assert bytes(m.u.mem_read(vertices,128))==quad_live,'Modified accepted HD/native sprite data'
        silhouettes.append([(point[0][0],point[0][2]) for point in projected])
    polygons=[[quad[index] for index in [0,1,3,2]] for quad in silhouettes]
    for polygon in polygons:
        for i,point in enumerate(polygon):
            following=polygon[(i+1)%4];axis=(following[1]-point[1],point[0]-following[0])
            intervals=[[p[0]*axis[0]+p[1]*axis[1] for p in shape] for shape in polygons]
            assert max(min(v) for v in intervals)<=min(max(v) for v in intervals)+1e-4,'Head shadow detached from body'
    m.u.mem_write(m.player+0x10,struct.pack('<3f',0.,-97.,1.))
    # Night, rain and map exit retain only the untouched stock scenery draw.
    for packet in [dict(phase=1,map_name=b'prt_fild08\0'),dict(map_name=b'prontera\0')]:
        m.receive(m.snapshot(push=True,**packet));m.frame();original_calls.clear()
        m.invoke(m.r(0x104D450+7*4),(view,0),ecx=actor)
        assert len(original_calls)==1
    print('PASS: terrain-projected mesh/sprite geometry, moving sun direction, alpha/UV ownership, native actor forwarding, map/night gates and terrain immutability')


if __name__=='__main__':main()
