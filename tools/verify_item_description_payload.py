"""Run freshly compiled IDUI code in memory without producing a game EXE.

An existing 2025-07-16 client supplies unchanged native scrollbar code. Engine
boundaries remain mocked, as in the release suites. This does not claim WARP
integration or live acceptance. No source client or deployment file is written.
"""
from pathlib import Path
from unittest.mock import patch
import argparse, hashlib, json, struct
import pefile
from verify_item_description_native import VM, WIN, ITEM, PIXELS, HITS, LINES, SHAPES, STOP

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = {0:0x892A50,1:0xA245C0,4:0x8A0E70,19:0x8BAEC0,20:0x8B4200,25:0x8B97B0,
            28:0x8BA470,31:0x8B9B70,32:0x8BB4C0,35:0x5A8AF0,37:0x8C18B0}
COMPARISON = {**ORIGINAL,0:0x892A80,4:0x8A0EB0,25:0x8B9820,31:0x8B9BA0,32:0x8BB6D0,37:0x8C3540}
COMPONENT = {**ORIGINAL,0:0x892480,4:0x8A0E20,31:0x8B9AC0,37:0x8BF3B0}

class MemoryImage:
    def __init__(self, engine, blob, node='node'):
        self.image = bytearray(engine.get_memory_mapped_image())
        offset = (len(self.image) + 0xFFFF) & ~0xFFFF
        self.image.extend(bytes(offset - len(self.image)))
        payload = bytearray.fromhex(blob['hex']); base = 0x400000 + offset
        for fixup in blob['relocations']:
            old = struct.unpack_from('<I', payload, fixup)[0]
            struct.pack_into('<I', payload, fixup, old - blob['imageBase'] + base)
        entries = {name:base+value for name,value in blob['exports'].items()}
        original = [ORIGINAL.get(i,0) for i in range(53)]
        comparison = [COMPARISON.get(i,0) for i in range(53)]
        component = [COMPONENT.get(i,0) for i in range(53)]
        config = [STOP+0x200,STOP+0x220,STOP+0x240,0,*original,0x94F380,0x8BB340,1,*comparison,*component]
        assert len(config) == 166
        struct.pack_into('<166I',payload,blob['exports']['ItemDescriptionConfig'],*config)
        self.image.extend(payload)
        def relative(op, at, target): return bytes([op])+struct.pack('<i',target-at-5)
        site, resume = 0x8B438A, 0x8B4391
        bridge = 0x400000+len(self.image)
        code = b'\x9c\x60\xfc\x57'+relative(0xe8,bridge+4,entries['ItemDescriptionHeader'])
        code += b'\x61\x9d\x83\xbf\xd4\x01\x00\x00\x00'
        code += relative(0xe9,bridge+len(code),resume)
        self.image.extend(code)
        self.image[site-0x400000:site-0x400000+7] = relative(0xe9,site,bridge)+b'\x90\x90'
        hooks=[]
        names={0:'Destroy',4:'Position',19:'Process',20:'Draw',25:'Down',28:'Move',31:'Up',32:'Right',35:'Wheel',37:'Message'}
        if 'ItemDescriptionSize' in entries:names[1]='Size'
        for table, stock in [(0x1032AAC,original),(0x1032C5C,comparison),(0x1032B84,component)]:
            for slot,name in names.items():
                address=table+slot*4; replacement=entries['ItemDescription'+name]
                struct.pack_into('<I',self.image,address-0x400000,replacement)
                hooks.append(dict(address=address,original=stock[slot],replacement=replacement))
        self.manifest=dict(entries=entries,original=original,comparisonOriginal=comparison,componentOriginal=component,config=config,hooks=hooks,
            state=dict(vir=entries['ItemDescriptionState'],size=123664),comparisonState=dict(vir=entries['ItemDescriptionComparisonState'],size=123664),
            componentState=dict(vir=entries['ItemDescriptionComponentState'],size=123664),
            packetRefs=dict(packetCtorA=config[0],packetSend=config[1]),source_sha256=blob['source_sha256'],
            headerHook=dict(address=site,resume=resume,bridge=dict(vir=bridge)))
        if 'ItemDescriptionNativeOpen' in entries:
            from verify_item_description_lifecycle import install
            self.manifest['lifecycleHooks']=install(self.image,entries,node)
    def get_memory_mapped_image(self): return bytes(self.image)
    def get_data(self,offset,length): return bytes(self.image[offset:offset+length])

def rows_response(v, rows):
    data=v.response();data[128:]=bytes(len(data)-128)
    struct.pack_into('<H',data,38,len(rows));struct.pack_into('<4H',data,40,2,0,0,4)
    for i,(section,kind,item,flags,slot,label,text) in enumerate(rows):
        off=128+i*192;struct.pack_into('<HHIHH',data,off,section,kind,item,flags,slot)
        data[off+16:off+64]=label.encode().ljust(48,b'\0')
        data[off+64:off+192]=text.encode().ljust(128,b'\0')
    return data

def layout_lines(v):
    return [(y,row,kind,style,x,text.split(b'\0')[0].decode()) for y,row,kind,style,x,text in
            [struct.unpack('<iiBBh192s',v.u.mem_read(v.state+LINES+i*204,204)) for i in range(v.s('lines'))]]

def feature_checks(pe, m):
    from PIL import Image
    from verify_item_description_comparison import DualVM, COMP
    component_rows=[(8,2,4001,0,1,'Slot 1','Installed card'),(8,1,0,0,1,'','Damage +20%'),
                    (8,2,4002,0,2,'Slot 2','Installed card'),(8,1,0,0,2,'','ATK +20%'),
                    (8,2,0,8,3,'Slot 3','Empty'),(8,2,0,8,4,'Slot 4','Empty')]
    grade_rows=[(5,0,0,0,0,'Current grade','None'),(5,1,0,2,0,'Rare','ATK +1%'),
                (5,1,0,2,0,'Epic','ATK +2%'),(5,1,0,2,0,'Mythic','ATK +3%'),(5,1,0,2,0,'Legendary','ATK +5%')]
    rows=component_rows+grade_rows+[(11,0,0,0,0,'Discard','Yes')]
    hidden_rows=[r for r in rows if r[0]!=5]
    def fresh(show=False):
        v=VM(pe,m);v.open();v.receive(rows_response(v,rows if show else hidden_rows));v.run('Draw');return v
    hidden, shown = fresh(), fresh(True)
    for text in ['Grade:','Current grade  None','Rare','Epic','Mythic','Legendary']:
        assert text not in [line[-1] for line in layout_lines(hidden)]
        assert text in [line[-1] for line in layout_lines(shown)]
    assert hidden.s('content') < shown.s('content') and hidden.s('hits')==shown.s('hits')==2
    assert not any('Installed card' in line[-1] for line in layout_lines(hidden))
    assert any('Slot 3' in line[-1] for line in layout_lines(hidden))
    shapes=[struct.unpack('<iihhHH',shown.u.mem_read(shown.state+SHAPES+i*16,16)) for i in range(shown.s('shapes'))]
    gy,gh,gx,gw,_,_=next(shape for shape in shapes if shape[4]==10)
    shown.s('scroll',gy);shown.run('Draw')
    w=shown.read32(WIN+0x14)
    assert len({shown.read32(PIXELS+((154+y)*w+gx+gw-12)*4) for y in (12,gh//2,gh-12)})==1,'Grade background bands'
    # The server controls visibility by omitting Grade rows from each snapshot.
    for show in [False,True]:
        v=DualVM(pe,m);right,left=v.open_pair()
        v.sent=[v.sent[-1]];left=rows_response(v,rows if show else hidden_rows)
        assert v.receive(right)==v.receive(left)==1
        v.run('Draw',ecx=COMP)
        assert any(t=='Grade:' for _,_,t,*_ in v.draws)==show
    v=fresh();nodes={4001:0x50110000,4002:0x50110200};lookups=[]
    v.write32(0x159c088,0x50109000)
    v.stub(0xa7e780,4,lambda ecx,args:lookups.append(v.read32(args[0])) or nodes.get(v.read32(args[0]),0))
    for item,node in nodes.items():
        stem=f'card{item}';v.u.mem_write(node+0x40,stem.encode()+b'\0');v.write32(node+0x54,15)
        v.u.mem_write(node+0x58,stem.encode()+b'\0');v.write32(node+0x6c,15)
        v.add_texture('유저인터페이스\\collection\\'+stem+'.bmp',Image.new('RGBA',(75,100),(20,180,80,255)))
    v.s('layout',0);v.run('Draw');before=len(lookups);paths=len(v.loaded_paths)
    hits=[struct.unpack('<5i',v.u.mem_read(v.state+HITS+i*20,20)) for i in range(2)]
    header=bytes(v.u.mem_read(PIXELS,116*360*4))
    for _ in range(8):
        for x,y,ww,hh,row in hits:
            v.run('Move',[x+8,154+y+8]);v.run('Draw')
            assert v.s('hover')==100+row
            assert bytes(v.u.mem_read(PIXELS,116*360*4))==header,'hover changed passive header'
            v.write32(WIN+0x58,0);v.run('Move',[x+9,154+y+9]);assert v.read32(WIN+0x58)==0
    assert len(lookups)==before and len(v.loaded_paths)==paths,'hover repeated artwork lookups'
    for x in [292,306,320,334]:
        v.run('Move',[x,105]);assert v.s('hover')==0
        sent=len(v.sent);v.run('Down',[x,105]);v.run('Up',[x,105]);assert len(v.sent)==sent
    v.run('Message',[0,5,0,0,0,0]);v.open();v.receive(rows_response(v,rows));v.run('Draw')
    assert len(lookups)>before,'close/reopen did not invalidate thumbnails'
    # Forged metadata must not create an occupied-card check mark.
    v=fresh()
    assert v.read32(PIXELS+(104*360+290)*4)==0xffffffff,'occupied slot check absent'
    assert v.read32(PIXELS+(104*360+304)*4)==0xffffffff,'second occupied slot check absent'
    assert v.read32(PIXELS+(104*360+318)*4)!=0xffffffff,'empty slot marked occupied'
    empty=[(8,2,0,8,i,f'Slot {i}','Empty') for i in range(1,5)]
    v.s('pending',1);v.receive(rows_response(v,empty));v.run('Draw')
    assert v.read32(PIXELS+(104*360+290)*4)!=0xffffffff
    # Model normal game frames: the compositor draws only dirty windows. Hover
    # must update just the changed panels on the existing surface, not replay the
    # title/illustration and every body row while walking continues underneath.
    v=fresh();surface=v.read32(WIN+0x24)
    hits=[struct.unpack('<5i',v.u.mem_read(v.state+HITS+i*20,20)) for i in range(2)]
    full_draws=lambda:sum(slot==20 for slot,_,_ in v.native_calls)
    transition_fills=[]
    for target in [hits[0],hits[1],None,hits[0]]:
        v.write32(WIN+0x58,0);v.write32(surface+0x1c,0);v.draws=[]
        count=full_draws();fills=v.fill_calls
        x,y=(target[0]+8,154+target[1]+8) if target else (150,130)
        v.run('Move',[x,y]);assert v.read32(WIN+0x58),'hover did not notify the native compositor'
        assert v.fill_calls==fills,'mouse handler painted synchronously'
        v.run('Draw');v.write32(WIN+0x58,0);transition_fills.append(v.fill_calls-fills)
        assert full_draws()==count and v.read32(surface+0x1c)&1,'native surface upload not requested'
        assert not any(text in ('Weapon','17','Unbound') for _,_,text,*_ in v.draws),'hover repainted header'
        partial=bytes(v.u.mem_read(PIXELS,v.surface_size));fills=v.fill_calls
        v.run('Draw');assert partial==bytes(v.u.mem_read(PIXELS,v.surface_size)),'partial hover pixels differ from full draw'
        assert transition_fills[-1]<v.fill_calls-fills,'hover did not reduce fill work'
    v.write32(WIN+0x58,0);v.write32(surface+0x1c,0)
    count=full_draws();fills=v.fill_calls;draws=len(v.draws);destroyed=v.scroll_destroyed;sent=len(v.sent)
    for frame in range(120):
        v.now+=16;v.run('Process');v.run('Message',[0,12,0,0,0,0])
        v.run('Move',[hits[0][0]+8+(frame%2),154+hits[0][1]+8])
        if v.read32(WIN+0x58):v.run('Draw');v.write32(WIN+0x58,0)
    assert full_draws()==count and v.fill_calls==fills and len(v.draws)==draws,'steady hover repeated render work'
    assert v.scroll_destroyed==destroyed and len(v.sent)==sent,'routine notifications rebuilt the view or sent requests'
    assert not v.read32(surface+0x1c),'steady hover dirtied the surface'
    # Multiple mouse events before the next frame repaint only the final pair.
    count=full_draws();fills=v.fill_calls
    v.run('Move',[150,130]);v.run('Move',[hits[1][0]+8,154+hits[1][1]+8])
    assert v.fill_calls==fills and v.read32(WIN+0x58)
    v.run('Draw');v.write32(WIN+0x58,0);assert full_draws()==count
    partial=bytes(v.u.mem_read(PIXELS,v.surface_size));v.run('Draw')
    assert partial==bytes(v.u.mem_read(PIXELS,v.surface_size)),'coalesced hover lost the previous/final highlight'
    # A wheel event on a body that already fits does not discard queued hover.
    v.write32(WIN+0x58,0);v.run('Move',[hits[0][0]+8,154+hits[0][1]+8])
    count=full_draws();v.run('Wheel',[-120]);v.run('Draw')
    assert full_draws()==count,'no-op wheel discarded the queued partial repaint'
    v.s('scroll',0);v.run('Draw')
    # Pending full redraws must remain authoritative; do not partially draw stale
    # geometry. Scrolling clips panels identically to a normal full repaint.
    v.write32(WIN+0x58,1);fills=v.fill_calls;v.run('Move',[150,130]);assert v.fill_calls==fills and v.read32(WIN+0x58)==1
    v.s('scroll',hits[0][1]+16);v.run('Draw');v.write32(WIN+0x58,0)
    v.run('Move',[hits[0][0]+8,160]);v.run('Draw');v.write32(WIN+0x58,0);partial=bytes(v.u.mem_read(PIXELS,v.surface_size))
    v.run('Draw');assert partial==bytes(v.u.mem_read(PIXELS,v.surface_size)),'clipped hover repaint differs'
    # The equipped pane must update its own surface without touching the main one.
    from verify_item_description_comparison import COMP_PIXELS
    d=DualVM(pe,m);right,left=d.open_pair();d.sent=[d.sent[-1]];left=rows_response(d,rows)
    d.receive(right);d.receive(left);d.run('Draw');d.run('Draw',ecx=COMP)
    untouched=bytes(d.u.mem_read(PIXELS,d.read32(WIN+0x14)*d.read32(WIN+0x18)*4))
    hit=struct.unpack('<5i',d.u.mem_read(d.comparison+HITS,20));d.write32(COMP+0x58,0)
    d.run('Move',[hit[0]+8,154+hit[1]+8],ecx=COMP)
    assert d.read32(COMP+0x58);d.run('Draw',ecx=COMP);d.write32(COMP+0x58,0)
    assert bytes(d.u.mem_read(PIXELS,len(untouched)))==untouched
    partial=bytes(d.u.mem_read(COMP_PIXELS,d.read32(COMP+0x14)*d.read32(COMP+0x18)*4))
    d.run('Draw',ecx=COMP);assert partial==bytes(d.u.mem_read(COMP_PIXELS,len(partial)))
    return dict(passed=True,checks=['Grade off/on hides/restores the complete section in both panes without layout gaps',
        'uniform Grade panel; installed subtitles removed; empty slots retained',
        'card hover reuses scaled thumbnails and preserves passive header indicators',
        'moving within a card does not trigger a redraw; close/reopen invalidates artwork',
        'forged item metadata does not mark slots occupied',
        'hover transitions repaint only changed panels; pixels match full draws, including clipped and comparison panels',
        'mouse events coalesce until composition; no-op scrolling preserves queued hover',
        '120 steady-hover frames and routine notifications cause zero redraws, lookups, requests or scrollbar rebuilds'],
        hover_artwork_lookups=0,steady_hover_frames=120,steady_hover_full_redraws=0,transition_fill_calls=transition_fills)

def motion_checks(pe, m):
    from verify_item_description_edges import long_response
    from verify_item_description_comparison import DualVM, COMP, COMP_PIXELS
    v=VM(pe,m);v.open();v.receive(long_response(v));v.run('Draw')
    full=lambda:sum(slot==20 for slot,_,_ in v.native_calls)
    surface=v.read32(WIN+0x24);sx=v.read32(WIN+0x14)-20
    saved_header=bytes(v.u.mem_read(PIXELS,154*360*4));scrolls=[]
    def frame(actions, redraw=True):
        v.write32(WIN+0x58,0);v.write32(surface+0x1c,0)
        before=full();fills=v.fill_calls;v.draws=[]
        for name,args in actions:v.run(name,args)
        assert v.fill_calls==fills,'input handler painted synchronously'
        assert bool(v.read32(WIN+0x58))==redraw,(actions,v.s('scroll'))
        if not redraw:return
        v.run('Draw');v.write32(WIN+0x58,0)
        assert full()==before,'scroll invoked native full title/art renderer'
        assert v.read32(surface+0x1c)&1,'partial scroll was not uploaded'
        assert bytes(v.u.mem_read(PIXELS,len(saved_header)))==saved_header,'scroll changed fixed header'
        partial=bytes(v.u.mem_read(PIXELS,v.surface_size));body_text=list(v.draws)
        assert all(154<=y<548 for _,y,*_ in body_text),'scroll drew outside the body'
        cost=v.fill_calls-fills;v.draws=[];v.run('Draw')
        assert bytes(v.u.mem_read(PIXELS,v.surface_size))==partial,'partial scroll pixels differ from full draw'
        assert [t for t in v.draws if 154<=t[1]<548]==body_text,'partial scroll text differs from full draw'
        assert cost<v.fill_calls-fills-cost,'partial scroll did not reduce fill work'
        assert bytes(v.u.mem_read(PIXELS+v.surface_size,64))==b'\xcd'*64
        scrolls.append(v.s('scroll'))
    frame([('Wheel',[0]),('Wheel',[120])],False)
    frame([('Wheel',[-120])]);frame([('Wheel',[-120])]*4)
    frame([('Down',[sx,156]),('Up',[sx,156])])
    frame([('Down',[sx,546]),('Up',[sx,546])])
    frame([('Message',[v.scrollbar,9,0,0,0,0])])
    frame([('Message',[v.scrollbar,10,0,0,0,0])])
    # Thumb capture and outside release, with many events coalesced per frame.
    v.s('scroll',0);v.run('Draw');v.write32(WIN+0x58,0)
    frame([('Down',[sx,170]),('Move',[sx,3000])])
    assert v.s('scroll')==v.s('content')-394 and v.read32(0x131f4e8+0x19c)==v.scrollbar
    frame([('Up',[sx,3000]),('Wheel',[-120])],False)
    assert not v.read32(0x131f4e8+0x19c)
    # Re-enter the last-position thumb, drag to top, then hold stationary.
    frame([('Down',[sx,530]),('Move',[sx,154])])
    assert v.s('scroll')==0
    frame([('Up',[sx,154])],False)
    v.run('Move',[sx,156]);v.run('Draw');v.write32(WIN+0x58,0)
    frame([('Move',[sx,156])]*60,False)
    # Invalid layouts/surfaces must still take the complete native draw path.
    v.write32(WIN+0x58,1);count=full();v.run('Wheel',[-120]);v.run('Draw');assert full()==count+1
    v.write32(WIN+0x58,0);v.run('Wheel',[-120]);v.s('layout',0);count=full();v.run('Draw');assert full()==count+1
    # Opening a component preserves the parent surface and invokes one native
    # card-detail message with its CItem; both owned strings are still released.
    v=VM(pe,m);v.open();v.receive(v.response());v.run('Draw')
    x,y,w,h,row=struct.unpack('<5i',v.u.mem_read(v.state+HITS,20));point=[x+8,154+y+8]
    v.run('Move',point);v.run('Draw');v.write32(WIN+0x58,0)
    v.write32(0x159c088,0x50109000);v.stub(0xa7e780,4,lambda ecx,args:0x50109400)
    target,table,handler=0x50130000,0x50131000,STOP+0x380
    v.write32(target,table);v.write32(table+37*4,handler);calls=[];destroys=[]
    v.stub(0xa39340,4,lambda ecx,args:calls.append(('factory',args[0])) or target)
    v.stub(handler,24,lambda ecx,args:calls.append(('open',ecx,args[1],int(v.cstring(args[2]+0x2c)))) or 0)
    v.stub(0x4f08f0,0,lambda ecx,args:destroys.append(ecx) or 0)
    before=(v.fill_calls,len(v.draws),len(v.sent));image=bytes(v.u.mem_read(PIXELS,v.surface_size))
    for _ in range(3):v.run('Down',point);v.run('Up',point);v.run('Right',point)
    assert calls==[('factory',82),('open',target,24,4001)]*6
    assert len(destroys)==12 and all(destroys[i]-destroys[i+1]==0x18 for i in range(0,12,2))
    assert not v.read32(WIN+0x58) and before==(v.fill_calls,len(v.draws),len(v.sent))
    assert image==bytes(v.u.mem_read(PIXELS,v.surface_size))
    v.run('Down',point);v.run('Up',[0,130]);assert len(calls)==12,'release off card opened details'
    # Comparison scrolling only touches its own body.
    d=DualVM(pe,m);right,left=d.open_pair();d.sent=[d.sent[-1]];left=long_response(d)
    d.receive(right);d.receive(left);d.run('Draw');d.run('Draw',ecx=COMP)
    main=bytes(d.u.mem_read(PIXELS,360*560*4));d.write32(COMP+0x58,0)
    count=sum(slot==20 for slot,_,_ in d.native_calls);d.run('Wheel',[-120],ecx=COMP);d.run('Draw',ecx=COMP)
    assert sum(slot==20 for slot,_,_ in d.native_calls)==count
    partial=bytes(d.u.mem_read(COMP_PIXELS,360*560*4));d.run('Draw',ecx=COMP)
    assert partial==bytes(d.u.mem_read(COMP_PIXELS,len(partial))) and main==bytes(d.u.mem_read(PIXELS,len(main)))
    # A scroll supersedes pending hover rectangles and clears the old pixels.
    v=VM(pe,m);v.open()
    rows=[(8,2,4001,0,1,'Slot 1','Installed card')]+[(8,1,0,0,1,'','Long component effect +20% '*3)]*12
    v.receive(rows_response(v,rows));v.run('Draw');assert v.s('content')>394
    x,y,w,h,row=struct.unpack('<5i',v.u.mem_read(v.state+HITS,20));v.write32(WIN+0x58,0)
    count=sum(slot==20 for slot,_,_ in v.native_calls)
    v.run('Move',[x+8,154+y+8]);v.run('Wheel',[-120]);v.run('Move',[150,130]);v.run('Draw')
    assert sum(slot==20 for slot,_,_ in v.native_calls)==count
    partial=bytes(v.u.mem_read(PIXELS,v.surface_size));v.run('Draw')
    assert partial==bytes(v.u.mem_read(PIXELS,v.surface_size)),'scroll/hover coalescing left stale pixels'
    # Full 64-row opening: wrapping does not measure every character prefix.
    v=VM(pe,m);measurements=[]
    def measure(ecx,args):
        value=v.cstring(args[0]).decode('utf8','replace');measurements.append(value);return len(value)*6
    v.stub(0xa21c90,24,measure);v.open();v.receive(long_response(v));v.run('Draw')
    assert len(measurements)<1800,len(measurements)
    return dict(passed=True,scroll_positions=scrolls,component_opens=6,parent_click_redraws=0,
                opening_font_measurements=len(measurements),checks=[
        'wheel, arrows, track/page and thumb scroll paint body only with full-render pixel/text parity',
        'coalesced scroll, bounds, zero wheel and stationary scrollbar hover avoid redundant work',
        'capture release, full invalidation, comparison isolation and surface bounds preserved',
        'left/right component clicks open native details once, release strings and leave parent unchanged',
        '64-row opening uses bounded font measurements instead of per-character prefix measurement'])

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--engine',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--node',default='node',help='Node executable for emitting the actual QJS lifecycle hooks')
    ap.add_argument('--features-only',action='store_true',help='Run only the focused Grade/hover and motion regression groups')
    args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    blob=json.loads((ROOT/'Outputs/ItemDescription/native/blob.json').read_text())
    for name,digest in blob['source_sha256'].items():assert hashlib.sha256((ROOT/'tools/native'/name).read_bytes()).hexdigest()==digest
    engine_hash=hashlib.sha256(args.engine.read_bytes()).hexdigest()
    image=MemoryImage(pefile.PE(str(args.engine)),blob,args.node);m=image.manifest
    (args.output/'native-manifest.json').write_text(json.dumps({'itemDescription':m},indent=2))
    original_init=VM.__init__
    def init(vm,pe,manifest):
        original_init(vm,pe,manifest)
        vm.fill_calls=0
        def fill(ecx,values):
            vm.fill_calls+=1
            window,x,y,w,h,color=values
            surface=vm.read32(window+0x24);pixels=vm.read32(surface+0x18);pitch=vm.read32(surface+4)
            assert x+w<=vm.read32(window+0x14) and y+h<=vm.read32(window+0x18)
            for yy in range(y,y+h):vm.u.mem_write(pixels+(yy*pitch+x)*4,struct.pack('<I',color)*w)
        vm.stub(m['config'][2],24,fill)
    from verify_item_description_native import verify as native
    from verify_item_description_edges import verify as edges
    from verify_item_description_artwork import verify as artwork
    from verify_item_description_comparison import verify as comparison
    from verify_item_description_skin import verify as skin
    from verify_item_description_header import verify as header
    results={}
    with patch.object(pefile,'PE',return_value=image),patch.object(VM,'__init__',init):
        for name,fn in [('native',native),('edges',edges),('artwork',artwork),('comparison',comparison),('skin',skin),('header',header)]:
            if args.features_only:continue
            print('VERIFY '+name,flush=True);results[name]=fn(args.output)
        results['features']=feature_checks(image,m)
        results['motion']=motion_checks(image,m)
        from verify_item_description_lifecycle import checks as lifecycle_checks
        print('VERIFY lifecycle',flush=True);results['lifecycle']=lifecycle_checks(image,m)
        from verify_item_description_components import checks as component_checks
        print('VERIFY components',flush=True);results['components']=component_checks(image,m)
    assert hashlib.sha256(args.engine.read_bytes()).hexdigest()==engine_hash
    report=dict(passed=True,engine_sha256=engine_hash,source_sha256=blob['source_sha256'],groups=list(results),
                fresh_payload=True,game_exe_created=False,engine_boundaries_mocked=True,live_accepted=False,
                features=results['features'],motion=results['motion'],lifecycle=results['lifecycle'],components=results['components'])
    (args.output/'payload-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
