"""Exercise announcement-only ITEML conversion, native parsers and emitted drawing in memory."""
import argparse,json,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ECX,UC_X86_REG_ESP,UC_X86_REG_EAX
from test_chat_item_icons import IconMachine,native_crt,native_font_boundaries,b62,TAIL
import test_stock_announcement_icons as stock

def setup(exe,patch):
    m=IconMachine(exe);native_crt(m);native_font_boundaries(m)
    for write in patch['writes']:m.u.mem_write(write['va'],bytes.fromhex(write['hex']))
    m.string('<ITEML>',0x1204068);m.string('</ITEML>',0x1204080)
    m.pane=m.window(parent=m.window());m.manager=m.alloc(0x100);panes=m.alloc(4)
    m.w(panes,m.pane);m.w(m.manager+0xf4,panes);m.w(m.manager+0xf8,panes+4)
    m.names={501:'Red Potion',1201:'+9 [Epic] Knife [3]',1202:'Knife',5001:'[Epic] Poo Poo Hat',9999999:'Largest ID'}
    m.decoded=[];m.native_names=[]
    # Locale normalization is a boundary; both original ITEML parsers, base62
    # tokenizer, std::string ownership and name-to-announcement paths execute.
    def normalize():
        out=m.args(1)[0];source=m.u.reg_read(UC_X86_REG_ESP)+8
        m.string(m.str_value(source),out);m.ret(28,out)
    m.stub(0x7FBFC0,normalize)
    def construct():
        item=m.u.reg_read(UC_X86_REG_ECX);m.u.mem_write(item,bytes(248));m.ret(0,item)
    def database_item():
        vector,item=m.args(2);start,end=m.r(vector),m.r(vector+4)
        fields=list(struct.unpack('<'+'I'*((end-start)//4),m.u.mem_read(start,end-start)));m.decoded.append(fields)
        assert len(fields)>=11,fields
        m.w(item+4,fields[2]);m.w(item+0x60,fields[3]);m.w(item+0x88,fields[5]);m.ret(8,fields[2] in m.names)
    def format_name():
        out,flag=m.args(2);item=m.u.reg_read(UC_X86_REG_ECX);id=m.r(item+4)
        m.native_names.append((id,m.r(item+0x60),m.r(item+0x88)))
        m.string(m.names[id],out);m.ret(8,out)
    m.stub(0x6A1B20,construct);m.stub(0x85B630,database_item);m.stub(0x6A2CE0,format_name)
    return m

def link(id,details="'00)00)00)00)00",equipment=False):
    return '<ITEML>'+('000041' if equipment else '000000')+b62(id)+details+'</ITEML>'

def convert(m,target,text):
    original=m.string(text);out=m.alloc(24);snapshot=m.str_value(original)
    m.invoke(target,m.manager,[out,original]);assert m.u.reg_read(UC_X86_REG_EAX)==out
    assert m.str_value(original)==snapshot,'announcement mutated the chat/source string'
    return m.str_value(out)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('exe');ap.add_argument('patch',type=Path);a=ap.parse_args()
    patch=json.loads(a.patch.read_text());m=setup(a.exe,patch);target=patch['contract']['links']
    hat=link(5001);old=convert(m,0x8E1730,hat)
    assert old==' '*8+'[Epic] Poo Poo Hat' and '^i[' not in old,old
    print('PASS reproduced current bug: native announcement conversion keeps chat spacing/name but loses the item icon')
    weapon=link(1201,"%09&01'04)12)34)56)78+01,02-03",True)
    for raw,expected in [
        (hat,'^i[5001][Epic] Poo Poo Hat'),
        (weapon,'^i[1201]+9 [Epic] Knife [3]'),
        ('Winner: '+hat+' / '+link(501),'Winner: ^i[5001][Epic] Poo Poo Hat / ^i[501]Red Potion'),
        (link(9999999),'^i[9999999]Largest ID'),
        ('^i[5001]'+hat,'^i[5001][Epic] Poo Poo Hat'),
        ('^i[5001,0]'+hat,'^i[5001,0][Epic] Poo Poo Hat'),
        ('Plain broadcast','Plain broadcast'),
        ('^i[909]Jellopy','^i[909]Jellopy'),
    ]:
        assert convert(m,target,raw)==expected,(raw,convert(m,target,raw),expected)
    assert (1201,9,4) in m.native_names
    assert any(v[:6]==[4,1,1201,9,1,4] and v[7:11]==[64,190,316,442] for v in m.decoded),m.decoded
    for site in [0xCB8437,0xCB7870]:assert (m.r(site+1)+site+5)&0xffffffff==target
    print('PASS both announcement routes, actual native ITEML decoding, grade/refine/cards/options, exact names, multiple items and explicit-icon deduplication')
    # Make native fallback observable for malformed/oversized inputs without
    # asking the stock client parser to accept deliberately corrupt CItems.
    seen=[]
    def fallback():
        out,source=m.args(2);seen.append(m.str_value(source));m.string(seen[-1],out);m.ret(8,out)
    m.stub(0x8E1730,fallback)
    bad=[link(0),link(10000000),hat[:-1],hat.replace("'00", "'!0"),hat.replace(')00','',1),
         '<ITEML>000000ZZZZZZZZZZZZZZZZZZZZ'+TAIL,'<ITEML>0000001</ITEML>',
         link(501).replace('000000','00000T'),link(501,'\'00)00)00)00)00'+('+01,02-03'*6)),
         'X'*1024,hat+'X'*1000]
    for raw in bad:assert convert(m,target,raw)==raw,raw
    m.names[5001]='N'*1020;assert convert(m,target,hat)==hat,'expanded name overflow must use original input'
    # Database lookup failure, no panes and empty messages preserve stock input.
    for raw in [link(42),'']:assert convert(m,target,raw)==raw
    m.w(m.manager+0xf8,m.r(m.manager+0xf4));assert convert(m,target,hat)==hat
    print('PASS malformed and oversized links, expansion bound, missing items/panes, unchanged source and native ABI')
    stock.PATCH_WRITES=patch;render=stock.StockMachine(a.exe)
    render.show(b'^i[5001][Epic] Poo Poo Hat')
    assert render.requests==[(5001,1)]
    assert render.rendered[0][0]=='[Epic] Poo Poo Hat' and render.rendered[0][1]==25
    assert render.rendered[0][3]==0xffff
    print('PASS announcement icon sits immediately beside the graded name with original broadcast color; client file remains read only')

if __name__=='__main__':main()
