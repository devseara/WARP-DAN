"""Focused quantity regression using fresh payloads and the real native icon/count x86.

The existing EXE is read only. Fonts, textures and OS calls are explicit emulator
boundaries; no server, player data or unrelated feature suites are exercised.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_EAX
import test_inventory_cart_payloads as payloads
import test_storage_payload as storage_payload

ROOT = Path(__file__).resolve().parents[1]
COUNTS = [1, 9, 10, 99, 100, 201, 582, 999, 1000, 1002, 9999, 10000, 11002, 30000]


def native_boundaries(m):
    """Execute 0x8711A0 itself, replacing only texture/font/format boundaries."""
    m.quantity_text = []
    m.quantity_icons = []
    m.u.hook_del(m._machine_stubs.pop(0x8711A0))
    texture = m.alloc(0x130)

    def item_path():
        _, out, _ = m.args(3)
        m.u.mem_write(out, b'quantity-fixture\0')
        m.ret(12)

    def load_texture():
        if m.cstr(m.args(1)[0]) == 'quantity-fixture':
            m.ret(4, texture)
        else:
            m.texture()

    def sprintf():
        out, fmt, count = m.args(3)
        assert m.cstr(fmt) == '%d'
        value = str(count).encode()
        m.u.mem_write(out, value + b'\0')
        m.ret(0, len(value))

    def measure():
        ptr, length, _, size, bold, _ = m.args(6)
        text = m.cstr(ptr)
        if length:
            text = text[:length]
        font = ImageFont.truetype('C:/Windows/Fonts/tahomabd.ttf' if bold else 'C:/Windows/Fonts/tahoma.ttf', size)
        m.ret(24, math.ceil(font.getlength(text)))

    def draw_text():
        x, y, ptr, length, _, size, color, bold, _ = m.args(9)
        text = m.cstr(ptr)
        if length:
            text = text[:length]
        font = ImageFont.truetype('C:/Windows/Fonts/tahomabd.ttf' if bold else 'C:/Windows/Fonts/tahoma.ttf', size)
        m.quantity_text.append((text, x, y, size, color, math.ceil(font.getlength(text))))
        pixels, width, height = m.pixels(m.u.reg_read(UC_X86_REG_ECX))
        im = Image.frombytes('RGBA', (width, height), bytes(m.u.mem_read(pixels, width*height*4)), 'raw', 'BGRA')
        ImageDraw.Draw(im).text((x, y-2), text, font=font, fill=(color&255, color>>8&255, color>>16&255, 255))
        m.u.mem_write(pixels, im.tobytes('raw', 'BGRA'))
        m.ret(36)

    def draw_icon():
        x, y, tex, _ = m.args(4)
        if tex != texture:
            m.sprite()
            return
        pixels, width, height = m.pixels(m.u.reg_read(UC_X86_REG_ECX))
        im = Image.frombytes('RGBA', (width, height), bytes(m.u.mem_read(pixels, width*height*4)), 'raw', 'BGRA')
        d = ImageDraw.Draw(im)
        d.ellipse((x+5, y+4, x+18, y+18), fill='#c5bfe9', outline='#746e8d')
        d.rectangle((x+9, y+2, x+14, y+5), fill='#e6e5ef', outline='#746e8d')
        m.u.mem_write(pixels, im.tobytes('raw', 'BGRA'))
        m.ret(16)

    def observe(u, address, size, user):
        x, y, item, _, _ = m.args(5)
        m.quantity_icons.append((x, y, item, m.r(item+0x10)))

    m.stub(0xD5A720, item_path)
    m.stub(0xA8D4A0, load_texture)
    m.stub(0x529850, sprintf)
    m.stub(0xA21C90, measure)
    m.stub(0xA25A70, draw_text)
    m.stub(0xA1D260, draw_icon)
    m.stub(0xDBBBD4, lambda: m.ret(0, m.u.reg_read(UC_X86_REG_EAX)))
    m.u.hook_add(UC_HOOK_CODE, observe, begin=0x8711A0, end=0x8711A0)


def check(m, label, output, is_storage=False, block=False):
    if is_storage:
        m.w(m.c['state']+12, int(block))
        m.rows([(i+1, 501, 0, count, 0) for i, count in enumerate(COUNTS)])
        items = m.items
    else:
        m.inventory([(i+1, 501, count, 0, 'Potion') for i, count in enumerate(COUNTS)])
        items = list(m.slots.values())
    before = [bytes(m.u.mem_read(p, 0xF8)) for p in items]
    m.quantity_text.clear()
    m.quantity_icons.clear()
    m.invoke(m.c['draw'], m.obj)
    quantity = [r for r in m.quantity_text if r[0].isdigit() and r[4] in (0, 0xFFFFFF)]
    foreground = [r for r in quantity if r[4] == 0]
    assert len(foreground) == len(m.quantity_icons) > 0
    seen = []
    for (text, x, y, size, color, width), (icon_x, icon_y, pointer, native_amount) in zip(foreground, m.quantity_icons):
        amount = COUNTS[len(seen)]
        assert text == str(amount), (label, text, amount)
        left, right = icon_x-4, icon_x+28
        assert x-1 >= left and x+width+1 <= right, (label, amount, x, width, left, right)
        assert y == icon_y+15 and size >= 8
        if amount in (1000, 1002, 9999):
            assert x == icon_x and native_amount == amount and pointer == items[len(seen)], 'working four-digit path changed'
        if amount in (100, 201, 582, 999):
            assert x < icon_x+14 and native_amount == 0 and pointer != items[len(seen)], 'short-count overflow not isolated'
        seen.append(amount)
    assert before == [bytes(m.u.mem_read(p, 0xF8)) for p in items], 'session CItem was mutated'
    assert len(quantity) == 5*len(seen), 'missing/duplicate count or outline'
    pixels, width, height = m.pixels(m.obj)
    im = Image.frombytes('RGBA', (width, height), bytes(m.u.mem_read(pixels, width*height*4)), 'raw', 'BGRA').convert('RGB')
    # Compare each completed cell with its own isolated text layer. Adjacent
    # cells painted later must not erase any of the count's black pixels.
    for text, x, y, size, color, advance in foreground:
        mask = Image.new('L', (width, height))
        ImageDraw.Draw(mask).text((x, y-2), text, font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf', size), fill=255)
        for yy in range(y, min(height, y+12)):
            for xx in range(x, min(width, x+advance)):
                if mask.getpixel((xx, yy)) == 255:
                    assert im.getpixel((xx, yy)) == (0, 0, 0), (label, text, 'quantity overwritten', xx, yy)
    im.save(output/(label+'.png'))
    print('PASS', label, seen)
    return {'view': label, 'counts': seen, 'unchanged_items': len(items)}


def reproduce_native_overflow(m):
    m.inventory([(1, 501, 201, 0, 'Potion')])
    pointer = m.slots[1]
    for amount in (201, 1002):
        m.w(pointer+0x10, amount)
        m.quantity_text.clear()
        m.invoke(0x8711A0, m.obj, (60, 63, pointer, 0, 0))
        foreground = [r for r in m.quantity_text if r[4] == 0]
        assert len(foreground) == 1
        text, x, y, size, color, width = foreground[0]
        assert text == str(amount)
        assert (x+width+1 > 88) == (amount == 201)
    print('PASS reproduced original 201 overflow while original 1002 fits.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('client', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    header_hash = hashlib.sha256((ROOT/'Scripts/Runtime/ItemSlotQuantity.h').read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    for feature in ('InventoryUI', 'CartUI', 'StorageUI'):
        assert json.loads((ROOT/f'Inputs/{feature}/runtime.json').read_text())['quantity_header_sha256'] == header_hash
    payloads.install_overlay()
    original = storage_payload.storage.contract
    storage_payload.storage.contract = lambda m: storage_payload.overlay(m, original(m))
    results = []
    for cls, label in [(payloads.inv.InventoryMachine, 'inventory'), (payloads.cart.CartMachine, 'cart')]:
        m = cls(str(args.client))
        native_boundaries(m)
        if label == 'inventory':
            reproduce_native_overflow(m)
        results.append(check(m, label, args.output))
        m.setsize(m.obj, 344, 360)
        results.append(check(m, label+'-resized', args.output))
    m = storage_payload.storage.StorageMachine(str(args.client))
    native_boundaries(m)
    # Both personal and guild storage receive the same INVTYPE_STORAGE list
    # and native UIStorageWnd. Exercise its list and block layouts separately.
    for label in ('storage', 'guild-storage'):
        for block in (False, True):
            # List view needs enough visible rows to include the 30000 sample.
            m.w(m.c['state']+1692, 14)
            m.setsize(m.obj, 312, 573)
            results.append(check(m, label+('-block' if block else '-list'), args.output, True, block))
    (args.output/'results.json').write_text(json.dumps({'results': results, 'limit': 30000, 'live_acceptance': False}, indent=2))
    print('PASS: real native quantity path, all four windows, full counts through 30000, outline, adjacent cells, and unchanged item data.')


if __name__ == '__main__':
    main()
