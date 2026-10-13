"""Exercise asset integrity, no-overwrite installs and unsafe-path boundaries."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from install_storage_inventory_assets import BUNDLE, UI_DIRECTORY, install, safe_file, verify


class AssetInstallerTests(unittest.TestCase):
    def test_fresh_repeated_and_custom(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'game'
            count = len(verify())
            receipt = install(target)
            self.assertEqual(receipt['copied'], count)
            self.assertEqual(install(target)['copied'], 0)
            custom = target / UI_DIRECTORY / 'inventoryui/bg.png'
            custom.write_bytes(b'user artwork')
            receipt = install(target)
            self.assertEqual(receipt['preserved_custom'], 1)
            self.assertEqual(custom.read_bytes(), b'user artwork')

    def test_dry_run_does_not_create_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'game'
            receipt = install(target, dry_run=True)
            self.assertFalse(target.exists())
            self.assertTrue(all(row['status'] == 'would-copy' for row in receipt['files']))

    def test_corrupt_bundle_fails_before_any_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle = root / 'bundle'
            shutil.copytree(BUNDLE, bundle)
            (bundle / 'inventoryui/bg.png').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                install(root / 'game', bundle)
            self.assertFalse((root / 'game').exists())

    def test_manifest_rejects_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in ('../outside.png', '/absolute.png', 'C:/outside.png', 'a\\b.png'):
                with self.assertRaises(ValueError):
                    safe_file(root, relative)

    def test_source_dimensions_match_manifest(self):
        rows = verify()
        metadata = json.loads((BUNDLE / 'assets.json').read_text(encoding='utf-8'))
        self.assertEqual(rows, metadata['files'])
        by_path = {row['path']: row for row in rows}
        self.assertEqual((by_path['inventoryui/bg.png']['width'], by_path['inventoryui/bg.png']['height']), (280, 240))
        self.assertEqual((by_path['inventoryui/favorite.png']['width'], by_path['inventoryui/favorite.png']['height']), (32, 30))
        self.assertEqual((by_path['cartui/cart_bg.png']['width'], by_path['cartui/cart_bg.png']['height']), (280, 208))
        self.assertTrue(all(row['path'].endswith(('.png','.bmp')) for row in rows))


if __name__ == '__main__':
    unittest.main()
