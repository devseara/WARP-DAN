"""Offline evidence probe for the 2026-09-11 precommit name-scope audit.
Extracts current serializer/scanner statements. Never contacts a running server.
The 24-byte build is a width control; it is not a build of the historical server.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--server', type=Path, default=Path('../BanquetOfHeroes'))
ap.add_argument('--output', type=Path, required=True)
a = ap.parse_args()
a.server, a.output = a.server.resolve(), a.output.resolve()
a.output.mkdir(parents=True, exist_ok=True)

def read(p):
    return (a.server / p).read_text(encoding='utf-8')

def function(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]

sources = {p: read(p) for p in ['src/common/mmo.hpp', 'src/common/strlib.cpp',
    'src/map/chrif.cpp', 'src/char/char_mapif.cpp', 'src/map/npc.cpp', 'src/map/map.hpp']}
copy = function(sources['src/common/strlib.cpp'], 'char* safestrncpy(')
request = function(sources['src/map/chrif.cpp'], 'int32 chrif_req_login_operation(')
char_parser = function(sources['src/char/char_mapif.cpp'], 'int32 chmapif_parse_fwlog_changestatus(')
ack = re.findall(r'WFIFOHEAD\(fd,34\);.*?WFIFOSET\(fd,34\);', char_parser, re.S)
assert len(ack) == 1
scanner = re.findall(r'sscanf\(w4, "%127\[\^,\].*?, &ai\)', sources['src/map/npc.cpp'])
assert len(scanner) == 1
cpp = r'''
#define _CRT_SECURE_NO_WARNINGS
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <string>
#include <common/mmo.hpp>
#include <common/socket.hpp>
#include <map/map.hpp>
static_assert(CHARACTER_NAME_LENGTH == 128 && EVENT_NAME_LENGTH == 77);
alignas(8) unsigned char fifo[512];
int32 char_fd = 1;
size_t reserved, sent;
#undef WFIFOHEAD
#undef WFIFOSET
#undef WFIFOW
#undef WFIFOL
#undef WFIFOCP
#define chrif_check(x) do {} while(0)
#define WFIFOHEAD(fd,n) (reserved=(n))
#define WFIFOSET(fd,n) (sent=(n))
#define WFIFOW(fd,n) (*reinterpret_cast<uint16*>(fifo+(n)))
#define WFIFOL(fd,n) (*reinterpret_cast<uint32*>(fifo+(n)))
#define WFIFOCP(fd,n) (reinterpret_cast<char*>(fifo+(n)))
COPY
#undef NAME_LENGTH
#define NAME_LENGTH 24
namespace width24 {
REQUEST
void ack(int32 fd, int32 aid, const char* name, int operation, int result) { ACK }
}
#undef NAME_LENGTH
#define NAME_LENGTH CHARACTER_NAME_LENGTH
namespace current {
REQUEST
void ack(int32 fd, int32 aid, const char* name, int operation, int result) { ACK }
}
void inspect(const char* phase, const char* route, size_t len) {
    const auto changed=std::count_if(fifo+reserved,fifo+sizeof(fifo),[](auto b){return b!=0xA5;});
    std::printf("%s,%s,%zu,%zu,%zu,%td\n",phase,route,len,reserved,sent,changed);
}
int main() {
    std::puts("phase,route,input_bytes,reserved_bytes,sent_bytes,changed_bytes_after_record");
    for (size_t len : {0,1,23,24,127}) {
        const std::string name(len,'N');
        for (int phase : {0,1}) {
            std::memset(fifo,0xA5,sizeof(fifo)); reserved=sent=0;
            if(phase) current::chrif_req_login_operation(123,name.c_str(),CHRIF_OP_LOGIN_BAN,3600,4,0);
            else width24::chrif_req_login_operation(123,name.c_str(),CHRIF_OP_LOGIN_BAN,3600,4,0);
            inspect(phase?"current128":"control24","2b0e",len);
            std::memset(fifo,0xA5,sizeof(fifo)); reserved=sent=0;
            if(phase) current::ack(1,123,name.c_str(),CHRIF_OP_LOGIN_BAN,0);
            else width24::ack(1,123,name.c_str(),CHRIF_OP_LOGIN_BAN,0);
            inspect(phase?"current128":"control24","2b0f",len);
        }
    }
    for(size_t length : {23,76,77,78}) {
        spawn_data mob{};
        std::memset(mob.filepath,0xA5,sizeof(mob.filepath));
        char sprite[NAME_LENGTH]{};
        int32 num=0, delay=0, size=0, ai=0;
        const std::string input="1002,1,0,0,"+std::string(length,'E')+",0,0";
        const char* w4=input.c_str();
        int fields=SCANNER;
        std::printf("npc_event,%zu,%zu,%d,%u\n",length,sizeof(mob.eventname),fields,
            static_cast<unsigned char>(mob.filepath[0]));
    }
}
'''
for key, value in [('COPY', copy), ('REQUEST', request), ('ACK', ack[0]), ('SCANNER', scanner[0])]:
    cpp = cpp.replace(key, value)
source = a.output / 'probe.cpp'
source.write_text(cpp, encoding='utf-8')
vc = Path('C:/Program Files/Microsoft Visual Studio/18/Community/VC/Auxiliary/Build/vcvars64.bat')
incs = ['src','3rdparty/rapidyaml/src','3rdparty/rapidyaml/ext/c4core/src','3rdparty/pcre/include','3rdparty/mysql/include','3rdparty/libconfig']
cmd = a.output / 'compile.cmd'
cmd.write_text('@echo off\ncall "'+str(vc)+'" > nul\nif errorlevel 1 exit /b %errorlevel%\ncl /nologo /EHsc /std:c++17 /Od /MD '+' '.join('/I"'+str(a.server/p)+'"' for p in incs)+' /Fo"'+str(a.output/'probe.obj')+'" /Fe"'+str(a.output/'probe.exe')+'" "'+str(source)+'"\nexit /b %errorlevel%\n', encoding='utf-8')
build = subprocess.run(['cmd','/c',str(cmd)],capture_output=True,text=True)
(a.output/'compile.log').write_text(build.stdout+build.stderr,encoding='utf-8')
if build.returncode:
    print(build.stdout+build.stderr)
    raise SystemExit(build.returncode)
run = subprocess.run([str(a.output/'probe.exe')],capture_output=True,text=True)
print(run.stdout+run.stderr)
rows = [x.split(',') for x in run.stdout.splitlines()]
serializers = [dict(zip(['phase','route','input_bytes','reserved_bytes','sent_bytes','changed_bytes_after_record'], r)) for r in rows if r[0] in ('current128','control24')]
events = [dict(zip(['route','input_bytes','capacity','scanned_fields','next_field_first_byte'],r)) for r in rows if r[0]=='npc_event']
report = {'probe_ran':run.returncode==0, 'ready_to_commit':False,
    'limits':'Extracted serializer statements with an oversized canary FIFO. This proves writes outside the record, not a live heap corruption or a specific crash cause.',
    'serializers':serializers, 'npc_events':events,
    'source_sha256':{p:hashlib.sha256((a.server/p).read_bytes()).hexdigest() for p in sources}}
(a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
assert len(serializers)==20 and len(events)==4
assert all(int(r['changed_bytes_after_record']) == (0 if r['phase']=='control24' else (90 if r['route']=='2b0e' else 100)) for r in serializers)
assert [int(r['next_field_first_byte']) for r in events] == [165,165,0,0]
raise SystemExit(run.returncode)
