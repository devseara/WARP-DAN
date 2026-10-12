"""Asset contract checks, including generalized ACT scales and pixel formats."""
from pathlib import Path
import json,struct,tempfile,unittest
import hd_job_ui_assets as asset_module
from PIL import Image
from hd_job_ui_assets import act_layers,convert_pair,read_spr,write_spr,read_spec,digest
ROOT=Path(__file__).resolve().parents[1]

def make_act(layers,version=5):
    header=b'AC'+bytes((version,2))+struct.pack('<H',2)+bytes(10)
    frame=bytes(range(32))+struct.pack('<I',len(layers))
    for index,sx,sy,kind in layers:
        frame+=struct.pack('<4iI2f2i',7,-19,index,1,0x7f123456,sx,sy,0,kind)
        if version==5:frame+=struct.pack('<2i',101,77)
    frame+=struct.pack('<ii',0,1)+b'ANCR'+struct.pack('<3i',9,-41,7)
    return header+struct.pack('<I',1)+frame+struct.pack('<I',1)+frame+struct.pack('<I',1)+b'step.wav'.ljust(40,b'\0')+struct.pack('<2f',3.5,7.25)

class AssetChecks(unittest.TestCase):
    def test_arbitrary_sizes_and_per_frame_variants(self):
        im=Image.new('RGBA',(101,77),(200,60,20,255))
        spr=write_spr([im],0,b'')
        scales=[(.25,.25),(.5,.5),(.33,.71),(1.5,.4),(2.1,1.25),(.25,.25)]
        act=make_act([(0,x,y,1) for x,y in scales])
        output,new,stats=convert_pair(spr,act);images,ni,_=read_spr(output)
        original,tail=act_layers(act);converted,new_tail=act_layers(new)
        self.assertEqual(len(images),5);self.assertEqual(stats['extra_variants'],4)
        self.assertEqual(act[tail:],new[new_tail:])
        for a,b in zip(original,converted):
            self.assertEqual((a['x'],a['y'],a['color'],a['mirror'],a['rotation']),(b['x'],b['y'],b['color'],b['mirror'],b['rotation']))
            self.assertEqual((b['sx'],b['sy']),(1,1))
            expected=(max(1,int(101*a['sx']+.5)),max(1,int(77*a['sy']+.5)))
            self.assertEqual(images[b['index']].size,expected)
        self.assertEqual(converted[0]['index'],converted[5]['index'])
    def test_premultiplied_transparency_and_abgr_storage(self):
        image=Image.new('RGBA',(40,40),(0,0,255,0))
        for y in range(10,30):
            for x in range(10,30):image.putpixel((x,y),(255,0,0,255))
        spr=write_spr([image],0,b'');self.assertEqual(spr[12:16],bytes((0,255,0,0)))
        ui,_,_=convert_pair(spr,make_act([(0,.25,.25,1)]))
        result=read_spr(ui)[0][0]
        self.assertTrue(any(0<a<255 for r,g,b,a in result.getdata()))
        self.assertTrue(all(b==0 and g==0 for r,g,b,a in result.getdata() if a))
    def test_indexed_palette_and_type_partition(self):
        palette=b''.join(bytes((i,255-i,0,255)) for i in range(256))
        indexed=Image.frombytes('P',(40,40),bytes([0,31,91,251])*400)
        indexed.putpalette([v for i in range(256) for v in palette[i*4:i*4+3]]);indexed.info['transparency']=0
        rgba=Image.new('RGBA',(20,20),(1,2,3,255))
        spr=write_spr([indexed,rgba],1,palette)
        act=make_act([(0,.5,.5,0),(0,.25,.25,0),(0,.5,.5,1)])
        ui,new,_=convert_pair(spr,act);images,ni,pal=read_spr(ui)
        self.assertEqual(pal,palette);self.assertEqual(ni,2);self.assertEqual(len(images),3)
        layers,_=act_layers(new);self.assertEqual([x['index'] for x in layers[:3]],[0,1,0])
        self.assertEqual([x['kind'] for x in layers[:3]],[0,0,1])
        self.assertEqual(set(images[0].convert('RGBA').getchannel('A').getdata())- {0,255},set())
    def test_invalid_scaling_and_indices_fail_closed(self):
        spr=write_spr([Image.new('RGBA',(8,8))],0,b'')
        for scale in (0,-1,float('nan'),float('inf'),65):
            with self.assertRaises(ValueError):convert_pair(spr,make_act([(0,scale,1,1)]))
        with self.assertRaises(ValueError):convert_pair(spr,make_act([(1,.5,.5,1)]))
    def test_discovery_native_override_shadows_scaled_archive(self):
        from package_hd_job_ui_grf import write_grf
        stem='인간족/몸통/남/검사_남'
        scaled=make_act([(0,.25,.25,1)]);native=make_act([(0,1,1,1)])
        spr=write_spr([Image.new('RGBA',(8,8))],0,b'')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);loose=root/'sprite';path=loose/(stem+'.act')
            path.parent.mkdir(parents=True);path.write_bytes(native);path.with_suffix('.spr').write_bytes(spr)
            archive=root/'source.grf'
            write_grf({'data/sprite/'+stem+'.act':scaled,'data/sprite/'+stem+'.spr':spr},archive)
            with self.assertRaisesRegex(ValueError,'No scaled'):
                asset_module.discover([loose],[archive],[])
    def test_discovery_resolves_each_extension_by_priority(self):
        from package_hd_job_ui_grf import write_grf
        stem='도람족/몸통/남/임의직업_남';key='data/sprite/'+stem
        hd=write_spr([Image.new('RGBA',(24,36),(40,120,200,255))],0,b'')
        native=write_spr([Image.new('RGBA',(8,12),(40,120,200,255))],0,b'')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);higher=root/'higher.grf';lower=root/'lower.grf';stock=root/'stock.grf'
            write_grf({key+'.act':make_act([(0,1/3,1/3,1)])},higher)
            write_grf({key+'.spr':hd,key+'.act':make_act([(0,1,1,1)])},lower)
            write_grf({key+'.spr':native,key+'.act':make_act([(0,1,1,1)])},stock)
            config=asset_module.discover([],[higher,lower],[stock])
            self.assertEqual(len(config['pairs']),1)
            row=config['pairs'][0]
            self.assertEqual(Path(row['source']['act']['grf']),higher)
            self.assertEqual(Path(row['source']['spr']['grf']),lower)
            result=asset_module.build(config,root/'out')['pairs'][0]
            image=read_spr((root/'out'/('preview/'+row['id']+'.spr')).read_bytes())[0][0]
            self.assertEqual(image.size,(8,12));self.assertFalse(result['fallback_baked'])
    def test_scaled_stock_fallback_and_duplicate_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            spr=write_spr([Image.new('RGBA',(20,20),(200,60,20,255))],0,b'')
            for name,scale in [('hd',.5),('stock',1.1)]:
                (root/(name+'.spr')).write_bytes(spr)
                (root/(name+'.act')).write_bytes(make_act([(0,scale,scale,1)]))
            config={'pairs':[{'id':name,'resource_stem':'jobs/'+name,'source':{'path':str(root/'hd')},'fallback':{'path':str(root/'stock')}} for name in ('one','two')]}
            result=asset_module.build(config,root/'out')['pairs']
            self.assertEqual(result[0]['preview'],result[1]['preview'])
            self.assertEqual(len(list((root/'out').rglob('*.spr'))),2)
            stock_spr=(root/'out/stock/one.spr').read_bytes();stock_act=(root/'out/stock/one.act').read_bytes()
            self.assertEqual(read_spr(stock_spr)[0][0].size,(22,22))
            self.assertTrue(result[0]['fallback_baked'])
            self.assertTrue(all((l['sx'],l['sy'])==(1,1) for l in act_layers(stock_act)[0]))

    def test_real_supplied_pairs_preserve_metadata_and_world_sources(self):
        path=ROOT/'Outputs/hd-job-ui/build-config.json'
        if not path.exists():self.skipTest('Local source configuration unavailable')
        for row in json.loads(path.read_text())['pairs']:
            original={e:read_spec(row['source'],e) for e in ('.spr','.act')}
            _,act,_=convert_pair(original['.spr'],original['.act'])
            self.assertTrue(all(l['index']<0 or (l['sx'],l['sy'])==(1,1) for l in act_layers(act)[0]))
            before,tail=act_layers(original['.act']);after,new_tail=act_layers(act)
            self.assertEqual(len(before),len(after));self.assertEqual(act[new_tail:],original['.act'][tail:])
            for a,b in zip(before,after):
                self.assertEqual((a['action'],a['frame'],a['x'],a['y']),(b['action'],b['frame'],b['x'],b['y']))
            for e in original:self.assertEqual(digest(original[e]),digest(read_spec(row['source'],e)))

if __name__=='__main__':unittest.main(verbosity=2)