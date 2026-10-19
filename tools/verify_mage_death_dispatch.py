"""Execute CPlayer's actual death action resource-replacement path."""

import json
import hashlib
from pathlib import Path
from unicorn.x86_const import *
import first_job_hd_sprites as h
from verify_mage_mount_compositor import Engine, WORK

OUT = WORK.parent / 'mage-mounted-grip-v48'


class Death(Engine):
    def boundary(self, uc, pc, size, unused):
        if pc in [0xD5B8E0, 0xD5BC30]:
            out, job, sex, body, variant = self.args(5)
            expected = 4130 if self.mounted and self.eligible else 2
            assert job == expected, (hex(pc), job, expected)
            ext = 'act' if pc == 0xD5B8E0 else 'spr'
            stem = '여우마법사' if job == 4130 else '마법사'
            name = f'sprite\\인간족\\몸통\\여\\{stem}_여.{ext}'
            raw = name.encode('cp949')
            p = self.alloc(len(raw) + 1)
            self.u.mem_write(p, raw + b'\0')
            self.w(out, p)
            self.w(out + 16, len(raw))
            self.w(out + 20, len(raw))
            self.ret(out, 20)
            self.producers.append(dict(extension=ext, job=job, sex=sex, body=body, variant=variant))
        elif pc in [0xD3D7C0, 0xD3FD90]:
            slot, name = self.args(2)
            assert slot == 0
            text = self.string(name)
            self.loaded.append(text)
            self.ret(0, 8)
        elif pc == 0xDBBC7F:
            self.ret(0)
        else:
            super().boundary(uc, pc, size, unused)


def verify(candidate=None):
    m = Death(candidate or OUT / 'death-client/client.exe')
    m.producers = []
    m.loaded = []
    cases = []
    for mounted, sex in [(1, 0), (0, 0), (1, 1)]:
        m.mounted = mounted
        m.eligible = sex == 0
        m.actor_state(mounted=mounted, sex=sex)
        for direction in range(8):
            m.w(m.actor + 0x70, 4)
            m.w(m.actor + 0x34, direction)
            m.w(m.actor + 0x38, 32 + direction)
            m.w(m.sp, 0x50003000)
            m.w(m.sp + 4, 3)
            m.w(m.sp + 8, 0)
            m.u.reg_write(UC_X86_REG_ESP, m.sp)
            m.u.reg_write(UC_X86_REG_ECX, m.actor)
            before = len(m.producers)
            m.u.emu_start(0xD41DF0, 0xD41F15, count=10000)
            assert m.u.reg_read(UC_X86_REG_EIP) == 0xD41F15
            assert len(m.producers) == before + 2
            assert m.u.mem_read(m.actor + 0x2CC, 1)[0] == mounted
            cases.append(
                dict(mounted=mounted, sex=sex, direction=direction, resources=m.producers[before:])
            )
    result = dict(
        passed=True,
        client_sha256=hashlib.sha256(
            Path(candidate or OUT / 'death-client/client.exe').read_bytes()
        ).hexdigest(),
        native_death_dispatch_cases=len(cases),
        mount_flag_unchanged=True,
        both_body_resources_selected=True,
        file_producer_and_load_boundaries_doubled=True,
        live_visual_acceptance=False,
        cases=cases,
    )
    (OUT / 'death-dispatch.json').write_text(json.dumps(result, indent=2) + '\n')
    print(
        'PASS 24 real death-dispatch cases: mounted female Fox body, unmounted/male native selection.'
    )


if __name__ == '__main__':
    verify()
