"""Compile real server layouts and copy expressions for scoped name/title checks.
Tests NPC and non-NPC script titles, mob database loading, packet serialization,
and the historical 128-byte write into a 24-byte buffer. No server is launched.
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

def read(name):
    return (a.server / name).read_text(encoding='utf-8')

def unique(pattern, text):
    hits = re.findall(pattern, text)
    assert len(hits) == 1, (pattern, hits)
    return hits[0]

strlib = read('src/common/strlib.cpp')
copy = strlib[strlib.index('char* safestrncpy('):strlib.index("/// doesn't crash on null pointer")]
status_copy = unique(r'safestrncpy\(md->ud\.title, md->db->title\.c_str\(\), [^;]+;', read('src/map/status.cpp'))
script = read('src/map/script.cpp').split('BUILDIN_FUNC(setunittitle)', 1)[1].split('clif_name_area(bl);', 1)[0]
script_copy = unique(r'const size_t title_capacity = [^;]+;\s+safestrncpy\(ud->title, [^;]+;', script)
script_copy = script_copy.replace('script_getstr(st, 3)', 'value')
resize = unique(r'title\.resize\(ENTITY_TITLE_LENGTH - 1\);', read('src/map/mob.cpp'))
clif = read('src/map/clif.cpp')
assert 'safestrncpy(packet.title, ud->title, NAME_LENGTH);' in clif
assert 'safestrncpy( packet.title_name, ud->title, NAME_LENGTH );' in clif
cpp = r'''
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <string>
#include <map/mob.hpp>
#include <map/npc.hpp>
#include <map/storage.hpp>
#include <map/packets.hpp>
COPY_BODY
struct TitleDb { std::string title; };
struct Fixture { unit_data ud{}; std::array<unsigned char,128> adjacent; TitleDb* db; };
void load_mob_title(TitleDb& db, std::string title) { RESIZE_BODY db.title=title; }
void initialize_mob(Fixture* md) { STATUS_COPY }
void script_title(unit_data* ud, block_list* bl, const char* value) { SCRIPT_COPY }
static_assert(sizeof(guild_log_entry::name) == CHARACTER_NAME_LENGTH);
static_assert(sizeof(npc_data::name) == 128 && sizeof(mob_data::name) == 128);
static_assert(sizeof(unit_data::title) == NPC_TITLE_LENGTH && NPC_TITLE_LENGTH == 128);
static_assert(ENTITY_TITLE_LENGTH == 24 && ENTITY_TITLE_LENGTH <= sizeof(unit_data::title));
static_assert(sizeof(PACKET_ZC_ACK_REQNAMEALL_NPC::title) == 128);
static_assert(sizeof(PACKET_ZC_EXT_NAME::title_name) == 128);
static_assert(sizeof(PACKET_ZC_ACK_REQNAMEALL_NPC) == 266);
static_assert(offsetof(PACKET_ZC_ACK_REQNAMEALL_NPC,title) == 138);
int main() {
    int failures=0, cases=0;
    const std::string smelter="<Responsible for smelting products>";
    const std::vector<std::string> values={"", "T", std::string(23,'T'), std::string(24,'T'),
        smelter, std::string(127,'T'), std::string(128,'T'), std::string(300,'T')};
    for (const auto& value : values) {
        for (auto type : {BL_NPC,BL_MOB,BL_PC,BL_PET,BL_HOM,BL_MER,BL_ELEM}) {
            TitleDb db; Fixture f; f.db=&db; block_list bl{}; bl.type=type;
            f.ud.group_id=0x11223344;
            f.ud.shadow_scar_timer={0x12345678,12}; f.ud.hatEffects={23,45};
            f.ud.pending_skill_timing_delay=0x55667788; f.adjacent.fill(0xA5);
            auto* begin=reinterpret_cast<unsigned char*>(&f);
            auto* end=f.adjacent.data()+f.adjacent.size();
            std::vector<unsigned char> before(begin,end);
            const size_t title=f.ud.title-reinterpret_cast<char*>(&f);
            script_title(&f.ud,&bl,value.c_str());
            size_t changed=0;
            for(size_t i=0;i<before.size();++i)
                if ((i<title || i>=title+sizeof(f.ud.title)) && begin[i]!=before[i]) ++changed;
            const auto expected=value.substr(0,type==BL_NPC?127:23);
            bool pass=std::string(f.ud.title)==expected && changed==0;
            PACKET_ZC_ACK_REQNAMEALL_NPC packet{};
            PACKET_ZC_EXT_NAME extended{};
            safestrncpy(packet.title, f.ud.title, NAME_LENGTH);
            safestrncpy(extended.title_name, f.ud.title, NAME_LENGTH);
            pass &= std::string(packet.title)==expected && std::string(extended.title_name)==expected;
            // Restore vector representations before destruction if a future regression corrupts them.
            std::memcpy(begin,before.data(),before.size());
            if (!pass) std::printf("FAIL script type=%d length=%zu adjacent=%zu\n",int(type),value.size(),changed);
            failures += !pass; ++cases;
        }
        TitleDb db; Fixture f; f.db=&db; f.adjacent.fill(0xA5); f.ud.group_id=1234;
        load_mob_title(db,value);
        initialize_mob(&f);
        bool pass=std::string(f.ud.title)==value.substr(0,23) && f.ud.group_id==1234 &&
            std::all_of(f.adjacent.begin(),f.adjacent.end(),[](auto b){return b==0xA5;});
        failures += !pass; ++cases;
        // Archived real-layout evidence covers the old mob layout. This negative
        // control keeps its 24-byte destination and checks safestrncpy padding.
        struct Legacy { char title[24]; std::array<unsigned char,104> after; } legacy;
        legacy.after.fill(0xA5);
        safestrncpy(legacy.title,value.c_str(),NAME_LENGTH);
        pass=std::all_of(legacy.after.begin(),legacy.after.end(),[](auto b){return b!=0xA5;});
        failures += !pass; ++cases;
    }
    std::printf("%s %d cases: NPC titles 127, other titles 23, mob loading, packet fields, historical overwrite\n",failures?"FAIL":"PASS",cases);
    std::printf("Smelter: full %zu-byte title retained in NPC storage and both packet formats\n",smelter.size());
    return failures?1:0;
}
'''
for key,value in [('COPY_BODY',copy),('STATUS_COPY',status_copy),('SCRIPT_COPY',script_copy),('RESIZE_BODY',resize)]:
    cpp = cpp.replace(key,value)
source = a.output/'name_buffers.cpp'
source.write_text(cpp,encoding='utf-8')
vc=Path('C:/Program Files/Microsoft Visual Studio/18/Community/VC/Auxiliary/Build/vcvars64.bat')
incs=['src','3rdparty/rapidyaml/src','3rdparty/rapidyaml/ext/c4core/src','3rdparty/pcre/include','3rdparty/mysql/include','3rdparty/libconfig']
cmd=a.output/'compile.cmd'
cmd.write_text('@echo off\ncall "'+str(vc)+'" > nul\nif errorlevel 1 exit /b %errorlevel%\ncl /nologo /EHsc /std:c++17 /O2 /MD '+' '.join('/I"'+str(a.server/p)+'"' for p in incs)+' /Fo"'+str(a.output/'name_buffers.obj')+'" /Fe"'+str(a.output/'name_buffers.exe')+'" "'+str(source)+'"\nexit /b %errorlevel%\n',encoding='utf-8')
build=subprocess.run(['cmd','/c',str(cmd)],capture_output=True,text=True)
(a.output/'compile.log').write_text(build.stdout+build.stderr,encoding='utf-8')
if build.returncode:
    print(build.stdout+build.stderr)
    raise SystemExit(build.returncode)
run=subprocess.run([str(a.output/'name_buffers.exe')],capture_output=True,text=True)
print(run.stdout+run.stderr)
report={'passed':run.returncode==0,'mob_copy':status_copy,'script_copy':script_copy,
    'output':run.stdout+run.stderr,'server':str(a.server),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
(a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
raise SystemExit(run.returncode)
