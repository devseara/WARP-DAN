"""Execute the description-only title callback with native/GDI boundaries mocked."""
import struct
from unicorn.x86_const import UC_X86_REG_ESP
from verify_item_description_native import VM, WIN
from verify_item_description_components import TripleVM, DETAIL
from verify_item_description_comparison import COMP


def title_boundary(v, name):
    log = dict(formatted=[], fonts=[], painted=[], released=[], color=0x123456, font=77, stock=[])
    def formatter(ecx, args):
        item,color,vector,cursor,remaining,special,zero,flags=args
        log['formatted'].append((ecx,item,flags))
        data=name.encode('utf8'); assert len(data)<256
        start=v.read32(cursor);v.u.mem_write(start,data+b'\0');v.write32(cursor,start+len(data))
        v.write32(remaining,256-len(data));v.write32(color,0x00ff00)
        v.u.mem_write(vector,struct.pack('<III',0x50160000,0x50160008,0x50160020))
    def release(ecx,args):
        sp=v.u.reg_read(UC_X86_REG_ESP)
        log['released'].append((v.read32(sp+4),v.read32(sp+8)))
    def dc_open(ecx,args):
        v.write32(ecx,0x1234);v.write32(ecx+4,log['font'])
        log['device']=ecx
    def dc_close(ecx,args):log['font']=v.read32(ecx+4)
    def set_font(ecx,args):
        font,size,bold,italic=args
        v.write32(ecx+12,font);v.write32(ecx+16,size);v.write32(ecx+20,65001)
        log['fonts'].append((font,size,bold,italic))
    def decode(p,n):return bytes(v.u.mem_read(p,n*2)).decode('utf-16-le')
    def convert(ecx,args):
        cp,flags,source,n,target,cap=args;assert cp==65001 and flags==0
        data=bytes(v.u.mem_read(source,n)).decode('utf8').encode('utf-16-le')
        assert len(data)//2<=cap;v.u.mem_write(target,data);return len(data)//2
    def select(ecx,args):old=log['font'];log['font']=args[1];return old
    def color(ecx,args):old=log['color'];log['color']=args[1];return old
    def measure(ecx,args):
        hdc,p,n,bounds=args
        # UTF-16 boundaries may be probed during binary search.
        text=bytes(v.u.mem_read(p,n*2)).decode('utf-16-le','replace')
        v.u.mem_write(bounds,struct.pack('<ii',len(text)*7,14));return 1
    def paint(ecx,args):
        hdc,x,y,p,n=args
        log['painted'].append(dict(window=log['formatted'][-1][0],x=x,y=y,text=decode(p,n),color=log['color'],font=log['font']))
        return 1
    v.stub(0x8a0570,32,formatter);v.stub(0xdbbc7f,0,release)
    v.stub(0x5443c0,4,dc_open);v.stub(0x5446f0,0,dc_close);v.stub(0x546f60,16,set_font)
    v.stub(0xa6f060,0,lambda ecx,args:65001)
    v.stub(0x546270,20,lambda ecx,args:88)
    v.stub(0x8972c0,28,lambda ecx,args:log['stock'].append((ecx,args)) or 99)
    for i,(address,size,fn) in enumerate([(0xfc1200,24,convert),(0xfc1120,8,select),
            (0xfc10e0,8,color),(0xfc112c,16,measure),(0xfc10dc,20,paint)]):
        target=0x50006000+i*32;v.write32(address,target);v.stub(target,size,fn)
    return log


def checks(pe,m):
    samples=['Dragon Tail Card','+7 Mace Bloody Explosive [4]',
             '[Legendary] +12 Very Long Decorated Equipment Name With Several Cards [4]',
             'Épée du dragon — 龍の盾', 'Long '+('A'*30)+' 🐉 '+('B'*40)]
    count=0
    for width in (360,288):
        for name in samples:
            v=VM(pe,m);v.open();v.receive(v.response());v.set_size(WIN,[width,560])
            log=title_boundary(v,name);args=[90,10,WIN+0xb8,0,0,12,0]
            v.run('Title',args)
            assert log['formatted']==[(WIN,WIN+0xb8,0)]
            assert log['fonts']==[(0,14,1,0)] and log['released']==[(0x50160000,32)]
            assert log['color']==0x123456 and log['font']==77, 'DC state leaked'
            assert 1<=len(log['painted'])<=2 and not log['stock']
            for draw in log['painted']:
                assert draw['color']==0xffffff and draw['font']==88
                assert draw['y'] in (10,26) and draw['x']==90
                assert draw['x']+len(draw['text'])*7<=width-24
            text=' '.join(d['text'] for d in log['painted'])
            assert text==name or text.endswith('...') and name.startswith(text[:-3])
            count+=1
    for mode in ('loading','forced','disabled','stale','unowned'):
        v=VM(pe,m);v.open();log=title_boundary(v,'Dragon Tail Card')
        if mode!='loading':v.receive(v.response())
        if mode=='forced':v.s('force',1)
        if mode=='disabled':v.write32(m['entries']['ItemDescriptionConfig']+59*4,0)
        if mode=='stale':v.write32(WIN+0xb8+0x60,9)
        if mode=='unowned':v.s('owner',0)
        args=[90,10,WIN+0xb8,0x808080,0,12,0];v.run('Title',args)
        if mode=='loading':assert log['painted'] and not log['stock']
        else:assert log['stock']==[(WIN,args)] and not log['painted'] and not log['formatted']
    v=TripleVM(pe,m);right,left=v.open_pair();v.receive(right);v.receive(left);v.run('Draw');v.run('Draw',ecx=COMP)
    v.click_card();v.now+=200;v.run('Process',ecx=DETAIL);v.receive(v.response());v.run('Draw',ecx=DETAIL)
    log=title_boundary(v,'Dragon Tail Card')
    for window in (WIN,COMP,DETAIL):v.run('Title',[90,10,window+0xb8,0,0,12,0],ecx=window)
    assert [d['window'] for d in log['painted']]==[WIN,COMP,DETAIL]
    return dict(passed=True,name_width_cases=count,scoped_panes=3,fallback_cases=4,
                font_size=14,bold=True,color='FFFFFF',dc_state_restored=True,live_accepted=False)
