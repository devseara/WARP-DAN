"""Execute Barter crafting metadata through the installed x86 packet dispatcher."""
import argparse
from pathlib import Path
import struct
from test_barter_ui import BarterMachine, normal, expanded


def metadata(native, rates):
    fingerprint = 2166136261
    for byte in native:
        fingerprint = ((fingerprint ^ byte) * 16777619) & 0xffffffff
    body = b''.join(struct.pack('<IIHH', index, item, rate, 0) for index, item, rate in rates)
    return bytearray(struct.pack('<HHIHHIHH', 0xbf6, 20+len(body), 0x52545242, 1, 1,
                                 fingerprint, len(rates), 0) + body)


def outcome(success, failed):
    return struct.pack('<HHIHHII', 0xbf6, 20, 0x52545242, 1, 2, success, failed)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('exe', type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    m = BarterMachine(args.exe, root/'Assets/BarterUI')
    def labels():
        m.preview()
        return {t: color for t, color, x, y in m.text_colors if t.startswith('Rate:')}
    p = normal([(984,100,756,5,7),(505,100,510,3,8)])
    m.receive(p)
    assert labels() == {'Rate: 100%': 0x3b8316}, 'legacy server defaults must remain green 100%'
    rates = metadata(p, [(7,984,20),(8,505,100)])
    m.receive(rates)
    assert labels() == {'Rate: 20%': 0x2822c5, 'Rate: 100%': 0x3b8316}
    m.preview(args.output/'rates-20-100.png')
    # All named color stops plus endpoints; exercise the actual native text color.
    palette = [(100,0x3b8316),(80,0x1a7f4f),(60,0x007680),(50,0x005fb6),
               (40,0x054bbd),(30,0x133ac1),(25,0x2a2ac9),(20,0x2822c5),
               (10,0x261ab8),(5,0x210ea3),(0,0x210ea3)]
    for percent, color in palette:
        m.receive(metadata(p, [(7,984,percent),(8,505,100)]))
        assert labels()[f'Rate: {percent}%'] == color, (percent, labels())
    m.receive(rates)
    # Invalid version, hash, count, item/index, rate and reserved bits cannot
    # partly overwrite a valid catalog, including a bad final row.
    for offset, fmt, value in [(8,'H',2),(10,'H',99),(12,'I',0),(16,'H',3),
                               (18,'H',1),(20,'I',99),(24,'I',501),(28,'H',101),
                               (30,'H',1),(40,'H',101),(2,'H',21)]:
        bad = bytearray(rates); struct.pack_into('<'+fmt,bad,offset,value)
        m.receive(bad)
        assert labels() == {'Rate: 20%':0x2822c5,'Rate: 100%':0x3b8316}, offset
    m.receive(outcome(1,0)) # no pending purchase: ignored
    m.click(80,55); m.preview()
    assert any(t[0]=='Attempts x1' for t in m.texts)
    m.click(585,184); m.click(480,360)
    assert m.state(32) == 1
    m.receive(outcome(100,0)) # invalid total
    m.receive(outcome(1,1)); m.receive(outcome(0,2)) # duplicate cannot replace accepted result
    m.receive(struct.pack('<HB',0xca,0)); m.preview(args.output/'mixed-outcome.png')
    assert any(t[0]=='Crafted: 1. Failed: 1.' for t in m.texts)
    assert any(t[0]=='Stock: 98' for t in m.texts), 'stock decrements by attempts'
    assert m.state(28)==0 and m.state(32)==0
    m.receive(p); m.receive(rates); m.click(80,55); m.click(480,360)
    m.receive(outcome(0,1)); m.receive(struct.pack('<HB',0xca,0)); m.preview(args.output/'failed-outcome.png')
    assert any(t[0]=='Crafted: 0. Failed: 1.' for t in m.texts)
    # A refreshed/reopened native catalog resets rates and rejects old metadata.
    fresh = normal([(984,77,756,5,7),(505,100,510,3,8)])
    m.receive(fresh); m.receive(rates)
    assert labels()=={'Rate: 100%':0x3b8316}
    m.click(530,360); m.receive(rates); assert m.state(4)==0
    p = expanded(count=2,materials=4)
    m.receive(p); m.receive(metadata(p, [(20,504,50),(21,505,5)]))
    assert labels()=={'Rate: 50%':0x005fb6,'Rate: 5%':0x210ea3}
    m.click(80,55); m.preview(args.output/'expanded-50-5.png')
    assert any(t[0]=='Attempts x1' for t in m.texts)
    print('PASS: actual BRTR routing; both catalogs; all rate colors; malformed/stale metadata; per-attempt cart; mixed/all-failed outcomes and stock accounting.')
    print('Offline x86/native boundary evidence; no live purchases.')


if __name__ == '__main__':
    main()
