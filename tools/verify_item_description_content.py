"""Exercise authored client text and held-button dragging in the fresh native payload."""
import json
import struct
from pathlib import Path
from verify_item_description_native import VM, WIN, PIXELS, HITS, SHAPES, OFF
from verify_item_description_components import TripleVM, DETAIL
from verify_item_description_comparison import COMP
from verify_item_description_payload import rows_response, layout_lines


def install_text(v, item_id, lines):
    # The profiled native map stores ItemInfo vectors of char pointers, not
    # std::string objects. Use the real map/vector offsets in the payload.
    base = 0x52000000
    if not getattr(v, 'text_memory', False):
        v.u.mem_map(base, 0x20000); v.text_memory = True
    head, node, vector, cursor = base, base + 0x100, base + 0x200, base + 0x2000
    v.write32(0x1255130, head); v.write32(head + 4, node)
    v.u.mem_write(head + 0xd, b'\1'); v.u.mem_write(node + 0xd, b'\0')
    v.write32(node, head); v.write32(node + 8, head); v.write32(node + 0x10, item_id)
    v.write32(node + 0x20, vector); v.write32(node + 0x24, vector + 4*len(lines))
    for i, line in enumerate(lines):
        data = line.encode('utf8') + b'\0'
        v.write32(vector + i*4, cursor); v.u.mem_write(cursor, data); cursor += len(data)


def checks(pe, m, output=None):
    fixtures = json.loads((Path(__file__).parent/'fixtures/item_description/authored-text.json').read_text(encoding='utf8'))
    results = []
    for sample in fixtures:
        sample['id'] = int(sample['id'])
        # Real itemInfo_f adds footers after the final authored section. Include
        # its exact format plus whitespace/case variants seen in other loaders.
        footer = ['________________________', '^0000CCItem ID:^000000 '+str(sample['id']),
                  '  ^777777___________^000000  ', ' item id : '+str(sample['id']),
                  '\tITEMID:\t'+str(sample['id']), '----------', '==========']
        v = VM(pe, m); install_text(v, sample['id'], sample['lines'] + footer); v.open(itemid=sample['id'])
        fonts = []
        def draw(ecx, args):
            fonts.append((v.cstring(args[2]).decode('utf8','replace'),args[5],args[6],args[7],args[0],args[1]))
            return v.draw_text(ecx,args)
        v.stub(0xa25a70,36,draw)
        rows = [(1,0,0,0,0,'Base DEF','3'), (1,0,0,0,0,'Weight',str(sample['weight'])),
                (1,0,0,0,0,'Item Collection','Yes'), (10,0,0,1,0,'Base level',str(sample['level'] or 0)),
                (10,0,0,2,0,'Job','Not allowed'), (10,0,0,2,0,'Equip eligibility','Not allowed'),
                (3,1,0,0,0,'','Duplicated server effect'), (5,0,0,0,0,'Current grade','None'),
                (5,1,0,2,0,'Rare','ATK +1%')]
        reply = rows_response(v, rows); reply[96:128] = sample['kind'].encode().ljust(32,b'\0')
        assert v.receive(reply); v.run('Draw'); lines = layout_lines(v)
        text = ' '.join(x[-1] for x in lines)
        assert 'Description:' in text
        assert '[' not in text and 'Duplicated server effect' not in text
        assert 'Special Effects:' not in text and 'Base Stats:' not in text and 'Set Bonuses:' not in text
        assert 'Grade:' in text and 'Current grade' in text
        assert 'doesn\'t have bonus effect' not in text
        assert 'Compound on:' not in text
        assert 'item id' not in text.lower() and 'itemid:' not in text.lower()
        assert '___' not in text and '---' not in text and '===' not in text
        if sample['id'] == 2115:
            assert 'messenger of Freya' in text and "Odin's Blessing" in text and 'Instead' in text
            assert any(x[2] == 4 and x[1] == 0x990099 for x in lines), 'itemInfo colors were lost'
            assert any('Job:' in x[-1] and x[3] == 7 for x in lines), 'unmet job not red'
        if sample['id'] == 4178:
            assert 'Item Collection:' in text and 'Flee +1' in text
            assert 'Tarot Card of Fate' in text and 'Green Ferus Card' in text
            visible = {x[0]:x for x in fonts if 118 <= x[5] <= 132}
            for label in ('Compound On:','Garment'):
                assert visible[label][1] == visible['Lv.:'][1] == visible['Weight:'][1] == 12
                assert visible[label][3] == visible['Lv.:'][3] == visible['Weight:'][3] == 1
                assert visible[label][5] == 124
            assert visible['Compound On:'][2] == visible['Lv.:'][2]
            assert visible['Garment'][2] == visible['Any'][2] == visible[str(sample['weight'])][2]
            assert visible['Compound On:'][2] != visible['Garment'][2]
            assert visible['Lv.:'][4] < visible['Compound On:'][4] < visible['Garment'][4] < visible['Weight:'][4]
            # Successful reload can toggle collection off without rebuilding the client.
            v.open(itemid=sample['id']); reply = rows_response(v, [r for r in rows if r[5] != 'Item Collection'])
            reply[96:128] = sample['kind'].encode().ljust(32,b'\0'); assert v.receive(reply); v.run('Draw')
            assert 'Item Collection:' not in ' '.join(x[-1] for x in layout_lines(v))
        if sample['id'] == 5124:
            v.open(itemid=sample['id'])
            changed=[(s,k,item,2 if label=='Base level' else 1 if label=='Job' else flags,slot,label,value)
                for s,k,item,flags,slot,label,value in rows]
            reply=rows_response(v,changed);reply[96:128]=sample['kind'].encode().ljust(32,b'\0')
            assert v.receive(reply);v.run('Draw');lines=layout_lines(v)
            assert any('Job:' in x[-1] and x[3]==6 for x in lines)
            assert any('Base Level:' in x[-1] and x[3]==7 for x in lines)
        # The copied description remains valid even if the source cache is gone;
        # scrolling/hover/drag never consult or reparse that source.
        v.write32(0x1255130, 0); before = v.s('lines')
        measurements = [0]
        def measure(ecx, args):
            measurements[0] += 1
            return len(v.cstring(args[0]).decode('utf8','replace')) * 6
        v.stub(0xa21c90,24,measure)
        v.write32(WIN + 0x58, 0) # the manager clears dirty after composition
        v.run('Wheel', [-120]); v.run('Draw'); assert v.s('lines') == before
        if sample['id'] == 4178:
            assert measurements[0] == 0, 'scrolling remeasured the authored card text'
        results.append(sample['id'])
        if output and sample['id'] in (2115,4178,1201,5124,501):
            v.s('scroll',0); v.render(output / ('authored-'+str(sample['id'])+'.png'))

    grade_cases = grade_checks(pe,m,output)
    footer_cases = footer_checks(pe,m)
    v = TripleVM(pe,m); right,left=v.open_pair(); v.receive(right); v.receive(left); v.run('Draw'); v.run('Draw',ecx=COMP)
    v.click_card(); v.now += 200; v.run('Process',ecx=DETAIL); v.receive(v.response()); v.run('Draw',ecx=DETAIL)
    samples = 0
    for window in (WIN,COMP,DETAIL):
        for offset,value in ((0x7c,0x70000000),(0x80,0x70000000),(0x84,0),(0x88,0)):
            v.write32(window+offset,value) # deliberately stale native drag anchors
        for coords in ([170,80],[5000,5000],[-5000,-5000]):
            v.run('Down',[150,70],ecx=window)
            v.run('Drag',coords,ecx=window) # no hover callback before the quick release
            v.run('Up',coords,ecx=window)
            assert v.u.mem_read(window+0x28,1)==b'\1'
            assert v.read32(window+0x1c)<1024 and v.read32(window+0x20)<768
            assert not v.read32(0x131f4e8+0x19c); samples += 1
        v.run('Down',[150,70],ecx=window); v.write32(0x131f4e8+0x19c,0)
        before=len(v.native_calls); v.run('Drag',[180,80],ecx=window)
        state = v.component if window==DETAIL else v.comparison if window==COMP else v.state
        x,y,_,_,_ = struct.unpack('<5i',v.u.mem_read(state+HITS,20))
        v.run('Move',[x+5,154+y+5],ecx=window)
        assert v.read32(state+OFF['hover'])>=100, 'lost capture left hover stuck when release went elsewhere'
        v.run('Up',[349,7],ecx=window)
        assert len(v.native_calls)==before, 'lost capture release reached a stock handler'
    return dict(passed=True,authored_items=results,grade_continuation_cases=grade_cases,item_id_footer=footer_cases,fast_drag_samples=samples,engine_boundaries_mocked=True,live_accepted=False)


def footer_checks(pe,m):
    from verify_item_description_edges import long_response
    def track(v):
        calls=[]
        def draw(window,args):
            value=v.cstring(args[2]).decode('utf8','replace')
            calls.append((window,args[0],args[1],value,args[5],args[6],args[7]))
            if value.startswith('ItemID: '):
                # Mark a footer pixel so partial repaint checks detect erasure.
                surface=v.read32(window+0x24); pixels=v.read32(surface+0x18)
                v.write32(pixels+(args[1]*v.read32(surface+4)+args[0])*4,0xff000000)
            return v.draw_text(window,args)
        v.stub(0xa25a70,36,draw)
        return calls
    def verify_label(v,calls,window,item):
        label=f'ItemID: {item}'; w=v.read32(window+0x14); h=v.read32(window+0x18)
        expected=(window,w-6-len(label)*6,h-15,label,10,0,0)
        assert [c for c in calls if c[3].startswith('ItemID: ')]==[expected]
        assert all(y+size+4<=h-18 for win,x,y,value,size,color,bold in calls if y>=154 and value!=label)
        return expected

    # All main-pane origins, including a ten-digit unsigned ID, and a compact
    # window. No stale ID is painted while a replacement snapshot is loading.
    for scope,item in ((0,4294967295),(1,1201),(2,501),(3,4178)):
        v=VM(pe,m); calls=track(v); v.open(scope=scope,itemid=item)
        v.run('Draw'); assert not any(c[3].startswith('ItemID: ') for c in calls)
        reply=long_response(v); assert v.receive(reply)
        w,h=(288,268) if scope==0 else (360,560)
        v.set_size(WIN,[w,h]); calls.clear(); v.run('Draw'); verify_label(v,calls,WIN,item)
        assert v.read32(v.scrollbar+0x18)==h-172
        footer=bytes(v.u.mem_read(PIXELS+(h-18)*w*4,18*w*4))
        calls.clear(); measures=[]
        v.stub(0xa21c90,24,lambda ecx,args:measures.append(v.cstring(args[0])) or len(v.cstring(args[0]))*6)
        v.write32(WIN+0x58,0); v.run('Wheel',[-120]); v.run('Draw')
        assert not any(value.startswith(b'ItemID: ') for value in measures)
        assert not any(c[3].startswith('ItemID: ') for c in calls)
        assert footer==bytes(v.u.mem_read(PIXELS+(h-18)*w*4,18*w*4))
        v.run('Move',[w-20,h-10]); assert v.s('hover')==0
        calls.clear(); v.open(scope=scope,itemid=1202); v.run('Draw')
        assert not any(c[3].startswith('ItemID: ') for c in calls)
        assert not v.receive(reply), 'old reply reactivated a different item footer'
        assert v.receive(v.response()); calls.clear(); v.run('Draw'); verify_label(v,calls,WIN,1202)
        v.s('force',1); calls.clear(); v.run('Draw')
        assert not any(c[3].startswith('ItemID: ') for c in calls)

    v=TripleVM(pe,m); calls=track(v); right,left=v.open_pair()
    v.receive(right); v.receive(left); v.run('Draw'); v.run('Draw',ecx=COMP)
    v.click_card(); v.now+=200; v.run('Process',ecx=DETAIL); v.receive(v.response())
    for window,state in ((WIN,v.state),(COMP,v.comparison),(DETAIL,v.component)):
        item=v.read32(state+OFF['snapshot']+24)
        calls.clear(); v.run('Draw',ecx=window); verify_label(v,calls,window,item)
    return dict(passed=True,source_scopes=4,independent_panes=3,font_pixels=10,
                color='black',alignment='bottom-right',partial_scroll_footer_redraws=0,
                stale_snapshot_rejected=True,compact_window=True,unsigned_id=True)


def grade_checks(pe,m,output):
    # Reproduce Builder::long_effect's word-boundary packet chunks, using the
    # real Valkyrie Shield tier text. No server or gameplay edits are needed.
    tiers = [('Rare',6,21),('Epic',7,22),('Mythic',8,23),('Legendary / S',10,25)]
    cases = 0
    for width,flags in ((360,2),(288,2),(360,1),(360,4)):
        v=VM(pe,m);v.open(itemid=2115)
        rows=[(5,0,0,0,0,'Current grade','None')]; expected=[]
        for label,mdef,percent in tiers:
            value=f'INT-based MDEF +{mdef}; '+ '; '.join(f'{element} damage resistance +{percent}%'
                for element in ('Water','Fire','Dark','Undead'))
            first=len(rows); at=0
            while at<len(value):
                end=min(at+120,len(value))
                if end<len(value):
                    space=value.rfind(' ',at,end+1)
                    if space>at+40:end=space
                rows.append((5,1,0,flags,0,label if at==0 else '',value[at:end]))
                at=end
                while at<len(value) and value[at]==' ':at+=1
            expected.append((first,label,value))
        assert v.receive(rows_response(v,rows));v.set_size(WIN,[width,560]);v.run('Draw');lines=layout_lines(v)
        shapes=[struct.unpack('<H',v.u.mem_read(v.state+SHAPES+i*16+12,2))[0] for i in range(v.s('shapes'))]
        # Exactly one lock/check/info icon per complete tier.
        icon=6 if flags==2 else 4 if flags==1 else 7
        assert shapes.count(icon)==4
        for first,label,value in expected:
            tier=[x for x in lines if x[1]==first]
            if flags==4:
                assert ' '.join(x[-1] for x in tier)==label+': '+value
            else:
                assert tier[0][-1]==label
                body=tier[1:]
                assert ' '.join(x[-1] for x in body)==value
                assert all(x[4]==body[0][4] and x[4]>tier[0][4] for x in body)
            assert not any(x[1]==first+1 for x in lines), 'continuation became a separate tier'
        if output and width==360 and flags==2:v.render(output/'shield-grade-continuations.png')
        cases+=1
    return cases
