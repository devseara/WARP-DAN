"""Run emitted x86 UI bridges with mocked VFS/resource APIs, not a live client."""
from pathlib import Path
import json,struct,unittest
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX,UC_X86_REG_EBX,UC_X86_REG_ECX,UC_X86_REG_EDX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP,UC_X86_REG_ESP
ROOT=Path(__file__).resolve().parents[1]

class NativeFixture:
    def __init__(self,available=()):
        self.u=Uc(UC_ARCH_X86,UC_MODE_32);p=pefile.PE(str(ROOT/'Outputs/hd-job-ui/native/preview.exe'))
        self.base=p.OPTIONAL_HEADER.ImageBase
        self.u.mem_map(self.base,(p.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);self.u.mem_write(self.base,p.get_memory_mapped_image())
        self.exports={s.name.decode():self.base+s.address for s in p.DIRECTORY_ENTRY_EXPORT.symbols}
        self.u.mem_map(0x400000,0x900000);self.u.mem_map(0x30000000,0x20000)
        self.next=0x30000000;self.stack=0x3001e000;self.stop=0x3001f000
        self.available=set(available);self.opens=[];self.loads=[];self.frees=[];self.file=None;self.closed=0;self.destroyed=0
        self.pairs=json.loads((ROOT/'Assets/HDJobUI/manifest.json').read_text())['pairs']
        table=self.alloc(len(self.pairs)*12)
        for i,row in enumerate(self.pairs):
            self.write(table+i*12,self.string(bytes.fromhex(row['resource_hex'])),self.string(row['preview'].encode()),self.string(row['fallback'].encode()))
        self.write(self.exports['HDJobConfig'],1,len(self.pairs),table,0x800100,0x800200)
        self.apis={0x573750:16,0x573060:0,0x4f08f0:0,0x4f1940:8,0xa8d4a0:4,0xa8d9f0:24,0x800100:4,0x800200:24}
        for addr,pop in self.apis.items():self.u.mem_write(addr,b'\xc2'+struct.pack('<H',pop))
        self.u.hook_add(UC_HOOK_CODE,self.hook)
    def alloc(self,size):
        p=self.next;self.next+=(size+15)&~15;assert self.next<0x3000c000;return p
    def string(self,s):
        p=self.alloc(len(s)+1);self.u.mem_write(p,s+b'\0');return p
    def write(self,p,*v):self.u.mem_write(p,struct.pack('<'+'I'*len(v),*(x&0xffffffff for x in v)))
    def words(self,p,n=1):return struct.unpack('<'+'I'*n,self.u.mem_read(p,n*4))
    def cstr(self,p):
        out=bytearray()
        for i in range(384):
            c=self.u.mem_read(p+i,1)[0]
            if c==0:return bytes(out)
            out.append(c)
        raise AssertionError('Unbounded native string')
    def native_string(self,p):
        size,cap=self.words(p+16,2);address=p if cap<16 else self.words(p)[0]
        value=self.cstr(address);assert len(value)==size;return value,address,cap
    def hook(self,u,addr,size,unused):
        if addr not in self.apis:return
        sp=u.reg_read(UC_X86_REG_ESP);receiver=u.reg_read(UC_X86_REG_ECX)
        if addr==0x573750:
            path,mode,flag,zero=self.words(sp+4,4);assert (mode,flag,zero)==(0,1,0)
            assert self.words(receiver,5)==(0xfd3074,0xffffffff,0,0,0)
            assert self.words(receiver+36,2)==(0,15)
            self.file=receiver;key=self.cstr(path);self.opens.append(key)
            u.reg_write(UC_X86_REG_EAX,int(key in self.available))
        elif addr==0x573060:
            assert receiver==self.file;self.closed+=1
        elif addr==0x4f08f0:
            assert receiver==self.file+20;self.destroyed+=1
        elif addr==0x4f1940:
            path,n=self.words(sp+4,2);value=self.cstr(path);assert len(value)==n
            old,ptr,cap=self.native_string(receiver)
            if cap>=16:self.frees.append(ptr)
            newptr=self.string(value);self.write(receiver,newptr,0,0,0,n,n)
            u.reg_write(UC_X86_REG_EAX,receiver)
        else:
            assert receiver==0x12345678,'Lost resource-manager this pointer'
            if addr in (0xa8d9f0,0x800200):
                key,ptr,cap=self.native_string(sp+4)
                if cap>=16:self.frees.append(ptr)
            else:key=self.cstr(self.words(sp+4)[0])
            self.loads.append((addr,key));u.reg_write(UC_X86_REG_EAX,0x22223333)
    def run(self,name,args,pop):
        saved=[UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP]
        for i,r in enumerate(saved):self.u.reg_write(r,0x11110000+i*0x100)
        self.write(self.stack,self.stop,*args);self.u.reg_write(UC_X86_REG_ESP,self.stack)
        self.u.reg_write(UC_X86_REG_ECX,0x12345678);self.u.reg_write(UC_X86_REG_EDX,0x87654321)
        self.u.emu_start(self.exports[name],self.stop,count=100000)
        assert self.u.reg_read(UC_X86_REG_ESP)==self.stack+4+pop,'Native stack imbalance'
        for i,r in enumerate(saved):assert self.u.reg_read(r)==0x11110000+i*0x100,'Callee-saved register changed'
        return self.u.reg_read(UC_X86_REG_EAX)
    def load(self,path,string=False):
        if string:
            if len(path)<16:raw=path.ljust(16,b'\0')+struct.pack('<II',len(path),15)
            else:raw=struct.pack('<6I',self.string(path),0,0,0,len(path),len(path))
            result=self.run('@HDJobStringHook@32',struct.unpack('<6I',raw),24)
        else:result=self.run('@HDJobResourceHook@12',[self.string(path)],4)
        assert result==0x22223333
        assert self.closed==self.destroyed==len(self.opens),'CFile lifecycle mismatch'
        return self.loads[-1]

class BridgeChecks(unittest.TestCase):
    def test_complete_pair_and_cache_on_both_abis(self):
        rows=json.loads((ROOT/'Assets/HDJobUI/manifest.json').read_text())['pairs']
        for row in rows:
            available=[('sprite/'+row['preview']+e).replace('/','\\').encode() for e in ('.spr','.act')]
            for string in (False,True):
                f=NativeFixture(available)
                for ext in (b'.spr',b'.act',b'.spr'):
                    result=f.load(bytes.fromhex(row['resource_hex']).replace(b'/',b'\\')+ext,string)
                    self.assertEqual(result,((0xa8d9f0 if string else 0xa8d4a0),(row['preview'].replace('/','\\')).encode()+ext))
                self.assertEqual(len(f.opens),2)
                if string:self.assertEqual(len(set(f.frees)),6) # old argument + replacement for each load
    def test_missing_either_member_selects_stock_for_both(self):
        row=json.loads((ROOT/'Assets/HDJobUI/manifest.json').read_text())['pairs'][-1]
        for missing in ('.spr','.act','both'):
            available=[('sprite/'+row['preview']+e).replace('/','\\').encode() for e in ('.spr','.act') if missing not in (e,'both')]
            f=NativeFixture(available)
            for string,ext in ((False,b'.act'),(True,b'.spr')):
                _,path=f.load(bytes.fromhex(row['resource_hex'])+ext,string)
                self.assertEqual(path,row['fallback'].replace('/','\\').encode()+ext)
    def test_unmatched_resources_delegate_unchanged(self):
        f=NativeFixture()
        for path in (b'x.spr',b'world_effects/unrelated.act',b'clan_skins/2/unlisted.spr',b'foo.bmp'):
            for string in (False,True):
                self.assertEqual(f.load(path,string),((0x800200 if string else 0x800100),path))
        self.assertFalse(f.opens)
    def test_prefix_case_and_dbcs_boundaries(self):
        f=NativeFixture();row=f.pairs[-1]
        # Uppercase only ASCII characters; never change CP949 trail bytes.
        raw=bytes.fromhex(row['resource_hex'])
        for prefix in (b'data\\sprite\\',b'sprite\\',b'data\\',b''):
            _,path=f.load(prefix+raw+b'.SPR')
            self.assertEqual(path,prefix+row['fallback'].replace('/','\\').encode()+b'.spr')
        f=NativeFixture();source=f.string(b'\x81A/test')
        table=f.words(f.exports['HDJobConfig']+8)[0];f.write(table,source)
        _,path=f.load(b'\x81A/TEST.SPR')
        self.assertEqual(path,f.pairs[0]['fallback'].replace('/','\\').encode()+b'.spr')

if __name__=='__main__':unittest.main(verbosity=2)