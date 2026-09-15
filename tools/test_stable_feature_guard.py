"""Ensure the preservation check detects edits, missing files and unsafe paths."""
import tempfile
from pathlib import Path
from verify_stable_features import digest, verify


with tempfile.TemporaryDirectory(prefix='stable-feature-guard-') as directory:
    root = Path(directory)
    text = root / 'sample.txt'
    text.write_bytes(b'accepted\r\n')
    manifest = {'files': {'sample.txt': {'mode': 'text-lf', 'sha256': digest(b'accepted\n', 'text-lf')}}}
    assert verify(root, manifest) == []
    text.write_bytes(b'changed\n')
    assert verify(root, manifest) == ['CHANGED sample.txt']
    text.unlink()
    assert verify(root, manifest) == ['MISSING sample.txt']
    assert digest(b'\r\n', 'binary') != digest(b'\n', 'binary')
    for bad in ({'files': {}}, {'files': {'../outside': {'mode': 'binary', 'sha256': '0' * 64}}}):
        try:
            verify(root, bad)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid baseline accepted')
print('PASS: preservation guard detects modifications/missing files, normalizes only text, rejects unsafe/empty baselines')
