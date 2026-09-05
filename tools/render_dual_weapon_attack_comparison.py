"""Compare the archived c2e857e3 attack with installed pixel-grip geometry.

Reads both compiled payloads and verifies their relocated bytes against the
archived EXEs. Runs the old C dispatch plus its real legacy core, not a
replacement formula. Renders original pixels over the same native body pose.
"""
from __future__ import annotations
import sys, json, hashlib, struct, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / '.venv/Lib/site-packages'))
sys.dont_write_bytecode = True
from PIL import Image, ImageDraw, ImageFont
import pefile
from verify_dual_weapon_pixel_grips import GripResources, GripMachine, CLIENT
from verify_dual_weapon_native_basis import NativeLegacyMachine, invoke_native
from verify_dual_weapon_native_projection import NativeProjector
from render_dual_weapon_native_overlay import paint
from dual_weapon_formats.spr_reader import Spr

OUT = ROOT / 'Outputs/dual_weapon_attack_comparison'
OLD_EXE = ROOT / 'Outputs/dual_weapon_supported_types/client-dagger-sword-axe.exe'
OLD_PAYLOAD = ROOT / 'Outputs/dual_weapon_supported_types/compositor.dwcp'
NEW_EXE = ROOT / 'Outputs/dual_weapon_grip_placement/client-pixel-grips.exe'
NEW_PAYLOAD = ROOT / 'Outputs/dual_weapon_grip_placement/compositor.dwcp'
OLD_SHA = 'c2e857e3e9d63b510f8b7f31015f821f951aab5033aeb404806acb1751eeeb02'
NEW_SHA = '95674dbae0b470c7cef7eade9580dea06038f337228d5f10753f1d73ff5d4220'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verified_pe(exe, payload, expected):
    assert sha(exe) == expected
    pe = pefile.PE(str(exe)); data = payload.read_bytes()
    _, _, size, entry, count, rigsize, gripsize, _ = struct.unpack_from('<8I', data)
    base = 0x1e7a4f0
    mapped = bytearray(data[32+count*4:])
    for offset in struct.unpack_from('<' + 'I'*count, data, 32):
        value, = struct.unpack_from('<I', mapped, offset)
        struct.pack_into('<I', mapped, offset, base+value)
    assert pe.get_data(base-pe.OPTIONAL_HEADER.ImageBase, len(mapped)) == mapped
    return pe, dict(exe=str(exe), exe_sha256=expected, payload_sha256=sha(payload),
                    compositor_va=hex(base), compositor_entry_va=hex(base+entry),
                    mapped_payload_bytes=len(mapped), full_payload_match=True)

class PreviousMachine(NativeLegacyMachine):
    def __init__(self, resources):
        super().__init__(resources, OLD_PAYLOAD)
        self.body = self.load('@body')
        self.w(self.slot, self.body['spr'])
        # Execute the archived C wrapper, with its legacy callback enabled.
        entry = struct.unpack_from('<I', OLD_PAYLOAD.read_bytes(), 12)[0]
        self.entry = self.code + entry
        self.w(self.ctx+19*4, self.legacy_base)
        self.legacy_entries = 0
    def native_hook(self, uc, address, size, user):
        if address == self.legacy_base:
            self.legacy_entries += 1
        super().native_hook(uc, address, size, user)
    def setup(self):
        self.main, self.off, self.stock, self.trail = self.equip(28, 1, 2)
        mt, ot = self.load('단검_검광'), self.load('검_검광')
        self.w(self.row+12, mt['spr'], mt['act'])
        self.w(self.row+28, ot['spr'], ot['act'])
        self.act_map = {r['act']: r for r in self.loaded.values()}
        return self.stock, self.trail

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    old_pe, old_identity = verified_pe(OLD_EXE, OLD_PAYLOAD, OLD_SHA)
    _, new_identity = verified_pe(NEW_EXE, NEW_PAYLOAD, NEW_SHA)
    resources = GripResources(CLIENT)
    old = PreviousMachine(resources); old_stock = old.setup()
    new = GripMachine(resources, NEW_PAYLOAD)
    new_stock = new.equip_views(new.load('1238'), new.load('13412'), 1, 2, 34, 45)
    # Verify that the legacy code and accepted embedded rig actually match
    # those installed in the archived PE, including every absolute relocation.
    source = (ROOT/'Scripts/Patches/AllowDualCustomWeaponSprites.qjs').read_text(encoding='utf-8')
    relocs = json.loads(re.search(r'const DualWeaponAuthoredCoreRelocs = (\[.*?\]);', source)[1])
    legacy = bytearray(old_pe.get_data(0x1e66d00-old_pe.OPTIONAL_HEADER.ImageBase, 63177))
    for offset, target in relocs:
        assert struct.unpack_from('<I', legacy, offset)[0] == 0x1e66d00+target
        struct.pack_into('<I', legacy, offset, old.legacy_base+target)
    assert bytes(old.u.mem_read(old.legacy_base, len(legacy))) == legacy
    old_context = struct.unpack('<21I', old_pe.get_data(0x1e87a40-old_pe.OPTIONAL_HEADER.ImageBase, 84))
    rig_ptr = old.r(old.ctx+8)
    rig_end = old.capture
    from verify_dual_weapon_scope import payload
    rig_bytes = payload(source, 'DualWeaponAuthoredRig')
    assert old_pe.get_data(old_context[2]-old_pe.OPTIONAL_HEADER.ImageBase, len(rig_bytes)) == rig_bytes
    assert bytes(old.u.mem_read(rig_ptr, len(rig_bytes))) == rig_bytes
    old_identity.update(legacy_code_match=True, legacy_rig_match=True)

    projector = NativeProjector(OLD_EXE)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 16)
    cache = {}; records = []; panels = {}
    def pixels(resource, kind, index):
        key = resource['name'], kind, index
        if key not in cache:
            rgba, w, h = Spr(resources.read(resource['name']+'.spr')).get_rgba(index, kind)
            cache[key] = Image.frombytes('RGBA', (w,h), rgba)
        return cache[key]
    for d in range(8):
        for f in range(8):
            action = 88+d
            for label, machine, carriers in [('old', old, old_stock), ('current', new, new_stock)]:
                canvas = Image.new('RGBA', (360,330), (223,234,238,255))
                layer = machine.native_layer(machine.body, action, f)
                im = pixels(machine.body, layer[8], layer[2])
                body_packet = projector.project(layer, (*im.size,0,0), origin=(400,300))
                paint(canvas, im, [*body_packet[:4], body_packet[7]])
                draws = []
                for channel, resource in zip((5,6), carriers):
                    result = invoke_native(machine, projector, resource, action, f, 1., channel)
                    if result:
                        assert result['handled'] == 1, (label,d,f,channel)
                        draws.extend(result['draws'])
                for draw in draws:
                    resource = machine.loaded[draw['resource']]
                    top,left,bottom,right,angle = draw['geometry']
                    paint(canvas, pixels(resource,*draw['image']),
                          [top-195,left-560,bottom-195,right-560,angle])
                record = dict(build=label, direction=d, frame=f, action=action,
                              body_image=layer[2], draws=draws)
                records.append(record); panels[label,d,f] = canvas.convert('RGB')
    assert old.legacy_entries == 96, old.legacy_entries
    # 8 held-style body channels and 4 terminal trail packets per direction.
    # Timing is deliberately slowed for inspection, independent of live ASPD.
    for d in range(8):
        frames=[]; old_frames=[]
        for f in range(8):
            im=Image.new('RGB',(720,395),(240,243,245)); p=ImageDraw.Draw(im)
            im.paste(panels['old',d,f],(0,58));im.paste(panels['current',d,f],(360,58))
            p.text((8,7),f'OLD c2e857e3 | D{d} F{f}',font=font,fill='black')
            p.text((368,7),f'CURRENT 95674dba | D{d} F{f}',font=font,fill='black')
            p.text((8,30),'Main: Zeny Knife 1238 / Off: blue Twin Edge 13412',font=font,fill='black')
            frames.append(im);old_frames.append(im.crop((0,0,360,395)))
        frames[0].save(OUT/f'old-vs-current-attack-d{d}.gif',save_all=True,append_images=frames[1:],duration=180,loop=0)
        old_frames[0].save(OUT/f'old-attack-d{d}.gif',save_all=True,append_images=old_frames[1:],duration=180,loop=0)
        sheet=Image.new('RGB',(1440,790*2),(240,243,245))
        for f, im in enumerate(frames):sheet.paste(im,((f%2)*720,(f//2)*395))
        sheet.save(OUT/f'old-vs-current-attack-d{d}-frames.png')
    all_frames=[]
    for f in range(8):
        im=Image.new('RGB',(1440,380),(240,243,245));p=ImageDraw.Draw(im)
        for i,d in enumerate((0,2,4,6)):
            im.paste(panels['old',d,f],(i*360,45))
            p.text((i*360+8,8),f'OLD attack | D{d} F{f}',font=font,fill='black')
        all_frames.append(im)
    all_frames[0].save(OUT/'old-attack-directions.gif',save_all=True,append_images=all_frames[1:],duration=180,loop=0)
    report=dict(schema='dual_weapon_attack_comparison/v1',old=old_identity,current=new_identity,
        loadout=dict(main_item=1238,main_view=34,off_item=13412,off_view=45),
        cells_per_build=64,old_legacy_calls=old.legacy_entries,body_family='female Assassin Cross',
        frame_duration_ms=180,records=records,
        limitations=['CPU nearest-neighbor rendering from actual x86 packets, not a live game recording.',
                    'Head omitted to expose the body arms; body drawn before weapons; native GPU depth/occlusion not simulated.',
                    '180 ms/frame is slowed inspection timing, not measured server ASPD.'])
    (OUT/'evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    html=['<!doctype html><meta charset="utf-8"><title>Previous attack comparison</title>',
          '<style>body{font:16px system-ui;background:#17212b;color:#f0f4f8;margin:24px}img{max-width:100%}</style>',
          '<h1>Previous attack vs current grip update</h1>',
          '<p>Old c2e857e3 on the left; current 95674dba on the right. Zeny Knife main, blue Twin Edge off. Compiled x86 packets and original SPR pixels. Head/depth omitted; slowed to 180 ms/frame.</p>']
    for d in (7,0,1,2,3,4,5,6):
        html.append(f'<h2>Direction {d}</h2><img src="old-vs-current-attack-d{d}.gif">')
    (OUT/'review.html').write_text('\n'.join(html),encoding='utf-8')
    print(json.dumps(dict(output=str(OUT),cells_per_build=64,old_legacy_calls=old.legacy_entries)))

if __name__=='__main__':main()
