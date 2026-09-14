"""Offline x86 checks for text-only chat tabs, white controls and native actions.

Win32 GDI and window-manager boundaries are explicit doubles. No game message
is sent, no process is injected, and this does not claim live visual acceptance.
"""
import argparse
import struct

from unicorn.x86_const import *
from test_chat_item_icons import IconMachine
from test_modern_chat_ui import pack


def contract(m):
    tag=m.pe.__data__.find(b'ModernChatUI.v12\0')
    assert tag>=0,'ModernChatUI v12 was not applied'
    va=m.base+m.pe.get_rva_from_offset(tag)
    data=m.pe.get_memory_mapped_image();positions=[];pos=0
    while (pos:=data.find(pack(va),pos))>=0:
        positions.append(m.base+pos);pos+=1
    assert len(positions)==1
    names='face size weight state getFont tabLabel inputFinalize send emoji cursor'.split()
    return dict(zip(names,[m.r(positions[0]+4+i*4) for i in range(len(names))]))


def test_font(m,c):
    created=[];drawn=[];acquired=[];released=[]
    hdc=0x4455;base_font=0xAABB;bold_font=base_font if c['weight']==700 else 0xCCDD
    font_weights={base_font:c['weight'],bold_font:700}
    dc={'font':0x1122,'color':0x123456,'mode':2}
    original=dict(dc)
    module=m.alloc(16);extent=m.alloc(16);output=m.alloc(16)
    def get_module():
        assert m.cstr(m.args(1)[0]).lower()=='gdi32.dll'
        m.ret(4,module)
    def get_proc():
        handle,name=m.args(2);assert handle==module
        addresses={'GetTextExtentPoint32A':extent,'ExtTextOutA':output}
        m.ret(8,addresses[m.cstr(name)])
    def create_font():
        args=m.args(14);weight=c['weight'] if not created else 700
        assert args==[(-c['size'])&0xFFFFFFFF,0,0,0,weight,0,0,0,1,0,0,3,0,c['face']]
        created.append(args);m.ret(56,base_font if len(created)==1 else bold_font)
    def dc_field(key):
        handle,value=m.args(2);assert handle==hdc
        previous=dc[key];dc[key]=value;m.ret(8,previous)
    def acquire():
        painter=m.u.reg_read(UC_X86_REG_ECX);surface=m.args(1)[0]
        m.w(painter,hdc);m.w(painter+4,dc['font']);m.w(painter+8,surface)
        acquired.append(surface);m.ret(4,painter)
    def release():
        assert dc==original,'font/color/background state leaked into another draw'
        released.append(m.u.reg_read(UC_X86_REG_ECX));m.ret(0)
    def measure():
        handle,text,count,size=m.args(4);assert handle==hdc and dc['font'] in font_weights
        assert 0<=count<=255
        m.w(size,count*(c['size']//2+(font_weights[dc['font']]==700)))
        m.w(size+4,c['size']+2);m.ret(16,1)
    def draw():
        handle,x,y,flags,rect,text,count,spacing=m.args(8)
        assert handle==hdc and flags==4 and spacing==0
        assert dc['font'] in font_weights and dc['color'] in (0xC7C7C7,0xFFFFFF) and dc['mode']==1
        clip=tuple(m.r(rect+i*4) for i in range(4))
        assert clip[1:4:2]==(1,19)
        drawn.append((m.cstr(text),x,y,clip,count,dc['color'],font_weights[dc['font']]))
        surface=acquired[-1];pixels=m.r(surface+0x18);width=m.r(surface+4)
        if clip[0]<=x<clip[2] and 1<=y<19:m.w(pixels+(y*width+x)*4,dc['color'])
        m.ret(32,1)
    m.iat(0xFC1268,get_module);m.iat(0xFC1390,get_proc)
    m.iat(0xFC1114,create_font);m.iat(0xFC1120,lambda:dc_field('font'))
    m.iat(0xFC10E0,lambda:dc_field('color'));m.iat(0xFC10E8,lambda:dc_field('mode'))
    m.stub(0x5443C0,acquire);m.stub(0x5446F0,release)
    m.stub(extent,measure);m.stub(output,draw)
    for title in ['Main','Guild','Party','Market','Battle','A renamed long custom channel']:
        for cell_width in [32,106,180]:
            for selected in [0,1]:
                pane=m.window(w=256,h=20)
                m.invoke(c['tabLabel'],pane,[m.text_buffer(title),4,cell_width,selected])
                weight=700 if selected else c['weight'];color=0xFFFFFF if selected else 0xC7C7C7
                text_width=len(title)*(c['size']//2+(weight==700))
                expected_x=4+max(2,(cell_width-text_width)//2)
                expected_y=max(1,(20-(c['size']+2))//2)
                assert drawn[-1]==(title,expected_x,expected_y,(6,1,cell_width+2,19),len(title),color,weight)
    # Execute native tab clicks, then the complete emitted tab draw. Exactly
    # the actual selected page must switch to white/bold, with no stale state.
    parent,tab=m.setup();m.invoke(m.r(0x1037FD0),parent)
    tab_draw=m.r(m.r(tab)+0x50);tab_click=m.r(m.r(tab)+0x64)
    titles=['Main','Market','Battle','Party','Guild']
    for selected in range(5):
        m.invoke(tab_click,tab,[selected*106+40,8]);assert m.r(tab+0x7C)==selected
        m.invoke(tab_draw,tab)
        assert [row[0] for row in drawn[-5:]]==titles
        for index,row in enumerate(drawn[-5:]):
            weight=700 if index==selected else c['weight']
            color=0xFFFFFF if index==selected else 0xC7C7C7
            assert row[5:]==(color,weight)
            width=len(titles[index])*(c['size']//2+(weight==700))
            assert row[1]==106*index+max(2,(106-width)//2)
        m.invoke(m.r(m.r(tab)+0x7C),tab,[selected*106+40,8])
    assert len(created)==(1 if c['weight']==700 else 2),'fonts must be cached, not allocated per draw'
    assert m.r(c['state'])==base_font and m.r(c['state']+16)==bold_font
    assert len(acquired)==len(released)==len(drawn)==61
    assert dc==original


def test_font_failure(m,c):
    attempts=[]
    m.iat(0xFC1268,lambda:(attempts.append(True),m.ret(4,0)))
    pane=m.window(w=106,h=20)
    for selected in [0,1,0]:
        m.invoke(c['tabLabel'],pane,[m.text_buffer('Battle'),0,106,selected])
        assert m.texts[-1]==('Battle',35,4,pane)
        pix,w,_=m.pixels(pane)
        assert m.r(pix+(4*w+35)*4)==(0xFFFFFF if selected else 0xC7C7C7)
    assert len(attempts)==1


def test_icons(m,c):
    # Tab icons are removed, but the native PM input indicator is retained.
    parent,tab=m.setup();recipient=m.r(parent+0xC0)
    for name,asset in [('', 'icon_general.png'),('WhisperTarget','icon_pm.png')]:
        m.string(name,recipient+0xD8);m.images.clear()
        main=m.r(0x1037FD0)
        png=next(t for t in m.targets(main) if bytes(m.u.mem_read(t,12))==bytes.fromhex('55 8b ec 83 ec 20 53 56 57 8b 71 24'))
        m.stub(png,m.image)
        m.invoke(main,parent)
        assert any(row[:3]==(asset,5,201) for row in m.images)
        assert any(row[:3]==('btn_emote2.png',549,202) for row in m.images)
        assert not any(row[0]=='icon_emotion.png' for row in m.images)
        m.images.clear();m.texts.clear();m.invoke(m.r(m.r(tab)+0x50),tab)
        assert not m.images,'text-only tabs drew an icon'
        assert [row[0] for row in m.texts]==['Main','Market','Battle','Party','Guild']
    for asset in ['btn_emote2.png','icon_direct.png','icon_settings.png','icon_lock_on.png','icon_lock_off.png']:
        m.load_texture(asset)
        colors={pixel&0xFFFFFF for pixel in m.asset_pixels[asset] if pixel>>24}
        assert colors=={0xE5F2FF},(asset,colors)


def test_control_cursor(m,c):
    # Execute the native setter, including its change-only animation reset.
    cursor=m.alloc(0x80);m.w(0x121333C,cursor)
    notifications=[]
    def notify():
        assert m.u.reg_read(UC_X86_REG_ECX)==0x131F4E8
        notifications.append(m.args(5));m.ret(20)
    m.stub(0xA4AD20,notify)
    assert m.r(0x1037F80+0x78)==c['cursor']
    assert m.r(0x1037EA8+0x78)==0xA23470,'floating/other cursor callback changed'
    assert m.r(0x102DD44+0x78)==0xA23470,'shared tab cursor callback changed'
    for width,height in [(180,100),(594,240),(800,320)]:
        parent,tab=m.setup(width,height)
        for pressed in [0,1]:
            m.w(0x11E40E4,pressed)
            for unlocked in [0,1]:
                m.u.mem_write(0x15FAAEC,bytes([unlocked]))
                for x in [0,108,width-52,width-51,width-28,width-27,width-19,
                          width-18,width-11,width-10,width-4,width-3,width-1,width]:
                    for y in [height-43,height-42,height-23,height-22,height-21,
                              height-20,height-1,height]:
                        hand=(width-51<=x<width-3 and height-42<=y<height-22 or
                              width-18<=x<width-10 and height-20<=y<height)
                        m.invoke(c['cursor'],parent,[x,y])
                        assert m.r(cursor+0x50)==(2 if hand else 0),(width,height,x,y,pressed)
                        assert m.r(0x11E40E4)==pressed,'cursor callback modified button state'
        m.invoke(c['cursor'],parent,[width-40,height-32]);assert m.r(cursor+0x50)==2
        m.w(cursor+0x24,123);m.w(cursor+0x54,3);before=len(notifications)
        m.invoke(c['cursor'],parent,[width-40,height-32])
        assert (m.r(cursor+0x24),m.r(cursor+0x54))==(123,3),'hover restarted hand animation'
        assert len(notifications)==before
        for capture in [parent,tab]:
            m.w(0x131F4E8+0x19C,capture)
            m.invoke(c['cursor'],parent,[width-40,height-32]);assert m.r(cursor+0x50)==0
        m.w(0x131F4E8+0x19C,0)
        m.w(parent+0x30,0);m.invoke(c['cursor'],parent,[width-40,height-32])
        assert m.r(cursor+0x50)==0,'hidden chat requested hand cursor'
        m.w(parent+0x30,1);m.w(parent+0xBC,0)
        m.invoke(c['cursor'],parent,[width-40,height-32]);assert m.r(cursor+0x50)==0
        m.invoke(c['cursor'],parent,[width-15,height-10]);assert m.r(cursor+0x50)==2
        m.invoke(c['cursor'],parent,[120,30]);assert m.r(cursor+0x50)==0,'hand leaked onto body'
    # Native cursors.act action 2 uses frame 0 while up, and native left-button
    # state drives its pressed frames. Render calls are outside this slice.
    assert m.r(0xA74924)==0xA74478
    m.stub(0x70F6B0,lambda:m.ret(4,4)) # Four-frame hand action boundary double.
    for pressed,expected in [(0,0),(1,3)]:
        m.w(cursor+0x50,2);m.w(cursor+0x54,99);m.w(0x11E40E4,pressed)
        m.u.reg_write(UC_X86_REG_EDI,cursor)
        m.u.reg_write(UC_X86_REG_EBX,0x20000000)
        m.u.reg_write(UC_X86_REG_EBP,0x3000E000)
        m.u.reg_write(UC_X86_REG_ESP,0x3000D000)
        m.w(0x3000E000-4,12)
        m.u.emu_start(0xA74464,0xA7453F,count=1000)
        assert m.u.reg_read(UC_X86_REG_EIP)==0xA7453F
        assert m.r(cursor+0x54)==expected,'native pressed hand animation not retained'


def test_native_actions(m,c):
    parent,tab=m.setup();edit=m.r(parent+0xBC);recipient=m.r(parent+0xC0)
    m.string('KeepTarget',recipient+0xD8)
    m.string('Keep draft <ITEML>payload</ITEML>',edit+0xD8)
    calls=[]
    # Remove only the native event boundary double, then execute the real
    # dispatcher's entry and switch to the same 0xB8 submit branch as Enter.
    m.u.hook_del(m._stub_handles[0x8FC220]);del m._stub_handles[0x8FC220]
    def submit_entry():
        frame=m.u.reg_read(UC_X86_REG_EBP)
        calls.append(tuple(m.r(frame+8+i*4) for i in range(6)))
        assert m.u.reg_read(UC_X86_REG_EDI)==parent
        m.u.reg_write(UC_X86_REG_EAX,0)
        m.u.reg_write(UC_X86_REG_EIP,0x8FE497) # Native dispatcher epilogue; no network.
    m.stub(0x8FD8E3,submit_entry)
    for active in [0,1]:
        m.u.mem_write(0x131F50C,bytes([active]))
        m.invoke(c['send'],parent)
        assert calls[-1]==(edit,6,0xB8,0,0,0)
        assert m.r(parent+0xB4)==edit and m.r(0x131F4E8+0x1A0)==edit
    assert len(calls)==2
    emoji=[]
    def open_emoji():
        assert m.u.reg_read(UC_X86_REG_ECX)==0x131F4E8
        emoji.append(m.args(1)[0]);m.ret(4,0)
    m.stub(0xA39340,open_emoji);m.invoke(c['emoji'],parent)
    assert emoji==[0x57] and len(calls)==2,'emoji button sent the draft'
    assert m.str_value(recipient+0xD8)=='KeepTarget'
    assert m.str_value(edit+0xD8)=='Keep draft <ITEML>payload</ITEML>'
    # Profiled factory case is UICashEmotionListWnd (the supplied Emoji List),
    # not the Alt+M shortcut editor. Confirm the native table and ctor call.
    index=m.u.mem_read(0xA42CA8+0x57,1)[0]
    assert m.r(0xA42904+index*4)==0xA3DECB
    assert bytes(m.u.mem_read(0xA3DEFE,5))==bytes.fromhex('e8 0d ef d4 ff')
    m.w(parent+0xBC,0);m.invoke(c['send'],parent);m.invoke(c['emoji'],parent)
    assert len(calls)==2 and emoji==[0x57],'missing edit pointer was not guarded'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('exe')
    parser.add_argument('--font');parser.add_argument('--size',type=int);parser.add_argument('--weight',type=int)
    args=parser.parse_args()
    for test in [test_font,test_font_failure,test_icons,test_control_cursor,test_native_actions]:
        m=IconMachine(args.exe);c=contract(m)
        if args.font:assert m.cstr(c['face'])==args.font
        if args.size:assert c['size']==args.size
        if args.weight:assert c['weight']==args.weight
        test(m,c);print('PASS',test.__name__,flush=True)
    print('PASS: native selected-tab white/bold highlight, centered fonts and DC restoration,')
    print('      white controls, native hover/pressed hand, PM/Enter and Alt+L Emoji List.')
    print('In-game visual acceptance is still required.')


if __name__=='__main__':main()
