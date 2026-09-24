"""Save and install the user-requested September 24 clan correction.

Deployment authorization is distinct from live visual acceptance. Preserve the
previous manifest and archive transaction evidence; never label this build as
user visually accepted merely because installation was requested.
"""
import argparse
import copy
import json
from pathlib import Path
from audit_clan_motion import ROOT, GAME, load, save, sha
from package_clan_skin_assets import pack_payloads, GrfFile
from clan_grf_transaction import digest
from save_clan_neck_correction import write_zip
from save_accepted_clan_work import source_closure, active_authoring_tools, RETIREMENT_RECORD
from sprite_formats import read_spr, read_act
from review_original_job_directions import native_context

WORK=ROOT/'Assets/ClanBodySkins/shoulder-motion-v2'
NECK=ROOT/'Assets/ClanBodySkins/neck-motion-correction-v1'
RELEASE_ID='first-jobs-neck-shoulders-v11'
RELEASE=ROOT/'Assets/ClanBodySkins/releases'/RELEASE_ID
PATCH=RELEASE/f'angel-{RELEASE_ID}.grf'
CURRENT=ROOT/'Inputs/ClanBodySkins/records/clan-sprites-current.json'
RECORD=ROOT/'Inputs/ClanBodySkins/records/clan-sprites-v11-installation.json'


def payloads():
    rows=load(WORK/'release-files.json')['files'];result={}
    for r in rows:
        raw=(ROOT/r['source']).read_bytes();assert sha(raw)==r['sha256']
        result[r['entry']]=raw
    assert len(result)==24
    for r in rows:
        if not r['entry'].endswith('.spr'):continue
        images=read_spr(result[r['entry']]);act=read_act(result[r['entry'][:-4]+'.act'])
        native=native_context(r['job'],r['sex'])[2]
        assert len(act.actions)==104 and sum(map(len,act.actions))==456 and act.speeds==native.speeds
        for ai,frames in enumerate(act.actions):
            for fi,f in enumerate(frames):
                n=native.actions[ai][fi]
                assert (f.anchors,f.ranges,f.sound)==(n.anchors,n.ranges,n.sound)
                assert len(f.layers)==1
                l=f.layers[0];assert (l.sx,l.sy,l.angle,l.kind)==(.25,.25,0,1) and 0<=l.index<len(images)
    return rows,result


def prepare():
    review=load(WORK/'review-verification.json')
    assert review['frame_uses']==5472 and not any(r['new_fragment_flags'] for r in review['pairs'])
    browser=load(WORK/'browser-verification.json')
    assert browser['status']=='passed' and browser['walking_cycles']==96
    assert browser['review_data_sha256']==sha((WORK/'review-data.json').read_bytes())
    rows,raw=payloads();RELEASE.mkdir(parents=True,exist_ok=True)
    previous=load(CURRENT)
    if not (RELEASE/'previous-manifest.json').exists():save(RELEASE/'previous-manifest.json',previous)
    else:previous=load(RELEASE/'previous-manifest.json')
    manifest=copy.deepcopy(previous)
    manifest.update(release_id=RELEASE_ID,status='complete_correction_prepared',date='2026-09-24',resources=rows,
        visual_acceptance={j:'Installation requested by user; live visual acceptance pending' for j in sorted({r['job'] for r in rows})},
        deployment_authorization='User: proceed to fix and save to grf',
        previous_release=previous['release_id'],acceptance_records=[],coverage_reports=[],
        expected_replaced_resources=[dict(entry=r['entry'],sha256=r['sha256']) for r in previous['resources']])
    manifest['versions']={j:('Neck correction V1 plus diagonal shoulder V2' if j in ('acolyte','archer') else 'Neck/motion correction V1') for j in sorted({r['job'] for r in rows})}
    manifest['authoring_tools']=active_authoring_tools(previous.get('authoring_tools',[])+['correct_clan_neck_registration.py','fix_clan_shoulders.py','review_clan_neck_correction.py','release_clan_neck_shoulders.py'])
    if RETIREMENT_RECORD.exists():manifest['retired_work_record']=RETIREMENT_RECORD.relative_to(ROOT).as_posix()
    for job,sex in sorted({(r['job'],r['sex']) for r in rows}):
        chosen=[r for r in rows if (r['job'],r['sex'])==(job,sex)]
        report=ROOT/Path(chosen[0]['source']).parent.parent/f'{sex}-release-coverage.json'
        save(report,dict(actions=104,frame_uses=456,stock_fallback_frames=[],missing_sheets=[],detached_artwork_flags=[],
            provenance='Complete pinned source pair; current correction preserves every native action.',
            files=[dict(path=(ROOT/r['source']).relative_to(report.parent).as_posix(),sha256=r['sha256']) for r in chosen]))
        manifest['coverage_reports'].append(dict(job=job,sex=sex,path=report.relative_to(ROOT).as_posix()))
    save(RELEASE/'manifest.json',manifest)
    pack_payloads(raw,PATCH)
    save(RELEASE/'verification.json',dict(status='prepared_for_authorized_installation',files=rows,world_resources=24,
        actions=1248,frame_uses=5472,shoulder_changed_frame_uses=112,all_native_metadata_preserved=True,
        live_visual_acceptance=False,review_verification=WORK.relative_to(ROOT).as_posix()+'/review-verification.json',
        browser_verification=WORK.relative_to(ROOT).as_posix()+'/browser-verification.json',patch_sha256=digest(PATCH)))


def install():
    import release_accepted_clan_sprites as release
    manifest=load(RELEASE/'manifest.json');rows,raw=payloads()
    packed=GrfFile(PATCH)
    try:
        assert set(packed.entries)==set(raw)
        for name,data in raw.items():assert packed.read(name)==data
    finally:packed.close()
    release.CONFIG=manifest;release.RELEASE=RELEASE;release.PATCH=PATCH
    release.install(raw,GAME)
    installation=load(RELEASE/'installation.json')
    installation.update(release_id=RELEASE_ID,files=rows,live_visual_acceptance=False,
        authorization='User requested correction and GRF installation; no new visual acceptance claimed.')
    save(RECORD,installation)
    # The older Mage state remains preserved verbatim in this release's history.
    mage=ROOT/'Assets/ClanBodySkins/Mage/installed-correction.json'
    if mage.exists():
        state=load(mage)
        if state.get('release_id')!=RELEASE_ID:
            if not (RELEASE/'previous-mage-correction.json').exists():save(RELEASE/'previous-mage-correction.json',state)
            state=dict(status='deployed_requested_correction',release_id=RELEASE_ID,revision='neck-v1',
                package_tool='tools/release_clan_neck_shoulders.py',resources=[r for r in rows if r['job']=='mage'],
                deployment=RECORD.relative_to(ROOT).as_posix(),user_acceptance=False,
                previous_state=(RELEASE/'previous-mage-correction.json').relative_to(ROOT).as_posix())
            save(mage,state)
    manifest['status']='installed_correction';manifest['installation_record']=RECORD.relative_to(ROOT).as_posix()
    save(CURRENT,manifest);save(RELEASE/'manifest.json',manifest)
    state=load(WORK/'release-files.json');state.update(status='installed_correction',installation_record=RECORD.relative_to(ROOT).as_posix());save(WORK/'release-files.json',state)
    data=load(WORK/'review-data.json')
    for sexes in data['jobs'].values():
        for entry in sexes.values():entry['state']='Installed correction; live visual acceptance pending'
    save(WORK/'review-data.json',data)
    html=(WORK/'review.html').read_text(encoding='utf8')
    html=html.replace('These files are for review and are not installed in the GRF.','These exact pairs are installed in maindata.grf. Live visual acceptance is pending.')
    html=html.replace('native head and collar correction','head, collar and shoulder correction')
    (WORK/'review.html').write_text(html,encoding='utf8',newline='\n')
    # Only status text changed; preserve the hash of the exercised dataset too.
    browser=load(WORK/'browser-verification.json');browser['pre_install_review_data_sha256']=browser['review_data_sha256'];browser['review_data_sha256']=sha((WORK/'review-data.json').read_bytes());browser['post_install_change']='State text only; frame data and resources unchanged.';save(WORK/'browser-verification.json',browser)
    print('Installed and recorded all 24 world resources.',flush=True)


def archive():
    assert load(CURRENT)['release_id']==RELEASE_ID and load(RECORD)['status']=='installed'
    recovery=load(NECK/'recovery-verification.json');members={}
    for row in recovery['inputs']:
        p=ROOT/row['path'];assert p.is_file();members[row['path']]=p
    # Shoulder correction consumes four saved neck pairs; the remaining eight
    # neck pairs are themselves the deployed output, so each path is stored once.
    for r in load(ROOT/'Inputs/ClanBodySkins/records/clan-neck-motion-correction.json')['files']+load(WORK/'release-files.json')['files']:
        p=ROOT/r['source'];assert sha(p.read_bytes())==r['sha256'];members[r['source']]=p
    for row in load(CURRENT)['coverage_reports']:
        p=ROOT/row['path'];assert p.is_file();members[row['path']]=p
    for p in source_closure([Path(__file__),ROOT/'tools/fix_clan_shoulders.py',ROOT/'tools/review_clan_neck_correction.py']):members[p.relative_to(ROOT).as_posix()]=p
    if RETIREMENT_RECORD.exists():members[RETIREMENT_RECORD.relative_to(ROOT).as_posix()]=RETIREMENT_RECORD
    for folder in (RELEASE,WORK):
        for p in folder.rglob('*.json'):
            if p.name!='saved-work.json':members[p.relative_to(ROOT).as_posix()]=p
    for p in [CURRENT,RECORD,ROOT/'Assets/ClanBodySkins/Mage/installed-correction.json',ROOT/'docs/clan-body-skins.md',ROOT/'tools/clan_neck_correction_review.html',ROOT/'tools/verify_clan_shoulder_release_browser.cjs',WORK/'review.html',ROOT/'Inputs/ClanBodySkins/records/clan-neck-motion-correction.json']:
        members[p.relative_to(ROOT).as_posix()]=p
    saved=write_zip(RELEASE/'current-work.zip',members);save(RELEASE/'saved-work.json',dict(status='saved_and_verified',archive=saved,includes='Pinned native/source assets, current exports, authoring code, verification, rollback receipt and single guide; no preview PNGs or older ZIP copies.'))
    print(json.dumps(saved),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['prepare','install','archive']);a=p.parse_args()
    {'prepare':prepare,'install':install,'archive':archive}[a.stage]()
