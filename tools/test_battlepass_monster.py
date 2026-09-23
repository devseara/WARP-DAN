"""Run the BPUI-embedded Bestiary fitter; only final engine blit is doubled."""
import argparse,math,struct
from test_battlepass_board import BoardMachine

ap=argparse.ArgumentParser();ap.add_argument('exe');args=ap.parse_args()
m=BoardMachine(args.exe);surface=m.r(m.obj+0x24);vt=m.alloc(64);blit=m.alloc(16)
m.w(surface,vt);m.w(vt+52,blit);calls=[]
m.stub(blit,lambda:(calls.append(m.args(10)),m.ret(40)))
for sw,sh in [(24,24),(2000,150),(100,2200),(1200,1200)]:
    spr=m.alloc(0x528);act=m.alloc(0x11C);actions=m.alloc(12);frame=m.alloc(68)
    images=m.alloc(4);image=m.alloc(16);layers=m.alloc(36)
    m.u.mem_write(image,struct.pack('<hh',sw,sh));m.w(images,image)
    for off,value in enumerate([images,images+4,images+4]):m.w(spr+0x510+off*4,value)
    for off,value in enumerate([actions,actions+12,actions+12]):m.w(act+0x110+off*4,value)
    for off,value in enumerate([frame,frame+68,frame+68]):m.w(actions+off*4,value)
    for off,value in enumerate([layers,layers+36,layers+36,1]):m.w(frame+32+off*4,value)
    m.u.mem_write(layers,struct.pack('<iiiiIffii',-sw//2,-sh,0,0,0xffffffff,1,1,0,0))
    for w,h in [(96,102),(31,33)]:
        calls.clear();m.invoke(m.c['monster'],0,(m.obj,spr,act,140,176,w,h,1200))
        assert len(calls)==1
        a=calls[0];assert a[:4]==[140,176,w,h]
        ox,oy=struct.unpack('<ii',struct.pack('<II',a[6],a[7]));scale=struct.unpack('<f',struct.pack('<I',a[8]))[0]
        assert math.isfinite(scale) and 0<scale<=1
        assert -sw//2*scale+ox>=-.01 and -sh*scale+oy>=-.01
        assert sw/2*scale+ox<=w+.01 and oy<=h+.01
    m.w(frame+44,4097);calls.clear();m.invoke(m.c['monster'],0,(m.obj,spr,act,0,0,96,102,1200));assert not calls
print('PASS BPUI Bestiary x86 adapter: small/wide/tall/large sprite geometry, both-axis fit, ABI and malformed-vector rejection; final engine compositor doubled')
