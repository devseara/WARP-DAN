"""Check alphabetical include and file-entry lists in the requested server files."""
import argparse,re,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def key(s):return s.replace('\\','/').casefold()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--server',type=Path,default=ROOT.parent/'BanquetOfHeroes');args=ap.parse_args()
    license_header='// Copyright (c) rAthena Dev Teams - Licensed under GNU GPL\n// For more information, see LICENCE in the main folder\n'
    for name in ['src/common/world_environment_wire.hpp','src/map/world_environment.cpp','src/map/world_environment.hpp',
                 'src/map/world_environment_profiles.cpp','src/map/world_environment_profiles.hpp','tools/test_world_environment_profiles.cpp',
                 'tools/test_world_environment.cpp','tools/test_world_environment_rain_schedule.cpp',
                 'tools/test_world_environment_storm.cpp','tools/test_world_environment_auto_storm.cpp',
                 'tools/world_environment_test_boundary.hpp']:
        assert (args.server/name).read_text(encoding='utf8').startswith(license_header),(name,'missing rAthena license header')
    print('PASS rAthena license headers: weather module, wire and test boundaries')
    for name in ['clif.cpp','pc.hpp','pincode_ui.hpp','world_environment.cpp','world_environment_profiles.cpp','world_environment_profiles.hpp']:
        text=(args.server/'src/map'/name).read_text(encoding='utf-8-sig')
        for block in re.findall(r'(?:^#include [<"][^\n]+\n)+',text,re.M):
            paths=[key(p) for p in re.findall(r'^#include [<"]([^>"]+)',block,re.M)]
            assert paths==sorted(paths),(name,paths)
        print('PASS alphabetical C++ includes:',name)
    for name in ['map-server.vcxproj','map-server-generator.vcxproj',
                 'map-server.vcxproj.filters','map-server-generator.vcxproj.filters']:
        ns={'m':'http://schemas.microsoft.com/developer/msbuild/2003'}
        document=ET.parse(args.server/'src/map'/name)
        for group in document.findall('m:ItemGroup',ns):
            for tag in ['ClInclude','ClCompile','Filter','None','ResourceCompile','CustomBuild']:
                paths=[key(e.get('Include')) for e in group.findall('m:'+tag,ns) if e.get('Include')]
                assert paths==sorted(paths),(name,tag,[(a,b) for a,b in zip(paths,paths[1:]) if a>b][:8])
        if name.endswith('.filters'):
            for tag,path in [('ClInclude','..\\common\\world_environment_wire.hpp'),
                             ('ClInclude','world_environment.hpp'),('ClCompile','world_environment.cpp'),
                             ('ClInclude','world_environment_profiles.hpp'),('ClCompile','world_environment_profiles.cpp')]:
                entries=[e for group in document.findall('m:ItemGroup',ns) for e in group.findall('m:'+tag,ns)
                         if key(e.get('Include',''))==key(path)]
                assert len(entries)==1,(name,tag,path,'missing or duplicate weather filter entry')
                assert entries[0].find('m:Filter',ns).text==('Header Files' if tag=='ClInclude' else 'Source Files')
        print('PASS alphabetical project/filter entries:',name)
if __name__=='__main__':main()
