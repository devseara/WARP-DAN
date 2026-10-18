"""Exercise real QJS entry detours and redesigned container right-click payloads.

The native hit-test/message dispatch boundary is mocked after its displaced
prologue. This tests integration/identity and ABI, not live mouse geometry.
"""
from pathlib import Path
import hashlib, json, struct, zlib
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EBP, UC_X86_REG_ECX
from verify_item_description_native import WIN, ITEM
from verify_item_description_comparison import DualVM, COMP

ROOT=Path(__file__).resolve().parents[1]
SOURCE=0x5010e000
EQUIPPED=0x5010e800

def item(index, item_id=1201, refine=7):
    data=bytearray(0xb8)
    struct.pack_into('<I',data,4,index)
    data[0x2c:0x31]=str(item_id).encode()+b'\0'
    struct.pack_into('<I',data,0x40,15)
    data[0x5c]=1
    struct.pack_into('<I',data,0x60,refine)
    struct.pack_into('<H',data,0x88,2)
    struct.pack_into('<4I',data,0x1c,4001,4140,0,0)
    struct.pack_into('<I',data,0x98,1)
    struct.pack_into('<hhB',data,0x9c,5,17,1)
    return bytes(data)

def overlay(v, name):
    feature=name+'UI'
    blob=(ROOT/f'Inputs/{feature}/runtime.bin').read_bytes()
    meta=json.loads((ROOT/f'Inputs/{feature}/runtime.json').read_text())
    _,version,size,count,_,_,client,crc=struct.unpack_from('<8I',blob)
    assert version==1 and client==20250716 and zlib.crc32(blob[32:])==crc
    source=(ROOT/f'Scripts/Runtime/{feature}/runtime.cpp').read_bytes().replace(b'\r\n',b'\n')
    assert hashlib.sha256(source).hexdigest()==meta['source_sha256']
    base=0x52000000
    code=bytearray(blob[32+count*4:]);assert len(code)==size
    for offset in struct.unpack_from('<'+'I'*count,blob,32):
        struct.pack_into('<I',code,offset,struct.unpack_from('<I',code,offset)[0]+base)
    v.u.mem_map(base,(size+4095)&~4095);v.u.mem_write(base,bytes(code))
    # The redesigned patch owns its virtual slot. IDUI intercepts the native
    # function it calls, so either patch-selection order has the same route.
    table=SOURCE+0x400;v.write32(SOURCE,table)
    v.write32(table+32*4,base+meta['exports']['@'+name+'Right@16'])
    return v.read32(table+32*4)

def checks(pe,m):
    hits=[]
    for redesigned in [False,True]:
        for scope,hook in enumerate(m['sourceHooks'],1):
            assert hook['name']==['Inventory','Cart','Storage'][scope-1]
            v=DualVM(pe,m)
            v.u.mem_write(ITEM,item(1 if scope==3 else 2))
            v.u.mem_write(EQUIPPED,item(9,item_id=1202,refine=9))
            v.stubs.pop(hook['trampoline']['vir'],None)
            continuation=hook['address']+5
            code=bytearray()
            def dispatch(window,pointer):
                code.extend(b'\x6a\x00\x6a\x00\x6a\x00\x68'+struct.pack('<I',pointer)+b'\x6a\x18\x6a\x00\xb9'+struct.pack('<I',window))
                code.extend(b'\xe8'+struct.pack('<i',m['entries']['ItemDescriptionMessage']-(continuation+len(code)+5)))
            dispatch(WIN,ITEM)
            dispatch(COMP,EQUIPPED)
            code.extend(b'\x8b\xe5\x5d\xc2\x08\x00')
            v.u.mem_write(continuation,bytes(code))
            observed=[]
            def observe(u,pc,size,_):
                if pc==continuation:
                    bp=u.reg_read(UC_X86_REG_EBP)
                    observed.append((v.s('origin'),u.reg_read(UC_X86_REG_ECX),v.read32(bp+8),v.read32(bp+12)))
            v.u.hook_add(UC_HOOK_CODE,observe)
            entry=overlay(v,hook['name']) if redesigned else hook['address']
            v.run(entry,[70,90],ecx=SOURCE)
            assert observed==[(scope,SOURCE,70,90)] and v.s('origin')==0
            assert len(v.sent)==2 and v.s('ready') and v.c(12)
            main,comparison=v.sent
            assert struct.unpack_from('<IIHHH',main,16)==(1201,1 if scope==3 else 2,scope,7,2)
            assert struct.unpack_from('<4I',main,32)==(4001,4140,0,0)
            assert struct.unpack_from('<hhB',main,48)==(5,17,1)
            assert struct.unpack_from('<IIHHH',comparison,16)==(1202,9,1,9,2)
            assert struct.unpack_from('<I',comparison,12)[0]&0x80000000
            replies=[]
            for request in [main,comparison]:
                v.sent=[request];replies.append(v.response())
            v.sent=[main,comparison]
            assert v.receive(replies[1])==v.receive(replies[0])==1
            assert v.run('CustomDraw',[WIN],ecx=0)==v.run('CustomDraw',[COMP],ecx=0)==1
            # Late packets from a different container cannot replace this pane.
            wrong=bytearray(replies[0]);struct.pack_into('<H',wrong,32,2 if scope!=2 else 3)
            assert v.receive(wrong)==0
            hits.append(dict(source=hook['name'],redesigned=redesigned,first_slot=True,comparison_scope=1))

    # Catalog windows can carry a local index. Never send it or instance rolls
    # as inventory ownership; still use the redesigned description body.
    v=DualVM(pe,m);v.u.mem_write(ITEM,item(77));v.run('Message',[0,24,ITEM,0,0,0])
    assert len(v.sent)==1 and v.s('ready')
    request=v.sent[-1]
    assert struct.unpack_from('<I',request,20)[0]==0 and request[24:30]==bytes(6)
    assert request[32:84]==bytes(52)
    assert v.receive(v.response())==1 and v.run('CustomDraw',[WIN],ecx=0)==1
    # Rapid cross-container switching retains the newest source and ignores
    # stale responses, including identical IDs/indices in two containers.
    v=DualVM(pe,m);responses=[]
    for scope in [1,2,3,1]:
        v.open(scope=scope);responses.append(v.response())
    for response in responses[:-1]:assert v.receive(response)==0
    assert v.receive(responses[-1])==1
    return dict(passed=True,routes=hits,checks=[
        'Actual QJS detours and displaced prologues preserve native right-click ABI',
        'Stock and redesigned Inventory/Cart/Storage callbacks retain exact refine, cards and options',
        'First storage slot uses index 1; inventory/cart use index 2',
        'Nested equipped comparison remains inventory-owned and both panes accept independent snapshots',
        'Catalog fallback, cross-container switching and stale/wrong-scope reply rejection'])
