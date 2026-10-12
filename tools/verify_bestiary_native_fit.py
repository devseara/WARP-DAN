"""Execute the emitted general native fitter on real and extreme ACT layouts.

Only the final native compositor is mocked. Geometry, bounds, frame selection,
both-axis fit, padding and integer offsets execute the actual embedded C++.
"""
from pathlib import Path
import argparse,configparser,json,math,struct
import pefile
from verify_bestiary_journal import JournalVM
from dual_weapon_formats.grf_reader import GrfFile
from dual_weapon_formats.spr_reader import Spr
from dual_weapon_formats.act_reader import parse_act


def verify(directory,game):
    m=json.loads((directory/'native-manifest.json').read_text(encoding='utf-8'))['bestiary']
    pe=pefile.PE(str(directory/'bestiary-preview.exe'),fast_load=True)
    v=JournalVM(pe,m);entry=m['preview']['vir']
    del v.stubs[entry];v.u.mem_write(entry,pe.get_data(entry-pe.OPTIONAL_HEADER.ImageBase,4))
    surface=v.alloc(44);vt=v.alloc(56);v.write32(surface,vt);v.write32(vt+52,0x60000180);v.write32(v.window+0x24,surface)
    v.write32(0xfc17b0,0x60000010)
    drawn=[]
    v.stub(0x60000180,40,lambda ecx,a:drawn.append(a))
    base_heap=v.heap
    reports=[]

    def run_case(name,images,frames,viewports=((240,156),(210,168),(31,33))):
        v.heap=base_heap
        spr=v.alloc(0x528);act=v.alloc(0x11c);action=v.alloc(12);frame_ptr=v.alloc(len(frames)*68)
        for kind in (0,1):
            im=[i for i in images if i[0]==kind];ptr=v.alloc(max(4,len(im)*4))
            for index,(_,w,h) in enumerate(im):
                item=v.alloc(16);v.u.mem_write(item,struct.pack('<hh',w,h));v.write32(ptr+index*4,item)
            for o,value in enumerate((ptr,ptr+len(im)*4,ptr+len(im)*4)):v.write32(spr+0x510+kind*12+o*4,value)
        for o,value in enumerate((action,action+12,action+12)):v.write32(act+0x110+o*4,value)
        for o,value in enumerate((frame_ptr,frame_ptr+len(frames)*68,frame_ptr+len(frames)*68)):v.write32(action+o*4,value)
        bounds=[]
        for i,layers in enumerate(frames):
            ptr=v.alloc(max(4,len(layers)*36));f=frame_ptr+i*68
            for o,value in enumerate((ptr,ptr+len(layers)*36,ptr+len(layers)*36,len(layers))):v.write32(f+32+o*4,value)
            b=[]
            for j,(kind,index,x,y,sx,sy,mirror) in enumerate(layers):
                v.u.mem_write(ptr+j*36,struct.pack('<iiiiIffii',x,y,index,mirror,0xffffffff,sx,sy,0,kind))
                if index<0 or sx<=0 or sy<=0:continue
                _,w,h=[a for a in images if a[0]==kind][index]
                b.append((x*sx,y*sy,(x+w)*sx,(y+h)*sy))
            bounds.append(b)
        scales=[]
        for width,height in viewports:
            fixed=None
            for i in range(len(frames)):
                v.now=(i*60000+len(frames)-1)//len(frames);drawn.clear()
                result=v.run('preview',[v.window,spr,act,20,20,width,height,60000])
                assert result==1 and len(drawn)==1,(name,result)
                args=drawn[0];ox,oy=struct.unpack('<ii',struct.pack('<II',args[6],args[7]));scale=struct.unpack('<f',struct.pack('<I',args[8]))[0]
                assert args[:4]==[20,20,width,height] and args[4]==spr and args[5]==frame_ptr+i*68
                assert 0<scale<=1 and math.isfinite(scale),(name,scale)
                if fixed is None:fixed=(ox,oy,scale)
                assert fixed==(ox,oy,scale),'Animation must not resize/recenter per pose'
                for left,top,right,bottom in bounds[i]:
                    b=(left*scale+ox,top*scale+oy,right*scale+ox,bottom*scale+oy)
                    assert b[0]>=-0.001 and b[1]>=-0.001 and b[2]<=width+0.001 and b[3]<=height+0.001,(name,i,b,width,height)
            scales.append({'viewport':[width,height],'scale':fixed[2]})
        # Empty/malformed vectors and invalid dimensions must never reach stock.
        for args in [[v.window,spr,act,0,0,0,156,1200],[v.window,spr,act,0,0,240,156,-1]]:
            drawn.clear();assert v.run('preview',args)==0 and not drawn
        v.write32(frame_ptr+44,4097);drawn.clear();assert v.run('preview',[v.window,spr,act,0,0,240,156,1200])==0 and not drawn
        reports.append({'name':name,'frames':len(frames),'scales':scales})

    for name,w,h in [('wide',2000,150),('tall',100,2200),('large_square',1200,1200),('small_native',24,24)]:
        run_case(name,[(0,w,h)],[[(0,0,-w//2,-h,1,1,0)],[(0,0,-w//2-70,-h-90,1.1,1.2,1)]])
    run_case('small_stationary',[(0,24,24)],[[(0,0,-12,-24,1,1,0)]])
    assert all(s['scale']==1 for s in reports[-1]['scales'])
    run_case('hidden_layer',[(0,24,24)],[[(0,0,-12,-24,1,1,0),(0,0,90000,90000,0,0,0)]])
    run_case('layered_bgra_offsets',[(0,120,180),(1,640,110)], [[(0,0,-70,-200,1,1,0),(1,0,-320,-100,1,1,1)],[(0,0,100,-300,2,1,0),(1,0,-400,60,.8,2,0)]])
    cfg=configparser.ConfigParser();cfg.read(game/'DATA.INI',encoding='utf-8-sig')
    wanted={'randgris','baphomet','maya','ifrit','ktullanux','beelzebub','beelzebub_','satan_morocc','fallenbishop','detale','nidhoggur','gloomundernight','taogunka','doppelganger','phreeoni','amon_ra'}
    assets={}
    prefix='data/sprite/\ubaac\uc2a4\ud130/'
    for _,file in sorted(cfg['Data'].items(),key=lambda p:int(p[0])):
        if not (game/file).is_file():continue
        grf=GrfFile(game/file)
        for stem in wanted:
            for suffix in ['.spr','.act']:
                key=prefix+stem+suffix
                if key not in assets:
                    loose=game/key;raw=loose.read_bytes() if loose.is_file() else grf.read(key)
                    if raw:assets[key]=raw
        grf.close()
    for stem in sorted(wanted):
        if prefix+stem+'.spr' not in assets or prefix+stem+'.act' not in assets:continue
        spr=Spr(assets[prefix+stem+'.spr']);act=parse_act(assets[prefix+stem+'.act'])
        images=[(0 if i<spr.n_indexed8 else 1,im.width,im.height) for i,im in enumerate(spr.images)]
        frames=[]
        for f in act['actions'][0].frames:
            # Native loader expresses centers as top-left image offsets.
            layers=[]
            for l in f.layers:
                if l.sprite_index<0:continue
                im=spr.images[l.sprite_index+(spr.n_indexed8 if l.sprite_type else 0)]
                layers.append((l.sprite_type,l.sprite_index,l.x-im.width//2,l.y-im.height//2,l.scale_x,l.scale_y,l.mirror))
            frames.append(layers)
        run_case(stem,images,frames)
    assert any(r['name']=='randgris' for r in reports)
    pe.close()
    result={'passed':True,'engine_compositor_mocked':True,'live_accepted':False,'cases':reports}
    (directory/'native-fit-verification.json').write_text(json.dumps(result,indent=2))
    return result


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('directory',type=Path);ap.add_argument('--game',type=Path,required=True);a=ap.parse_args()
    r=verify(a.directory,a.game);print(json.dumps({'passed':r['passed'],'cases':len(r['cases']),'names':[c['name'] for c in r['cases']]}))
