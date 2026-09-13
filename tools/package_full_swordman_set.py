"""Package the complete body-art review with reopened-file verification."""
import json,hashlib,zipfile,re
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from prepare_full_swordman_art import WORK,WALK,sha,native_context
from sprite_formats import read_spr,read_act
from review_full_swordman_set import joined

ROOT=Path(__file__).resolve().parents[1]

def main():
    reports=[];files=[];alpha=[]
    for sex in ('male','female'):
        report=json.loads((WORK/f'{sex}-verification.json').read_text(encoding='utf8'))
        assert report['actions']==104 and report['frame_uses']==456 and report['new_nonwalk_frame_uses']==392
        assert not report['stock_fallback_frames'] and not report['missing_sheets'] and not report['detached_artwork_flags']
        assert report['accepted_walk_pixels_and_placement_identical'] and report['native_metadata_preserved'] and report['independent_decoder_match']
        for entry in report['files']:
            path=WORK/entry['path'];assert sha(path)==entry['sha256'];files.append(dict(path=path.relative_to(WORK).as_posix(),sha256=sha(path),bytes=path.stat().st_size))
        images=read_spr((WORK/f'assets/{sex}-angel-complete-v9.spr').read_bytes())
        actual_green=actual_magenta=dirty_transparent=inherited_magenta_candidate=0
        act=read_act((WORK/f'assets/{sex}-angel-complete-v9.act').read_bytes())
        accepted_indices={l.index for fs in act.actions[8:16] for f in fs for l in f.layers if l.index>=0}
        for image_index,im in enumerate(images):
            a=np.asarray(im);rgb=a[:,:,:3].astype(int);opaque=a[:,:,3]>0
            actual_green+=int(((rgb[:,:,1]>95)&(rgb[:,:,1]-rgb[:,:,0]>48)&(rgb[:,:,1]-rgb[:,:,2]>48)&opaque).sum())
            pink_count=int(((rgb[:,:,0]>160)&(rgb[:,:,2]>145)&(rgb[:,:,1]<120)&opaque).sum())
            if image_index in accepted_indices:inherited_magenta_candidate+=pink_count
            else:actual_magenta+=pink_count
            dirty_transparent+=int(((a[:,:,:3]!=0).any(axis=2)&~opaque).sum())
            assert set(np.unique(a[:,:,3])).issubset({0,255})
        # The broad magenta predicate matches one accepted male A8 F7 pixel:
        # RGBA [162,116,154,255]. It is retained with the byte-exact walk.
        assert inherited_magenta_candidate==(1 if sex=='male' else 0)
        assert actual_green==actual_magenta==dirty_transparent==0,(sex,actual_green,actual_magenta,dirty_transparent)
        alpha.append(dict(sex=sex,indexed_images=0,rgba_images=len(images),explicit_green_residue=actual_green,new_art_magenta_residue=actual_magenta,protected_walk_color_candidates=inherited_magenta_candidate,transparent_rgb_zero=True,binary_alpha=True))
        reports.append(report)
    approval=json.loads((WALK/'user-acceptance.json').read_text(encoding='utf8'))
    for f in approval['files']:assert sha(WALK/f['path'])==f['sha256']
    coverage=json.loads((WORK/'review-coverage.json').read_text(encoding='utf8'));assert all(c['actions']==104 and c['frame_uses']==456 for c in coverage['coverage'])
    html=(WORK/'full-action-review.html').read_text(encoding='utf8')
    image_references=re.findall(r'review/images/[^"\s]+\.png',html);assert len(image_references)==2736
    referenced=set(image_references);assert len(referenced)==coverage['unique_review_pngs']
    assert all((WORK/p).is_file() for p in referenced)
    labels=['Idle','Walk','Sit','Pickup','Attack 1','Attack 2','Hit','Action 7','Death','Standby','Attack 3','Attack 4','Cast']
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15);board=Image.new('RGB',(13*180,600),'#283746');draw=ImageDraw.Draw(board)
    for si,sex in enumerate(('male','female')):
        pair=(read_spr((WORK/f'assets/{sex}-angel-complete-v9.spr').read_bytes()),read_act((WORK/f'assets/{sex}-angel-complete-v9.act').read_bytes()))
        for group,label in enumerate(labels):
            fi={1:2,3:1,4:2,5:2,10:5,11:3,12:3}.get(group,0);ai=group*8;fi=min(fi,len(pair[1].actions[ai])-1)
            im=joined(sex,ai,fi,pair).resize((300,300),Image.Resampling.NEAREST);x=group*180;y=si*300
            board.paste(im,(x-60,y+15),im);draw.text((x+5,y+4),f'{sex} / {label}',font=font,fill='white')
    board.save(WORK/'complete-action-overview.png')
    status=dict(status='Complete male/female body artwork exported for user visual review',actions_per_sex=104,frames_per_sex=456,body_artwork_complete=True,user_full_set_acceptance=False,installed_game_modified=False,accepted_walking_recovered_exactly=True,accepted_walking_preserved_in_complete_export=True,native_metadata_preserved=True,rgba_key_color_audit=alpha,files=files,review=coverage)
    (WORK/'full-set-verification.json').write_text(json.dumps(status,indent=2),encoding='utf8')
    archive=WORK.parent/'Swordman-complete-v9-SPR-ACT-review.zip'
    included=[WORK/f['path'] for f in files]+[WORK/n for n in ['full-action-review.html','complete-action-overview.png','full-set-verification.json','male-verification.json','female-verification.json','review-coverage.json','registration-adjustments.json']]+[WORK/p for p in sorted(referenced)]+sorted((WORK/'review').glob('*-comparison.png'))
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in included:z.write(p,p.relative_to(WORK).as_posix())
        z.write(ROOT/'docs/clan-body-skins.md','clan-body-skins.md')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for f in files:assert hashlib.sha256(z.read(f['path'])).hexdigest()==f['sha256']
    status['archive']=dict(path=archive.name,sha256=sha(archive),bytes=archive.stat().st_size,entries=len(included)+1)
    (WORK.parent/'delivery.json').write_text(json.dumps(status,indent=2),encoding='utf8')
    print(json.dumps(status['archive']))

if __name__=='__main__':main()
