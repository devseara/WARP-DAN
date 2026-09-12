"""Generate native-size UI pairs without changing HD world resources.

Supports the profiled ACT 2.4/2.5 and SPR 2.0/2.1/2.2 formats. Indexed
sprites retain their palette and indices' meaning (including dye support).
Premultiplied-alpha Lanczos is followed by original-palette quantization;
indexed edges necessarily retain binary transparency. Truecolor SPR pixels
are bottom-up ABGR on disk, NOT BGRA. No offsets/anchors are rescaled.
"""
from __future__ import annotations
import argparse, hashlib, json, math, struct
from collections import Counter
from pathlib import Path
from PIL import Image
from dual_weapon_formats.grf_reader import GrfFile


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def act_layers(raw):
    if raw[:2] != b'AC' or raw[2:4] not in (b'\x04\x02', b'\x05\x02'):
        raise ValueError('Expected ACT 2.4 or 2.5; other versions need profiling')
    version = raw[2]
    actions = struct.unpack_from('<H', raw, 4)[0]
    pos, layers = 16, []
    for ai in range(actions):
        frames, = struct.unpack_from('<I', raw, pos); pos += 4
        if frames > 10000: raise ValueError('Unbounded frame count')
        for fi in range(frames):
            pos += 32
            count, = struct.unpack_from('<I', raw, pos); pos += 4
            if count > 4096: raise ValueError('Unbounded layer count')
            for li in range(count):
                x,y,index,mirror,color,sx,sy,rotation,kind = struct.unpack_from('<4iI2f2i',raw,pos)
                layers.append(dict(pos=pos, action=ai, frame=fi, layer=li, x=x,y=y,index=index,mirror=mirror,color=color,sx=sx,sy=sy,rotation=rotation,kind=kind))
                pos += 44 if version == 5 else 36
            pos += 4  # frame sound id
            anchors, = struct.unpack_from('<I',raw,pos); pos += 4
            if anchors > 4096: raise ValueError('Unbounded anchor count')
            pos += anchors*16
    sounds, = struct.unpack_from('<I',raw,pos)
    end = pos+4+sounds*40+actions*4
    if end != len(raw): raise ValueError('ACT sound/timing tail does not consume file exactly')
    return layers, pos


def read_spr(raw):
    if raw[:2] != b'SP' or raw[2:4] not in (b'\x00\x02',b'\x01\x02',b'\x02\x02'):
        raise ValueError('Expected SPR 2.0/2.1/2.2')
    minor=raw[2]; ni,nt=struct.unpack_from('<HH',raw,4); pos=8; images=[]
    palette=raw[-1024:] if ni else b''
    for index in range(ni+nt):
        w,h=struct.unpack_from('<HH',raw,pos);pos+=4
        if not w or not h: raise ValueError('Empty sprite image')
        if index < ni:
            if minor:
                fmt='<H' if minor==1 else '<I';length=struct.unpack_from(fmt,raw,pos)[0];pos+=struct.calcsize(fmt)
                compressed=raw[pos:pos+length];pos+=length;decoded=bytearray();k=0
                while k<len(compressed):
                    v=compressed[k];k+=1
                    if v:decoded.append(v)
                    else:
                        if k==len(compressed):raise ValueError('Truncated zero run')
                        decoded.extend(bytes(compressed[k]));k+=1
                if len(decoded)!=w*h:raise ValueError('Invalid indexed image length')
                pixels=bytes(decoded)
            else:pixels=raw[pos:pos+w*h];pos+=w*h
            im=Image.frombytes('P',(w,h),pixels)
            im.putpalette([c for i in range(256) for c in palette[i*4:i*4+3]])
            im.info['transparency']=0
        else:
            size=w*h*4;pixels=raw[pos:pos+size];pos+=size
            im=Image.frombytes('RGBA',(w,h),pixels,'raw','ABGR',0,-1)
        images.append(im)
    if pos+len(palette)!=len(raw):raise ValueError('SPR image/palette lengths do not consume file exactly')
    return images,ni,palette


def write_spr(images,ni,palette):
    # Uncompressed 2.0 indexed images avoid RLE's 16-bit compressed-size cap.
    out=bytearray(b'SP\x00\x02'+struct.pack('<HH',ni,len(images)-ni))
    for i,im in enumerate(images):
        out+=struct.pack('<HH',*im.size)
        out+=im.tobytes() if i<ni else im.tobytes('raw','ABGR',0,-1)
    return bytes(out)+palette


def palette_image(rgba,palette):
    # Never quantize opaque pixels to reserved transparent index zero.
    reference=Image.new('P',(1,1))
    rgb=[tuple(palette[i*4:i*4+3]) for i in range(256)]
    reference.putpalette([v for color in rgb[1:]+[rgb[1]] for v in color])
    quant=rgba.convert('RGB').quantize(palette=reference,dither=Image.Dither.NONE)
    alpha=rgba.getchannel('A').tobytes()
    indices=bytes(((v+1) if v<255 else 1) if a>=128 else 0 for v,a in zip(quant.tobytes(),alpha))
    result=Image.frombytes('P',rgba.size,indices)
    result.putpalette([v for color in rgb for v in color]);result.info['transparency']=0
    return result


def convert_pair(spr,act):
    images,ni,palette=read_spr(spr);layers,tail=act_layers(act)
    live=[l for l in layers if l['index']>=0]
    if not live:raise ValueError('No visible image references')
    scale_counts=Counter((l['sx'],l['sy']) for l in live)
    for sx,sy in scale_counts:
        if not all(math.isfinite(v) and 0<v<=64 for v in (sx,sy)):
            raise ValueError('Visible ACT layers require finite positive scales <=64')
    default_scale=scale_counts.most_common(1)[0][0]
    requests=[{} for _ in images]
    def dimensions(im,sx,sy):
        # UI blits operate in integer pixels. Round each logical dimension,
        # without requiring integral HD multiples or changing file offsets.
        w=max(1,math.floor(im.width*sx+0.5));h=max(1,math.floor(im.height*sy+0.5))
        if w>4096 or h>4096:raise ValueError('Logical image exceeds 4096 pixels')
        return w,h
    for layer in live:
        kind,index=layer['kind'],layer['index']
        if kind not in (0,1):raise ValueError('Unknown ACT sprite type')
        absolute=index+(ni if kind else 0)
        if not 0<=absolute<len(images) or (absolute<ni)!=(kind==0):
            raise ValueError('ACT image index outside SPR type')
        layer['absolute']=absolute
        layer['size']=dimensions(images[absolute],layer['sx'],layer['sy'])
        requests[absolute][layer['size']]=None
    for im,variants in zip(images,requests):
        if not variants:variants[dimensions(im,*default_scale)]=None
    if sum(w*h for variants in requests for w,h in variants)>64*1024*1024:
        raise ValueError('Converted sprite exceeds 64 million pixels')
    converted=[];mapping={};out_counts=[]
    for kind,start,end in ((0,0,ni),(1,ni,len(images))):
        # Keep the first variant at the original relative index. Append only
        # additional sizes; remap the referring layer, never animation frames.
        work=[(i,next(iter(requests[i]))) for i in range(start,end)]
        work += [(i,size) for i in range(start,end) for size in list(requests[i])[1:]]
        if len(work)>65535:raise ValueError('SPR type exceeds 65535 image variants')
        out_counts.append(len(work))
        for relative,(absolute,size) in enumerate(work):
            im=images[absolute]
            if im.size==size:
                result_image=im.copy() # Identity preserves palette indices exactly.
            else:
                rgba=im.convert('RGBA').convert('RGBa').resize(size,Image.Resampling.LANCZOS).convert('RGBA')
                result_image=palette_image(rgba,palette) if kind==0 else rgba
            converted.append(result_image);mapping[absolute,size]=relative
    result=bytearray(act);changed=set()
    for layer in live:
        p=layer['pos'];index=mapping[layer['absolute'],layer['size']]
        struct.pack_into('<i',result,p+8,index);changed.update(range(p+8,p+12))
        struct.pack_into('<2f',result,p+20,1,1);changed.update(range(p+20,p+28))
        if act[2]==5:
            struct.pack_into('<2i',result,p+36,*layer['size']);changed.update(range(p+36,p+44))
    # Only image references, baked scales and ACT 2.5 dimensions may change.
    # X/Y stay logical, including negative coordinates. All frame headers,
    # anchors, color, mirror, rotation, sounds and timing remain byte-identical.
    assert all(a==b or i in changed for i,(a,b) in enumerate(zip(act,result)))
    assert result[tail:]==act[tail:]
    multiplier=None;scale=None
    if len(scale_counts)==1:
        sx,sy=next(iter(scale_counts))
        if sx==sy:
            scale=sx
            if abs(round(1/sx)*sx-1)<1e-6:multiplier=round(1/sx)
    stats=dict(multiplier=multiplier,scale=scale,scales=[dict(x=x,y=y,layers=n) for (x,y),n in scale_counts.items()],
               source_images=len(images),images=len(converted),extra_variants=len(converted)-len(images),
               indexed=out_counts[0],layers=len(live),actions=struct.unpack_from('<H',act,4)[0],tail_sha256=digest(act[tail:]))
    return write_spr(converted,out_counts[0],palette),bytes(result),stats


class ResourceReader:
    """Keep archive tables open for one build, then release every handle."""
    def __init__(self):self.archives={}
    def __enter__(self):return self
    def __exit__(self,*unused):
        for archive in self.archives.values():archive.close()
    def archive(self,path):
        path=Path(path).resolve()
        if path not in self.archives:self.archives[path]=GrfFile(path)
        return self.archives[path]
    def read(self,spec,ext):
        if ext[1:] in spec:return self.read(spec[ext[1:]],ext)
        if 'grf' not in spec:return Path(spec['path']+ext).read_bytes()
        raw=self.archive(spec['grf']).read(spec['stem'].replace('\\','/').lower()+ext)
        if raw is None:raise FileNotFoundError(spec['stem']+ext)
        return raw


def read_spec(spec,ext):
    with ResourceReader() as resources:return resources.read(spec,ext)


def build(config,output):
    with ResourceReader() as resources:return _build(config,output,resources)


def _build(config,output,resources):
    output=output.resolve();output.mkdir(parents=True,exist_ok=True)
    records=[];shared={};converted_pairs={}
    def converted(spr,act):
        key=(digest(spr),digest(act))
        if key not in converted_pairs:converted_pairs[key]=convert_pair(spr,act)
        return converted_pairs[key]
    if not 1<=len(config['pairs'])<=2048:raise ValueError('Expected 1..2048 asset pairs')
    ids=[r['id'] for r in config['pairs']]
    stems=[r['resource_stem'].replace('\\','/').lower() for r in config['pairs']]
    if len(set(ids))!=len(ids) or len(set(stems))!=len(stems):raise ValueError('Duplicate asset ids/resource stems')
    for row in config['pairs']:
        name=row['id']
        if len(name)>120 or not name.isascii() or not name.replace('_','').isalnum():raise ValueError('Expected simple ASCII asset id')
        source_spr,source_act=(resources.read(row['source'],ext) for ext in ('.spr','.act'))
        ui_spr,ui_act,stats=converted(source_spr,source_act)
        stock_spr,stock_act=(resources.read(row['fallback'],ext) for ext in ('.spr','.act'))
        stock_layers,_=act_layers(stock_act)
        stock_baked=any(l['index']>=0 and (l['sx']!=1 or l['sy']!=1) for l in stock_layers)
        if stock_baked:stock_spr,stock_act,_=converted(stock_spr,stock_act)
        stock_layers,_=act_layers(stock_act); stock_images,stock_indexed,_=read_spr(stock_spr)
        if not any(l['index']>=0 for l in stock_layers):raise ValueError('Fallback has no visible images')
        for l in stock_layers:
            if l['index']<0:continue
            available=stock_indexed if l['kind']==0 else len(stock_images)-stock_indexed
            if l['kind'] not in (0,1) or l['index']>=available:raise ValueError('Fallback ACT index outside SPR type')
        if any(l['index']>=0 and (l['sx']!=1 or l['sy']!=1) for l in stock_layers):raise ValueError('Fallback ACT must be native scale 1')
        signature=tuple(digest(raw) for raw in (ui_spr,ui_act,stock_spr,stock_act))
        asset_name=shared.setdefault(signature,name)
        files={f'preview/{asset_name}.spr':ui_spr,f'preview/{asset_name}.act':ui_act,f'stock/{asset_name}.spr':stock_spr,f'stock/{asset_name}.act':stock_act}
        for relative,data in files.items():
            target=output/relative;target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists() or target.read_bytes()!=data:target.write_bytes(data)
        incoming=row['resource_stem'].replace('\\','/').removeprefix('data/').removeprefix('sprite/').lower()
        encoded=incoming.encode('cp949')
        if len(encoded)+17>=384 or '\0' in incoming or any(part in ('','..','.') for part in incoming.split('/')):
            raise ValueError('Resource path exceeds native routing bounds or contains invalid components')
        record=dict(id=name,resource_stem=incoming,resource_hex=encoded.hex(),preview=f'hd_job_ui/preview/{asset_name}',fallback=f'hd_job_ui/stock/{asset_name}',fallback_baked=stock_baked,**stats,
                    source_sha256={'spr':digest(source_spr),'act':digest(source_act)},files={k:digest(v) for k,v in files.items()},stock_first_size=stock_images[0].size)
        records.append(record)
        print(json.dumps({k:record[k] for k in ('id','multiplier','images','indexed','layers','actions')}),flush=True)
    manifest={'version':1,'build_date':20250716,'pairs':records}
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')
    return manifest


def discover(sprite_roots,source_grfs,stock_grfs):
    with ResourceReader() as resources:return _discover(sprite_roots,source_grfs,stock_grfs,resources)


def _discover(sprite_roots,source_grfs,stock_grfs,resources):
    """Resolve each extension by priority; bake scaled bodies from any job.

    Loose roots precede source GRFs, and the first matching file wins. Pass
    only GRFs when the client uses archive-first loading. A separate stock
    archive chain provides fallback artwork, including native ACT scaling.
    """
    def canonical(stem):
        return stem.replace('\\','/').removeprefix('data/').removeprefix('sprite/').lower()
    def is_body(stem):
        return '/몸통/' in stem and '/preview/' not in stem and not stem.startswith('hd_job_ui/')
    def files_from_grfs(paths,files):
        for path in paths:
            archive=resources.archive(path)
            for key in sorted(archive.entries):
                if not key.endswith(('.spr','.act')):continue
                stem=canonical(key[:-4])
                if is_body(stem):files.setdefault((stem,key[-3:]),{'grf':str(Path(path).resolve()),'stem':key[:-4]})
    sources={}
    for root in sprite_roots:
        root=root.resolve()
        for path in sorted(root.rglob('*')):
            if not path.is_file() or path.suffix.lower() not in ('.spr','.act'):continue
            stem=path.relative_to(root).with_suffix('').as_posix()
            try:
                if all(ord(c)<=255 for c in stem):stem=stem.encode('latin1').decode('cp949')
            except (UnicodeEncodeError,UnicodeDecodeError):pass
            stem=canonical(stem)
            if is_body(stem):sources.setdefault((stem,path.suffix[1:].lower()),{'path':str(path.with_suffix(''))})
    files_from_grfs(source_grfs,sources)
    stock={};files_from_grfs(stock_grfs,stock)
    pairs=[];unpaired=[]
    for stem in sorted({stem for stem,ext in sources if ext=='act'}):
        if (stem,'spr') not in sources:
            unpaired.append(stem);continue
        act_spec=sources[stem,'act']
        try:layers,_=act_layers(resources.read(act_spec,'.act'))
        except (ValueError,struct.error) as error:raise ValueError('Invalid body ACT '+stem+': '+str(error)) from error
        if not any(l['index']>=0 and (l['sx']!=1 or l['sy']!=1) for l in layers):continue
        parts=stem.split('/');logical='/'.join(parts[parts.index('몸통')-1:])
        if any((logical,ext) not in stock for ext in ('spr','act')):
            raise ValueError('No complete stock fallback for '+stem)
        source={ext:sources[stem,ext] for ext in ('spr','act')}
        fallback={ext:stock[logical,ext] for ext in ('spr','act')}
        pairs.append({'id':'job_'+digest(stem.encode('cp949'))[:16],'resource_stem':stem,'source':source,'fallback':fallback})
    if not pairs:raise ValueError('No scaled body SPR/ACT pairs found')
    return {'pairs':pairs,'unpaired_act_resources':unpaired}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config',type=Path,help='Explicit source/fallback map; otherwise discover scaled bodies')
    ap.add_argument('--sprite-root',type=Path,action='append',default=[])
    ap.add_argument('--source-grf',type=Path,action='append',default=[])
    ap.add_argument('--stock-grf',type=Path,action='append',default=[])
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--write-config',type=Path,help='Save the resolved per-extension resource map for reproducible rebuilds')
    a=ap.parse_args()
    if a.config and (a.sprite_root or a.source_grf or a.stock_grf):ap.error('Use --config or discovery inputs, not both')
    config=json.loads(a.config.read_text(encoding='utf-8')) if a.config else discover(a.sprite_root,a.source_grf,a.stock_grf)
    if a.write_config:
        a.write_config.parent.mkdir(parents=True,exist_ok=True)
        a.write_config.write_text(json.dumps(config,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')
    build(config,a.output)

if __name__=='__main__':main()
