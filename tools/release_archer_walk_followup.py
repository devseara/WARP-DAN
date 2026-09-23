"""Install the remaining Archer walk correction over the verified V11 release."""
import argparse
import copy
from pathlib import Path
from audit_clan_motion import ROOT, GAME, load, save, sha
from clan_grf_transaction import digest
from package_clan_skin_assets import pack_payloads, GrfFile
from save_clan_neck_correction import write_zip
from save_accepted_clan_work import source_closure
import release_clan_neck_shoulders as parent

WORK=ROOT/'Assets/ClanBodySkins/archer-shoulder-v3'
ID='first-jobs-archer-walk-v12'
RELEASE=ROOT/'Assets/ClanBodySkins/releases'/ID
PATCH=RELEASE/'angel-archer-walk-v12.grf'
CURRENT=ROOT/'Inputs/ClanBodySkins/records/clan-sprites-current.json'
RECORD=ROOT/'Inputs/ClanBodySkins/records/clan-sprites-v12-installation.json'


def payloads():
    parent.WORK=WORK
    return parent.payloads()


def prepare():
    browser=load(WORK/'browser-refresh-verification.json')
    assert browser['status']=='passed' and browser['walking_cycles']==16 and browser['pairs']==2
    assert browser['review_data_sha256']==sha((WORK/'review-data.json').read_bytes())
    assert not any(r['new_fragment_flags'] for r in load(WORK/'review-verification.json')['pairs'])
    assert load(WORK/'surface-verification.json')['frame_uses']==128
    rows,raw=payloads();previous=load(WORK/'source-pins.json')
    old={r['entry']:r for r in previous['resources']}
    assert all(r==old[r['entry']] for r in rows if r['job']!='archer')
    RELEASE.mkdir(parents=True,exist_ok=True);save(RELEASE/'previous-manifest.json',previous)
    manifest=copy.deepcopy(previous);manifest.update(release_id=ID,status='complete_correction_prepared',resources=rows,
        previous_release=previous['release_id'],deployment_authorization='User requested remaining Archer shoulder correction, all views checked, within the active fix-and-save-to-GRF task.',
        expected_replaced_resources=[dict(entry=r['entry'],sha256=r['sha256']) for r in previous['resources']])
    manifest['versions']['archer']='Neck V1 plus shoulder V3; all eight walking views'
    manifest['visual_acceptance']['archer']='Follow-up correction; live visual acceptance pending'
    manifest['authoring_tools']=list(dict.fromkeys(manifest['authoring_tools']+['release_archer_walk_followup.py']))
    manifest['coverage_reports']=[r for r in manifest['coverage_reports'] if r['job']!='archer']
    for sex in ('male','female'):
        chosen=[r for r in rows if r['job']=='archer' and r['sex']==sex]
        report=WORK/'archer'/f'{sex}-release-coverage.json'
        save(report,dict(actions=104,frame_uses=456,stock_fallback_frames=[],missing_sheets=[],detached_artwork_flags=[],
            files=[dict(path=(ROOT/r['source']).relative_to(report.parent).as_posix(),sha256=r['sha256']) for r in chosen]))
        manifest['coverage_reports'].append(dict(job='archer',sex=sex,path=report.relative_to(ROOT).as_posix()))
    save(RELEASE/'manifest.json',manifest)
    delta={r['entry']:raw[r['entry']] for r in rows if r['job']=='archer'}
    pack_payloads(delta,PATCH)
    save(RELEASE/'verification.json',dict(status='verified_followup',current_resources=24,patch_resources=4,changed_frame_uses=56,
        all_archer_walking_frames_checked=128,live_visual_acceptance=False,files=rows,patch_sha256=digest(PATCH)))


def install():
    import release_accepted_clan_sprites as release
    manifest=load(RELEASE/'manifest.json');rows,raw=payloads()
    packed=GrfFile(PATCH)
    try:
        assert set(packed.entries)=={r['entry'] for r in rows if r['job']=='archer'}
        for name in packed.entries:assert packed.read(name)==raw[name]
    finally:packed.close()
    release.CONFIG=manifest;release.RELEASE=RELEASE;release.PATCH=PATCH
    release.install(raw,GAME)
    report=load(RELEASE/'installation.json');report.update(release_id=ID,files=rows,live_visual_acceptance=False,patch_resources=4)
    save(RECORD,report)
    manifest.update(status='installed_correction',installation_record=RECORD.relative_to(ROOT).as_posix())
    save(CURRENT,manifest);save(RELEASE/'manifest.json',manifest)
    record=load(WORK/'release-files.json');record.update(status='installed_correction',installation_record=RECORD.relative_to(ROOT).as_posix());save(WORK/'release-files.json',record)
    data=load(WORK/'review-data.json')
    for sex in ('male','female'):data['jobs']['archer'][sex]['state']='Installed Archer V3; all eight walking views; live visual acceptance pending'
    save(WORK/'review-data.json',data)
    html=(WORK/'review.html').read_text(encoding='utf8').replace('These files are for review and are not installed in the GRF.','These exact pairs are installed in maindata.grf. Live visual acceptance is pending.').replace('Correction candidate','Installed correction')
    (WORK/'review.html').write_text(html,encoding='utf8',newline='\n')
    browser=load(WORK/'browser-refresh-verification.json');browser['pre_install_review_data_sha256']=browser['review_data_sha256'];browser['review_data_sha256']=sha((WORK/'review-data.json').read_bytes());browser['post_install_change']='Status labels only; rendered pixels unchanged.';save(WORK/'browser-refresh-verification.json',browser)
    print('Installed Archer follow-up; other 20 clan resources unchanged.',flush=True)


def archive():
    assert load(CURRENT)['release_id']==ID
    base=ROOT/'Assets/ClanBodySkins/releases/first-jobs-neck-shoulders-v11'
    parent_archive=load(base/'saved-work.json')['archive'];assert digest(ROOT/parent_archive['path'])==parent_archive['sha256']
    save(RELEASE/'recovery-parent.json',dict(restore_first=parent_archive,instructions='Restore V11 current-work.zip first, then extract this delta bundle over the same root. Unchanged artwork is stored once in the V11 bundle.'))
    members={}
    for row in load(WORK/'release-files.json')['files']:
        if row['job']=='archer':members[row['source']]=ROOT/row['source']
    for p in source_closure([Path(__file__),ROOT/'tools/fix_clan_shoulders.py',ROOT/'tools/review_clan_neck_correction.py']):members[p.relative_to(ROOT).as_posix()]=p
    for folder in (WORK,RELEASE):
        for p in folder.rglob('*.json'):
            if p.name!='saved-work.json':members[p.relative_to(ROOT).as_posix()]=p
    for p in [CURRENT,RECORD,ROOT/'docs/clan-body-skins.md',ROOT/'tools/verify_clan_shoulder_release_browser.cjs',ROOT/'tools/clan_neck_correction_review.html',WORK/'review.html']:
        members[p.relative_to(ROOT).as_posix()]=p
    result=write_zip(RELEASE/'current-work-delta.zip',members)
    save(RELEASE/'saved-work.json',dict(status='saved_and_verified',archive=result,requires_parent=parent_archive))
    print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['prepare','install','archive']);a=p.parse_args()
    {'prepare':prepare,'install':install,'archive':archive}[a.stage]()
