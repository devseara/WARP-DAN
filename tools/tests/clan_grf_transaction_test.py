"""Prove record replacement/removal and exact rollback on small GRF fixtures."""
from pathlib import Path
import json
import copy
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from package_clan_skin_assets import pack_payloads
from clan_grf_transaction import replace_records, rollback, digest
from grf_reader import GrfFile
from save_accepted_clan_work import active_authoring_tools, RETIREMENT_RECORD
from release_accepted_clan_sprites import validate_active_release, validate_resource_pairs, validate_update_shadows, validate_complete_artwork


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='clan-grf-test-', dir=ROOT / 'Outputs')
        self.root = Path(self.temp.name).resolve()
        assert self.root.is_relative_to((ROOT / 'Outputs').resolve())
        self.target = self.root / 'fixture.grf'
        self.receipt = self.root / 'receipt.json'
        pack_payloads({'data/keep.bin': b'unchanged', 'data/change.bin': b'old',
                       'data/remove.bin': b'duplicate'}, self.target)
        self.before = self.target.read_bytes()

    def tearDown(self):
        assert self.root.is_relative_to((ROOT / 'Outputs').resolve())
        self.temp.cleanup()

    def test_replace_add_remove_preserve_and_rollback(self):
        row = replace_records(self.target, {'data/change.bin': b'new', 'data/add.bin': b'added'},
                              self.receipt, remove=['data/remove.bin'])
        self.assertEqual(row['entries'], 3)
        archive = GrfFile(self.target)
        try:
            self.assertEqual(set(archive.entries), {'data/keep.bin', 'data/change.bin', 'data/add.bin'})
            self.assertEqual(archive.read('data/keep.bin'), b'unchanged')
            self.assertEqual(archive.read('data/change.bin'), b'new')
        finally:
            archive.close()
        rollback(self.receipt)
        self.assertEqual(self.target.read_bytes(), self.before)

    def test_unchanged_is_noop_and_changed_archive_blocks_rollback(self):
        row = replace_records(self.target, {'data/change.bin': b'old'}, self.receipt)
        self.assertEqual(row['status'], 'already_current')
        self.assertEqual(self.target.read_bytes(), self.before)
        replace_records(self.target, {'data/change.bin': b'new'}, self.receipt)
        with self.target.open('ab') as stream:
            stream.write(b'external change')
        expected = digest(self.target)
        with self.assertRaisesRegex(AssertionError, 'Archive changed'):
            rollback(self.receipt)
        self.assertEqual(digest(self.target), expected)


class ReleaseManifestTests(unittest.TestCase):
    def test_full_job_rejects_stock_fallback_even_with_complete_act_table(self):
        record = dict(job='archer', sex='female', path='Assets/test/female-verification.json')
        files = [dict(path='assets/female.spr', sha256='spr'), dict(path='assets/female.act', sha256='act')]
        manifest = dict(resources=[dict(job='archer', sex='female', source='Assets/test/' + row['path'], sha256=row['sha256']) for row in files])
        report = dict(actions=104, frame_uses=456, stock_fallback_frames=[], missing_sheets=[], detached_artwork_flags=[], files=files)
        validate_complete_artwork(manifest, record, report)
        pilot = copy.deepcopy(report)
        pilot['stock_fallback_frames'] = [[9, 0]]
        with self.assertRaisesRegex(ValueError, 'stock_fallback'):
            validate_complete_artwork(manifest, record, pilot)
        stale = copy.deepcopy(report)
        stale['files'][0]['sha256'] = 'old-export'
        with self.assertRaisesRegex(ValueError, 'does not match'):
            validate_complete_artwork(manifest, record, stale)

    def test_release_requires_both_sexes_and_matching_spr_act(self):
        rows = json.loads((ROOT / 'Inputs/ClanBodySkins/records/clan-sprites-current.json').read_text(encoding='utf8'))['resources']
        self.assertEqual({row['job'] for row in rows}, {'swordman', 'mage', 'acolyte', 'archer', 'merchant', 'thief'})
        validate_resource_pairs(rows)
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            validate_resource_pairs(rows[:-1])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            validate_resource_pairs(rows + [rows[-1]])
        with self.assertRaisesRegex(ValueError, 'Missing male/female'):
            validate_resource_pairs([row for row in rows if not (row['job'] == 'acolyte' and row['sex'] == 'female')])
        bad = copy.deepcopy(rows)
        bad[-1]['entry'] = bad[-1]['entry'].replace('.act', '-wrong.act')
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            validate_resource_pairs(bad)

    def test_new_job_shadow_is_rejected_before_archive_mutation(self):
        desired = {'data/sprite/clan_skins/1/new.act': b'accepted'}
        validate_update_shadows(desired, {}, {})
        with self.assertRaisesRegex(ValueError, 'Unreviewed'):
            validate_update_shadows(desired, desired, {})
        validate_update_shadows(desired, desired, desired)

    def test_current_manifest_matches_active_correction_and_v7_is_rejected(self):
        current = json.loads((ROOT / 'Inputs/ClanBodySkins/records/clan-sprites-current.json').read_text(encoding='utf8'))
        historical = json.loads((ROOT / 'Inputs/ClanBodySkins/records/clan-sprites-accepted-v2.json').read_text(encoding='utf8'))
        state = dict(status='deployed_requested_correction', resources=[
            row for row in current['resources'] if row['job'] == 'mage' and row['sex'] == 'female'])
        validate_active_release(current, state)
        with self.assertRaisesRegex(ValueError, 'downgrade'):
            validate_active_release(historical, state)

    def test_retired_authoring_tools_cannot_return_through_old_manifests(self):
        current = json.loads((ROOT / 'Inputs/ClanBodySkins/records/clan-sprites-current.json').read_text(encoding='utf8'))
        record = json.loads(RETIREMENT_RECORD.read_text(encoding='utf8'))
        retired = [Path(row['path']).name for row in record['files'] if row['path'].startswith('tools/')]
        restored_old_names = current['authoring_tools'] + retired
        self.assertEqual(active_authoring_tools(restored_old_names), current['authoring_tools'])
        self.assertTrue(all((ROOT / 'tools' / name).is_file() for name in current['authoring_tools']))
        self.assertIn('native_sprite_tracing.py', current['authoring_tools'])
        self.assertIn('build_registered_angel_job.py', current['authoring_tools'])

    def test_unpinned_pending_correction_refuses_release(self):
        current = json.loads((ROOT / 'Inputs/ClanBodySkins/records/clan-sprites-current.json').read_text(encoding='utf8'))
        with self.assertRaisesRegex(ValueError, 'downgrade'):
            validate_active_release(current, dict(status='prepared_requested_correction', resources=[]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
