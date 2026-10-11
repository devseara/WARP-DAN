import tempfile
import os
import struct
import pefile
import unittest
from pathlib import Path
from unittest.mock import patch
import verify_riftlock_client as verifier

class RiftlockVerifierTests(unittest.TestCase):
	def test_current_v8_sources_and_vectors(self):
		verifier.check_sources()
		verifier.check_protocol_vectors()

	def test_hello_release_offsets_are_exact(self):
		size, fields = verifier.wire_layout(verifier.PROTOCOL.read_text(encoding='utf8'), 'ClientHello')
		self.assertEqual(600, size)
		self.assertIn(('release_number', 516, 4), fields)
		self.assertIn(('release_signature', 520, 64), fields)
		self.assertIn(('tag', 584, 16), fields)

	def test_v7_is_rejected(self):
		self.check_bad_protocol('kProtocolVersion = 8', 'kProtocolVersion = 7')

	def test_reordered_release_fields_are_rejected(self):
		self.check_bad_protocol('std::uint32_t release_number;\n\tstd::uint8_t release_signature[kSignatureSize];',
			'std::uint8_t release_signature[kSignatureSize];\n\tstd::uint32_t release_number;')

	@unittest.skipUnless(os.environ.get('RIFTLOCK_TEST_EXE'), 'set RIFTLOCK_TEST_EXE to a fresh WARP output')
	def test_emitted_reader_and_lazy_imports(self):
		verifier.check_pe(Path(os.environ['RIFTLOCK_TEST_EXE']))

	@unittest.skipUnless(os.environ.get('RIFTLOCK_TEST_EXE'), 'set RIFTLOCK_TEST_EXE to a fresh WARP output')
	def test_reader_slot_cannot_resolve_another_export(self):
		pe = pefile.PE(os.environ['RIFTLOCK_TEST_EXE'])
		base = pe.OPTIONAL_HEADER.ImageBase
		bridge = verifier.relative_target(pe, 0x00C147D0, 1)
		slot = struct.unpack_from('<I', pe.get_data(bridge-base,17),13)[0]
		iat = {symbol.name.decode('ascii'): symbol.address
			for descriptor in pe.DIRECTORY_ENTRY_IMPORT if descriptor.dll.lower()==b'riftlock.dll'
			for symbol in descriptor.imports if symbol.name}
		with self.assertRaises(AssertionError):
			verifier.check_export_slot(pe,slot,'RiftlockQueuePacketBridge',iat)

	def check_bad_protocol(self, old, new):
		text = verifier.PROTOCOL.read_text(encoding='utf8')
		self.assertIn(old,text)
		with tempfile.TemporaryDirectory() as folder:
			path = Path(folder)/'protocol.h'; path.write_text(text.replace(old,new),encoding='utf8')
			with patch.object(verifier,'PROTOCOL',path), self.assertRaises(AssertionError):
				verifier.check_sources()

if __name__ == '__main__': unittest.main()
