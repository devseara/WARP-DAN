"""TradeUI live-input regression against the shipped x86 editor pipeline.

This keeps the native UIEdit GetText, OnDraw, slot 55 text/caret layout and
selection geometry. Only final graphics/font/OS calls are boundary doubles.
It is offline evidence, not an in-game two-player acceptance test.
"""
import argparse
from pathlib import Path

from PIL import ImageFont
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX

from test_trade_ui import TradeMachine


class ZenyMachine(TradeMachine):
    def __init__(self, exe):
        super().__init__(exe)
        for address in (0x8210A0, 0x824FC0):
            hook = self._machine_stubs.pop(address, None)
            if hook is not None:
                self.u.hook_del(hook)
        self.draw_calls = []
        self.selection_calls = []
        self.stub(0xA25A70, lambda: self.capture_text(9))
        self.stub(0xA280D0, lambda: self.capture_text(8))
        self.stub(0xA1D460, self.capture_selection)
        # Blink-on clock and client keyboard-focus check are OS boundaries.
        self.stub(self.r(0xFC17B0), lambda: self.ret(0, 0))
        self.stub(0x821580, lambda: self.ret(0, 1))
        assert self.r(self.r(self.editor) + 55 * 4) == 0x81ED00

    def capture_text(self, count):
        args = self.args(count)
        x, y, ptr = args[:3]
        value = self.cstr(ptr)
        self.draw_calls.append((self.u.reg_read(UC_X86_REG_ECX), x, y, value))
        self.ret(count * 4)

    def capture_selection(self):
        self.selection_calls.append(tuple(self.args(5)))
        self.ret(20)

    def value(self):
        ptr = self.input + 0x34 if self.r(self.input + 0x48) < 16 else self.r(self.input + 0x34)
        return self.cstr(ptr)

    def insert(self, text, start=None, end=None):
        if start is not None:
            self.w(self.input + 0x50, start)
            self.w(self.input + 0x54, start if end is None else end)
        ptr = self.alloc(len(text.encode()) + 1)
        self.u.mem_write(ptr, text.encode() + b'\0')
        self.invoke(0xA6EA10, self.input, (ptr,))

    def draw(self, expected, require_caret=True):
        self.draw_calls.clear()
        self.selection_calls.clear()
        self.invoke(self.c['editdraw'], self.editor)
        calls = [call for call in self.draw_calls if call[0] == self.editor]
        values = [call for call in calls if call[3] == expected]
        assert values, ('native editor did not draw the formatted amount', expected, calls)
        width, height = self.r(self.editor + 0x14), self.r(self.editor + 0x18)
        font = ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf', 12)
        for _, x, y, text in calls:
            assert 0 <= x < width and 0 <= y and y + 12 <= height, (
                'native text/caret outside the Zeny editor', text, x, y, width, height)
            assert x + int(font.getlength(text)) <= width, ('text outside editor width', text, x, width)
        assert self.r(self.editor + 0xB4) == 2, 'native editor vertical inset changed'
        if require_caret:
            assert any(call[3] == '|' for call in calls), ('native caret was not drawn', calls)
        return calls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe', type=Path)
    args = parser.parse_args()
    machine = ZenyMachine(args.exe)

    # This first case reproduces the reported regression: the old build passes
    # y=105 to native text output for 5,555 inside a 16px-high child surface.
    machine.inputText('5555')
    machine.draw('5,555')
    assert machine.value() == '5,555'

    # Actual insert/delete/replace logic, followed by the real formatted draw.
    machine.inputText('')
    for digit, expected in zip('1000000', ['1', '10', '100', '1,000', '10,000', '100,000', '1,000,000']):
        machine.insert(digit)
        machine.draw(expected)
        assert machine.value() == expected
        assert machine.r(machine.input + 0x50) == len(expected)
        assert machine.r(machine.input + 0x54) == len(expected)

    machine.insert('', len(machine.value()) - 1, len(machine.value()))
    machine.draw('100,000')
    machine.insert('5555', 0, len(machine.value()))
    machine.draw('5,555')
    machine.insert('1234567', 0, len(machine.value()))
    machine.draw('1,234,567')

    # Removing a displayed comma keeps the amount and moves the caret before
    # it, so the next backspace can remove the preceding digit normally.
    machine.insert('', 5, 6)
    machine.draw('1,234,567')
    assert machine.r(machine.input + 0x50) == 5
    machine.insert('', 4, 5)
    machine.draw('123,567')
    assert machine.r(machine.input + 0x50) == 3
    machine.insert('', 0, len(machine.value()))
    machine.draw('')
    machine.insert('1000000001')
    machine.draw('1,000,000,000')

    # Preserve a selection through comma insertion and exercise the original
    # native selection rectangle path rather than replacing UIEdit slot55.
    machine.inputText('1234567')
    machine.w(machine.input + 0x50, 1)
    machine.w(machine.input + 0x54, 4)
    machine.draw('1,234,567', require_caret=False)
    assert (machine.r(machine.input + 0x50), machine.r(machine.input + 0x54)) == (1, 5)
    assert machine.selection_calls, 'native selection highlight was not drawn'
    for x, y, width, height, _ in machine.selection_calls:
        assert 0 <= x and x + width <= 140 and y == 0 and height == 16

    # Native GetText synchronizes the input into the UIEdit cached string. The
    # unfocused draw must retain it rather than draw another focused editor.
    machine.w(0x131F4E8 + 0x1A0, 0)
    machine.inputText('999')
    machine.draw('1,234,567', require_caret=False)
    machine.w(0x131F4E8 + 0x1A0, machine.editor)
    machine.inputText('1000000')
    machine.draw('1,000,000')
    # Exercise both stock final draw variants, retaining the same coordinates.
    old_outline = machine.r(machine.editor + 0xAC)
    machine.w(machine.editor + 0xAC, 0)
    machine.draw('1,000,000')
    machine.w(machine.editor + 0xAC, old_outline)
    machine.invoke(machine.c['numeric'], machine.editor)
    assert machine.cstr(machine.u.reg_read(UC_X86_REG_EAX)) == '1000000'
    print('PASS TradeUI real UIEdit text/caret/selection bounds, visible 5,555, progressive commas, native insertion/deletion/paste, caret preservation and unfocused retained text. Offline verification; live acceptance pending.')


if __name__ == '__main__':
    main()
