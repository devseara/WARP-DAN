"""Save the verified review pairs and one minimal, reproducible work bundle."""
import json
from pathlib import Path
import zipfile
from correct_clan_neck_registration import ROOT, WORK, AUDIT, load, save, sha

RELEASE=ROOT/'Assets/ClanBodySkins/releases/neck-motion-correction-v1'
RECORD=ROOT/'Inputs/ClanBodySkins/records/clan-neck-motion-correction.json'


def write_zip(path,members):
    expected={}
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,source in sorted(members.items()):
            raw=source if isinstance(source,bytes) else source.read_bytes()
            archive.writestr(name,raw);expected[name]=sha(raw)
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist())==set(expected)
        for name,digest in expected.items():assert sha(archive.read(name))==digest
    return dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path.read_bytes()),bytes=path.stat().st_size,members=len(expected))


def main():
    record=load(RECORD);summary=load(WORK/'build-summary.json');review=load(WORK/'review-verification.json');recovery=load(WORK/'recovery-verification.json')
    assert len(summary['files'])==24 and summary['frame_uses']==5472
    assert sum(len(p['new_fragment_flags']) for p in review['pairs'])==0
    assert load(WORK/'bow-grip-verification.json')['frames']==144
    assert load(WORK/'stature-verification.json')['status']=='passed'
    assert load(WORK/'browser-verification.json')['status']=='passed'
    refresh=load(WORK/'browser-refresh-verification.json');assert refresh['status']=='passed'
    assert refresh['review_data_sha256']==sha((WORK/'review-data.json').read_bytes())
    assert recovery['status']=='passed' and len(recovery['files_verified'])==24
    expected={r['path']:r['sha256'] for r in recovery['files_verified']}
    targets={(r['job'],r['sex'],Path(r['source']).suffix):r['entry'] for r in load(AUDIT/'inventory.json')['resources']}
    public={};files=[]
    for row in summary['files']:
        source=WORK/row['path'];digest=sha(source.read_bytes());assert digest==row['sha256']==expected[row['path']]
        name=row['job']+'/'+source.name;public[name]=source
        files.append(dict(**row,archive_path=name,target_grf_entry=targets[row['job'],row['sex'],source.suffix]))
    manifest=dict(status='review_candidate',user_accepted=False,installed=False,files=files)
    public['manifest.json']=(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode('utf8')
    public['docs/clan-body-skins.md']=ROOT/'docs/clan-body-skins.md'
    RELEASE.mkdir(parents=True,exist_ok=True)
    distribution=write_zip(RELEASE/'angel-first-jobs-neck-correction-v1-spr-act.zip',public)
    print('Verified SPR/ACT ZIP:',distribution['bytes'],'bytes',flush=True)
    bundle={}
    for pin in recovery['inputs']:
        source=ROOT/pin['path'];assert sha(source.read_bytes())==pin['sha256'],pin['path'];bundle[pin['path']]=source
    for row in summary['files']:
        source=WORK/row['path'];bundle[source.relative_to(ROOT).as_posix()]=source
    supporting=[ROOT/'docs/clan-body-skins.md',RECORD,Path(__file__),WORK/'build-summary.json',WORK/'source-pins.json',WORK/'review-verification.json',WORK/'bow-grip-verification.json',WORK/'stature-verification.json',WORK/'browser-verification.json',WORK/'browser-refresh-verification.json',WORK/'recovery-verification.json',WORK/'review-data.json',WORK/'review.html']
    supporting+=list(WORK.glob('*/*-verification.json'))
    for source in supporting:bundle[source.relative_to(ROOT).as_posix()]=source
    recovery_zip=write_zip(RELEASE/'current-work.zip',bundle)
    record['archives']=dict(spr_act=distribution,recovery=recovery_zip)
    record['validation_files']=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p.read_bytes())) for p in supporting if p.suffix=='.json' and p!=RECORD]
    save(RECORD,record);save(WORK/'delivery.json',dict(status='ready_for_visual_review',user_accepted=False,installed=False,archives=record['archives'],files=files))
    save(RELEASE/'manifest.json',manifest)
    print('Verified recovery ZIP:',recovery_zip['bytes'],'bytes;',recovery_zip['members'],'members',flush=True)


if __name__=='__main__':main()
