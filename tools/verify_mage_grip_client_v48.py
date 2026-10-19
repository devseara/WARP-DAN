"""Verify death and Knife / standard Rod-Staff routing before art acceptance."""

import json
from pathlib import Path
from verify_mage_mount_lifecycle import Lifecycle
from verify_mage_mount_compositor import WORK
import first_job_hd_sprites as h

OUT = WORK.parent / 'mage-mounted-grip-v48'
ART = (
    Path(__file__).resolve().parents[1]
    / 'Assets/HDFirstJobs/animation-audit-v1/female-mage-gripping-v48'
)


class Staff(Lifecycle):
    def boundary(self, uc, pc, size, unused):
        if pc == 0xD8A1D0:
            item = self.args(1)[0]
            self.ret(10 if 1601 <= item <= 1609 else 1 if item == 1201 else 0, 4)
        else:
            super().boundary(uc, pc, size, unused)


def main():
    m = Staff(OUT / 'client/client.exe')
    m.shields = 0
    for name in ['body', 'head', 'weapon']:
        m.act(name, h.base.read_act((WORK / 'fixtures' / (name + '.act')).read_bytes()))
    m.slots = {kind: m.alloc(36) for kind in ['act', 'spr']}
    for offset, kind in [(0x4B8, 'act'), (0x4AC, 'spr')]:
        m.w(m.actor + offset, m.slots[kind])
        m.w(m.actor + offset + 4, m.slots[kind] + 36)
    m.u.mem_write(0xD403A0, bytes.fromhex('558bec6aff'))
    records = []
    for item in [1201] + list(range(1601, 1610)):
        m.actor_state(mounted=0, weapon=item)
        for flag in [1, 1, 0]:
            old = m.u.mem_read(m.actor + 0x2CC, 1)[0]
            stem = '여우마법사' if flag else '마법사'
            suffix = '단검' if item == 1201 else '롯드'
            m.expected = {
                ext: f'sprite\\인간족\\{stem}\\{stem}_여_{suffix}.{ext}' for ext in ['act', 'spr']
            }
            before = len(m.loads)
            m.invoke(0xD3E340, [flag], m.actor)
            expected = (
                [('act', m.expected['act']), ('spr', m.expected['spr'])] if old != flag else []
            )
            assert m.loads[before:] == expected, (item, flag, m.loads[before:])
            records.append(dict(item=item, mounted=flag, reloaded=old != flag))
    for kwargs in [dict(sex=1), dict(visible=1), dict(body=1), dict(left=1201), dict(weapon=1610)]:
        m.actor_state(mounted=0, **kwargs)
        before = len(m.loads)
        m.invoke(0xD3E340, [1], m.actor)
        assert len(m.loads) == before
    assert all(
        x['Candidate']
        for kind in ['knife', 'rod']
        for x in json.loads((ART / f'{kind}-gripping.actproj').read_text(encoding='utf-8'))[
            'Layers'
        ]
    )
    report = dict(
        passed=True,
        transition_cases=records,
        unsupported_controls=5,
        native_equipment_setter_executed=True,
        rod_native_weapon_class=10,
        candidate_game_assets_not_exported=True,
        art_acceptance_required=True,
        scope=dict(knife=[1201], native_rod_staff=list(range(1601, 1610))),
        live_acceptance=False,
    )
    (OUT / 'staff-routing-verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print(
        'PASS 30 native Knife/Rod/Staff transition cases and5 native fallback controls; art remains Candidate.'
    )


if __name__ == '__main__':
    main()
