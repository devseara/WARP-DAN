"""Execute mount/dismount refresh through the complete native equipment setter."""

import json
from pathlib import Path
from unicorn.x86_const import *
import first_job_hd_sprites as h
from verify_mage_mount_compositor import Engine, WORK

OUT = WORK.parent / 'mage-mounted-death-v47'


class Lifecycle(Engine):
    def boundary(self, uc, pc, size, unused):
        if pc == 0xD401D0:
            self.shields += 1
            self.ret(0, 4)  # unchanged native shield refresh boundary
        elif pc in [0xD8A080, 0xD8A0F0]:
            # Stock slash-effect filename producer; no mounted slash art.
            out = self.args(1)[0]
            self.w(out, 0)
            self.w(out + 0x10, 0)
            self.w(out + 0x14, 15)
            self.ret(out, 28)
        elif pc in [0xD8A010, 0xD8A160] and not self.u.mem_read(self.actor + 0x2CC, 1)[0]:
            # Ordinary unmounted file producer is a control boundary. Mounted
            # filename construction executes the actual candidate/native string code.
            out = self.args(1)[0]
            ext = 'act' if pc == 0xD8A010 else 'spr'
            raw = self.expected[ext].encode('cp949')
            pointer = self.alloc(len(raw) + 1)
            self.u.mem_write(pointer, raw + b'\0')
            self.w(out, pointer)
            self.w(out + 0x10, len(raw))
            self.w(out + 0x14, len(raw))
            self.ret(out, 24)
        elif pc == 0xA8E500 and not self.string(self.args(1)[0]):
            self.ret(0, 4)
        elif pc == 0xDBBC7F:
            self.ret(0)
        else:
            super().boundary(uc, pc, size, unused)


def main(candidate=None):
    candidate = Path(candidate) if candidate else OUT / 'client/client.exe'
    m = Lifecycle(candidate)
    m.shields = 0
    for name in ['body', 'head', 'weapon']:
        m.act(name, h.base.read_act((WORK / 'fixtures' / (name + '.act')).read_bytes()))
    m.slots = {kind: m.alloc(9 * 4) for kind in ['act', 'spr']}
    for offset, kind in [(0x4B8, 'act'), (0x4AC, 'spr')]:
        m.w(m.actor + offset, m.slots[kind])
        m.w(m.actor + offset + 4, m.slots[kind] + 36)
    # The single-weapon dual-owner bridge's documented stock fallback invokes
    # this original method once. Execute that complete method instead of the
    # V46 test's earlier stop immediately after the preferred SPR load.
    m.u.mem_write(0xD403A0, bytes.fromhex('558bec6aff'))
    cases = []
    m.actor_state(mounted=0)
    for flag in [1, 1, 0, 0, 1]:
        old = m.u.mem_read(m.actor + 0x2CC, 1)[0]
        stem = '여우마법사' if flag else '마법사'
        m.expected = {
            ext: f'sprite\\인간족\\{stem}\\{stem}_여_단검.{ext}' for ext in ['act', 'spr']
        }
        count = len(m.loads)
        m.invoke(0xD3E340, [flag], m.actor)
        assert m.u.mem_read(m.actor + 0x2CC, 1)[0] == flag
        added = m.loads[count:]
        assert added == (
            [('act', m.expected['act']), ('spr', m.expected['spr'])] if old != flag else []
        ), added
        cases.append(dict(before=old, after=flag, loads=added))
    for kwargs in [dict(visible=1), dict(body=1), dict(sex=1), dict(weapon=1601), dict(left=1201)]:
        m.actor_state(mounted=0, **kwargs)
        count = len(m.loads)
        m.invoke(0xD3E340, [1], m.actor)
        assert len(m.loads) == count
    assert m.shields == 10
    result = dict(
        passed=True,
        transitions=cases,
        unsupported_actor_controls=5,
        native_shield_refresh_preserved=10,
        complete_native_equipment_setter_executed=True,
        scoped_owner_and_file_boundaries_documented=True,
        live_acceptance=False,
    )
    (OUT / 'mount-lifecycle-verification.json').write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
    )
    print(
        'PASS mount/dismount/repeated notification/other actor cases through the complete native single-weapon setter.'
    )


if __name__ == '__main__':
    main()
