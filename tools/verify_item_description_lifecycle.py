"""In-memory lifecycle hook emission and open/switch/fallback regressions."""
from pathlib import Path
import json, struct, subprocess

ROOT=Path(__file__).resolve().parents[1]
NODE=r'''
const fs=require('fs'),assert=require('assert');
const input=JSON.parse(fs.readFileSync(0,'utf8')),writes=[];
const shared=fs.readFileSync(input.root+'/Scripts/Patches/AutoCombatUI.qjs','utf8');
const assembler=shared.slice(shared.indexOf('AutoCombatUIStatic.asm = function()'),shared.indexOf('AutoCombatUIStatic.allocateBytes ='));
const native={bytesToHex:values=>values.map(v=>v.toString(16).padStart(2,'0')).join(' ')};
new Function('AutoCombatUIStatic',assembler)(native);
let next=input.next;
const Exe={Allocate(size,align){next=Math.ceil(next/align)*align;const result=[next,next];next+=size;return result;},
 Vir2Phy:a=>a,SetHex(address,hex){writes.push({address,hex:hex.replace(/ /g,'')});}};
const bytes=Buffer.from(input.hex,'hex');
const helpers={asm:native.asm,assertCode(label,address,expected){
 const raw=Buffer.from(expected.replace(/ /g,''),'hex');
 assert(bytes.subarray(address-input.base,address-input.base+raw.length).equals(raw),label);
}};
const source=fs.readFileSync(input.root+'/Scripts/Patches/ItemDescriptionUI.qjs','utf8');
const ui=new Function('Exe','ItemCollectionUI',source.slice(0,source.indexOf('ItemDescriptionUI = function'))+'\nreturn ItemDescriptionNative;')(Exe,{nativeFrameV1:helpers});
const manifest=ui.installLifecycleHooks(helpers,input.entries);
const sourceHooks=ui.installSourceHooks(helpers,input.entries);
console.log(JSON.stringify({writes,manifest,sourceHooks,end:next}));
'''

def install(image,entries,node):
    base=0x8b4000
    args=dict(root=str(ROOT),base=base,hex=image[base-0x400000:0x94fb00-0x400000].hex(),
              next=0x400000+len(image),entries=entries)
    result=subprocess.run([node,'-e',NODE],input=json.dumps(args),text=True,capture_output=True)
    if result.returncode:raise AssertionError(result.stderr)
    output=json.loads(result.stdout);image.extend(bytes(output['end']-0x400000-len(image)))
    for write in output['writes']:
        raw=bytes.fromhex(write['hex']);start=write['address']-0x400000;image[start:start+len(raw)]=raw
    return output['manifest'],output['sourceHooks']

def checks(pe, m):
    from unicorn import UC_HOOK_CODE
    from unicorn.x86_const import (UC_X86_REG_ESP,UC_X86_REG_EIP,UC_X86_REG_EDI,
        UC_X86_REG_EAX,UC_X86_REG_EBX,UC_X86_REG_ECX,UC_X86_REG_EDX,
        UC_X86_REG_ESI,UC_X86_REG_EBP,UC_X86_REG_EFLAGS)
    from verify_item_description_native import VM,WIN,ITEM,STOP
    from verify_item_description_comparison import DualVM,COMP
    from verify_item_description_components import TripleVM,DETAIL

    class NativeOpenVM(TripleVM):
        """Run the three real profiled OnMessage bodies at mocked boundaries."""
        def __init__(self):
            super().__init__(pe,m)
            self.u.mem_map(0,4096)
            self.allocations=[];self.lookup_calls=[];self.gates=[];self.front=[]
            self.stubs.pop(m['original'][37]);self.stubs.pop(m['comparisonOriginal'][37])
            self.stubs.pop(m['componentOriginal'][37])
            self.stub(0xa245c0,8,lambda ecx,args:self.allocations.append((ecx,args)) or self.set_size(ecx,args))
            self.stub(0x6a2a70,0,lambda ecx,args:self.lookup_calls.append(ecx) or 0x5010b000)
            self.stub(0x4dcc30,0,lambda ecx,args:0) # distinguish incoming item; same-item close tested separately
            self.write32(0xfc1830,STOP+0x400)
            self.stub(STOP+0x400,0,lambda ecx,args:int(self.cstring(self.read32(self.u.reg_read(UC_X86_REG_ESP)+4)) or b'0'))
            for address,pop in [(0xd8ebe0,4),(0x6a06b0,4),(0xa47b90,4),(0x88be30,8),
                                (0x6a5f30,0),(0x6a5d70,0),(0x6a5df0,0),(0xc6b1e0,4),
                                (0xdbbbd4,0),(0xa2e770,4)]:self.stub(address,pop,lambda ecx,args:0)
            self.write32(0x125510c,0x50150000);self.write32(0x131f714,0)
            self.stub(0xa75340,0,lambda ecx,args:0x50150000)
            self.stub(0x6a4bc0,0,lambda ecx,args:0x50151000)
            self.u.mem_write(0x50151000,b'knife\0')
            self.stub(0xa39130,4,lambda ecx,args:self.front.append(args[0]) or 0)
            self.stub(0xd59830,4,lambda ecx,args:0)
            self.stub(0x68ea70,0,lambda ecx,args:1)
            def assign(ecx,args):
                value=bytes(self.u.mem_read(args[0],args[1]));assert len(value)<16
                self.u.mem_write(ecx,value.ljust(16,b'\0')+struct.pack('<II',len(value),15));return ecx
            self.stub(0x4f1940,8,assign)
            def concat(ecx,args):
                # Resource string implementation is an engine boundary, not an
                # omitted branch: retain an owned short string through move/dtor.
                destination=self.read32(self.u.reg_read(UC_X86_REG_ESP)+4)
                self.u.mem_write(destination,b'art.bmp\0'.ljust(16,b'\0')+struct.pack('<II',7,15));return destination
            self.stub(0x69d160,0,concat);self.stub(0x4fef00,0,concat)
            for n,window in enumerate([WIN,COMP,DETAIL]):
                child=0x50152000+n*0x1000;table=child+0x200;tree=child+0x400
                self.write32(window+0x214,child);self.write32(window+0x1b4,child);self.write32(child,table)
                self.write32(table+0xd4,STOP+0x420);self.stub(STOP+0x420,4,lambda ecx,args:0)
                self.write32(table+0x10,STOP+0x440);self.stub(STOP+0x440,8,lambda ecx,args:0)
                self.write32(window+0x240,tree)
                for off in [0,4,8]:self.write32(tree+off,tree)
                self.write32(self.read32(window)+38*4,0xa23340)
            forbidden=[(0x8c1d70,0x8c21f2),(0x8c223f,0x8c2284),(0x8c255a,0x8c2a78),(0x8c2b59,0x8c2c58)]
            targets={s['target'] for s in m['lifecycleHooks']['branches'] if s['predicate']=='ItemDescriptionNativeOpen'}
            def track(u,pc,size,_):
                assert not any(lo<=pc<hi for lo,hi in forbidden),f'hidden legacy work executed at {pc:x}'
                if pc in targets:self.gates.append((pc,u.reg_read(UC_X86_REG_EDI)))
            self.u.hook_add(UC_HOOK_CODE,track)

    v=NativeOpenVM();v.open();assert v.s('ready') and len(v.sent)==1 and v.front==[WIN]
    assert [a for a in v.allocations if a[0]==WIN]==[(WIN,[360,560])]
    assert not v.lookup_calls and len(v.gates)==4
    assert v.read32(WIN+0x244)==v.read32(WIN+0x248)==v.read32(WIN+0x1fc)==0
    assert v.cstring(WIN+0x1c4)==b'art.bmp','native illustration path ownership lost'
    v.receive(v.response());v.allocations=[];old=v.response()
    for item in range(1202,1214):
        v.open(itemid=item);assert v.receive(old)==0
        old=v.response();assert v.receive(old)==1 and v.s('ready')
    assert not [a for a in v.allocations if a[0]==WIN],'switch reallocated parent surface'
    assert len(v.gates)==13*4 and not v.lookup_calls
    # A real native main open recursively dispatches the equipped item into the
    # comparison wrapper. Its scope must unwind before the final main-body gate.
    v=NativeOpenVM();v.open();v.receive(v.response());v.allocations=[];v.gates=[]
    equip=0x50154000;v.u.mem_write(equip,bytes(v.u.mem_read(ITEM,0xb8)))
    v.u.mem_write(equip+0x2c,b'2301\0');v.write32(equip+4,9)
    v.stub(0xd59830,4,lambda ecx,args:equip)
    v.stub(0xa39340,4,lambda ecx,args:COMP if args[0]==0xea else 0)
    v.open(itemid=2315)
    assert v.s('ready') and v.c(12) and len(v.sent)==3
    assert len([g for g in v.gates if g[1]==WIN])==len([g for g in v.gates if g[1]==COMP])==4
    assert v.gates[-1]==(0x8c2c58,WIN) and not v.lookup_calls
    assert [a for a in v.allocations if a[0] in (WIN,COMP)]==[(COMP,[360,560])]
    assert v.run('NativeOpen',[WIN],ecx=0)==v.run('NativeOpen',[COMP],ecx=0)==0
    assert v.run('NativeText',ecx=WIN+0xb8)==0x5010b000 and v.lookup_calls==[WIN+0xb8]

    # A card click takes the actual ID82 OnMessage -> base open path through all
    # four optimization gates, while retaining its parent's existing surface.
    card=NativeOpenVM();card.open();card.receive(card.response());card.run('Draw')
    card.allocations=[];card.gates=[];card.click_card()
    assert card.d('ready') and card.d('loading') and card.front[-1]==DETAIL
    assert card.gates==[(address,DETAIL) for address in [0x8c21f2,0x8c2284,0x8c2a78,0x8c2c58]]
    assert not card.lookup_calls and card.cstring(DETAIL+0x1c4)==b'art.bmp'
    assert card.allocations==[(DETAIL,[360,560])]
    card.receive(card.response());card.allocations=[];card.now+=200;card.click_card()
    assert card.d('ready') and not card.d('loading') and not card.allocations
    assert card.run('NativeOpen',[DETAIL],ecx=0)==0

    # Native same-item toggle closes inside OnMessage. Dispatch the real payload
    # destructor from the engine close boundary, without reentering VM.run().
    closed=NativeOpenVM();closed.open();closed.receive(closed.response())
    closed.stub(0x4dcc30,0,lambda ecx,args:1);closed.allocations=[]
    close_address=0xa2e770;closed.stubs.pop(close_address)
    code=b'\x83\x7c\x24\x04\x0c\x75\x0e\x6a\x00\xb9'+struct.pack('<I',WIN)
    code+=b'\xe8'+struct.pack('<i',m['entries']['ItemDescriptionDestroy']-(close_address+len(code)+5))+b'\xc2\x04\x00'
    # The comparison-close branch jumps directly to ret 4.
    code=code[:6]+bytes([len(code)-3-7])+code[7:]
    closed.u.mem_write(close_address,code);closed.u.ctl_remove_cache(close_address,close_address+len(code));sent=len(closed.sent)
    closed.open();assert not closed.s('owner') and not closed.s('ready') and len(closed.sent)==sent
    assert not [a for a in closed.allocations if a[0]==WIN]

    # Unscoped sources use a catalog preview. Disabled/unidentified items retain
    # native work. A small callback records the scoped predicate in x86.
    eligibility=[]
    for mode,options in [('owned',{}),('catalog',dict(scope=0,index=0)),('unidentified',dict(identified=0)),
                         ('unprofiled',dict(scope=0)),('disabled',{}),('small_viewport',{})]:
        t=VM(pe,m)
        if mode=='disabled':t.write32(m['entries']['ItemDescriptionConfig']+59*4,0)
        if mode=='small_viewport':t.write32(t.renderer+0x28,300)
        address=m['original'][37];t.stubs.pop(address)
        # Save ECX, call exact receiver predicate, store EAX, then return.
        code=b'\x51\x51\xe8'+struct.pack('<i',m['entries']['ItemDescriptionNativeOpen']-(address+7))
        code+=b'\xa3'+struct.pack('<I',0x50157000)+b'\x59\xff\x74\x24\x0c\x81\xc1\xb8\x00\x00\x00'
        code+=b'\xe8'+struct.pack('<i',0x6a25f0-(address+len(code)+5))+b'\xc2\x18\x00'
        t.u.mem_write(address,code);t.open(**options)
        expected=int(mode in ('owned','catalog','unprofiled'))
        assert t.read32(0x50157000)==expected,(mode,t.read32(0x50157000))
        eligibility.append(mode)

    # Run the real OnDraw prologue, both emitted gates, native illustration and
    # decorated-title call, and epilogue. The hidden background/body must not run.
    drawn=VM(pe,m);drawn.open();drawn.u.mem_map(0,4096)
    drawn.u.mem_write(0x8b4200,pe.get_data(0x8b4200-0x400000,0x540))
    drawn.u.mem_write(WIN+0x1c4,b'art.bmp\0');drawn.write32(WIN+0x1d4,7);drawn.write32(WIN+0x1d8,15)
    drawn.stub(m['config'][2],24,lambda ecx,args:0)
    titles=[];arts=[]
    drawn.stub(m['entries']['ItemDescriptionTitle'],28,lambda ecx,args:titles.append((ecx,args)) or 0)
    drawn.stub(0xdbbbd4,0,lambda ecx,args:0)
    saved_loader=drawn.stubs[0xa8d4a0];saved_blit=drawn.stubs[0xa1d260]
    def draw_edges(u,pc,size,_):
        assert not 0x8b4237<=pc<0x8b438a and not 0x8b4403<=pc<0x8b4712,f'legacy paint at {pc:x}'
    drawn.u.hook_add(UC_HOOK_CODE,draw_edges)
    # Engine entry ABI differs between the native art overload and scrollbar.
    # Select each mock at the actual instruction that calls that overload.
    def prepare(u,pc,size,data):
        if pc==0x8b43b9:drawn.stubs[0xa8d4a0]=(8,lambda ecx,args:0x50155000)
        if pc==0x8b43be:drawn.stubs[0xa8d4a0]=saved_loader
        if pc==0x8b43c5:drawn.stubs[0xa1d260]=(12,lambda ecx,args:arts.append((ecx,args)) or 0)
        if pc==0x8b43ca:drawn.stubs[0xa1d260]=saved_blit
    drawn.u.hook_add(UC_HOOK_CODE,prepare)
    drawn.run('Draw')
    assert len(titles)==len(arts)==1 and titles[0][1][2]==WIN+0xb8
    surface=drawn.read32(WIN+0x24);assert drawn.read32(surface+0x1c)&1
    drawn.write32(surface+0x1c,0);drawn.write32(WIN+0x1d4,0);drawn.run('Draw')
    assert drawn.read32(surface+0x1c)&1 and len(arts)==1 and len(titles)==2,'missing artwork lost the new surface upload'

    # False predicates replay displaced native instructions and flags exactly,
    # including both sides of the original title JNE. DF and general registers
    # are restored after the payload predicate, not leaked to the caller.
    replay_count=0
    for spec in m['lifecycleHooks']['branches']:
        for zf in [0,1]:
            t=VM(pe,m);t.u.mem_write(WIN+0x114,bytes([zf]));t.u.mem_write(WIN+0x20c,bytes([zf]))
            values={UC_X86_REG_EAX:0x1212,UC_X86_REG_EBX:0x2323,UC_X86_REG_ECX:0x3434,UC_X86_REG_EDX:0x4545,
                    UC_X86_REG_ESI:0x5656,UC_X86_REG_EDI:WIN,UC_X86_REG_EBP:0x5001e000,UC_X86_REG_ESP:0x5001f000}
            for reg,value in values.items():t.u.reg_write(reg,value)
            flags=0x602 | (0x40 if zf else 0);t.u.reg_write(UC_X86_REG_EFLAGS,flags)
            resume=spec['address']+len(bytes.fromhex(spec['original']))
            destination=spec.get('fallTarget',resume) if spec.get('fallTarget') and not zf else resume
            def stop(u,pc,size,_,destination=destination):
                if pc==destination:u.emu_stop()
            t.u.hook_add(UC_HOOK_CODE,stop);t.u.emu_start(spec['address'],STOP,count=10000)
            assert t.u.reg_read(UC_X86_REG_EIP)==destination
            raw=bytes.fromhex(spec['original']);expected=dict(values)
            if raw[:2]==b'\x8b\x8f':expected[UC_X86_REG_ECX]=t.read32(WIN+0x1b0)
            if raw[:2]==b'\x8b\x87':expected[UC_X86_REG_EAX]=t.read32(WIN+0x1b0)
            assert all(t.u.reg_read(reg)==value for reg,value in expected.items())
            if raw[0]==0x80:
                operand=zf;constant=raw[-1]
                assert bool(t.u.reg_read(UC_X86_REG_EFLAGS)&0x40)==(operand==constant)
            else:assert t.u.reg_read(UC_X86_REG_EFLAGS)==flags
            assert t.u.reg_read(UC_X86_REG_EFLAGS)&0x400
            replay_count+=1

    # Returning to original descriptions builds the skipped body exactly once.
    fallback=[]
    for failure in ['timeout','rejected','send_failure','deferred_send_failure']:
        t=VM(pe,m);t.open();t.receive(t.response());t.open(itemid=1202)
        if failure=='timeout':t.now+=4000;t.run('Process')
        elif failure=='rejected':
            data=t.response();struct.pack_into('<I',data,20,1);struct.pack_into('<H',data,38,0);t.receive(data)
        else:
            t.stub(m['packetRefs']['packetCtorA'],0,lambda ecx,args:0)
            if failure=='deferred_send_failure':t.now-=199
            t.open(itemid=1203)
            if failure=='deferred_send_failure':t.now+=200;t.run('Process')
        calls=[a for slot,w,a in t.native_calls if slot==37 and a[1]==24]
        assert calls[-1][3:]==[1,0,0] and calls[-1][2]!=ITEM,'fallback did not preserve native comparison refresh with forced CItem copy'
        assert t.cstring(calls[-1][2]+0x2c)==t.cstring(WIN+0xb8+0x2c)
        assert not t.s('ready') and not t.s('loading') and t.read32(WIN+0x14)==280
        before=len(calls);t.now+=4000;t.run('Process')
        assert len([a for slot,w,a in t.native_calls if slot==37 and a[1]==24])==before
        fallback.append(failure)
    return dict(passed=True,real_native_opens=17,real_nested_comparison_opens=1,real_component_opens=2,stock_branch_replays=replay_count,
                eligibility=eligibility,same_item_close_resurrections=0,
                repeated_switch_parent_allocations=0,hidden_description_lookups=0,fallbacks=fallback,
                checks=['actual native open/switch bodies skip hidden options, text parsing and intermediate resizes',
                        'native CItem/artwork ownership, front ordering and recursively dispatched comparison retained',
                        'exact receiver scopes unwind; unrelated description lookup remains native',
                        'real native draw calls illustration and decorated title once; skips hidden background/body',
                        'all displaced stock branches replay with original flags, registers and stack',
                        'native same-item destruction cannot reactivate the freed description or send another request',
                        'owned/catalog eligibility is scoped; unprofiled sources use catalog; unidentified/disabled/small views remain native',
                        'timeout/rejected/failed-send rebuild original body once with independent CItem strings'])
