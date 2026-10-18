"""Check weighted FPS/tail metrics, context separation and inherited weather config."""
import csv
from pathlib import Path
import tempfile
import unittest

from capture_celestial_frame_times import effective_profile, summarize


def checked_temporary_directory():
    root = Path(__file__).resolve().parents[1] / 'Outputs/CelestialDial/frame-times/test-temp'
    root.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.TemporaryDirectory(dir=root)
    assert root.resolve() in Path(temporary.name).resolve().parents
    return temporary


class FrameTimeChecks(unittest.TestCase):
    def fixture(self, path, *, second_chain=False, wrong_pid=False):
        fields = ['ProcessID', 'SwapChainAddress', 'Runtime', 'TimeInSeconds', 'QPCTime',
                  'msBetweenPresents', 'Dropped', 'msBetweenDisplayChange', 'msGPUActive', 'PresentMode']
        with path.open('w', newline='', encoding='utf8') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            elapsed = 0
            for index in range(201):
                interval = 100 if index >= 199 else 10
                if index:
                    elapsed += interval
                row = {'ProcessID': 8 if wrong_pid and index == 100 else 7,
                       'SwapChainAddress': '0x1', 'Runtime': 'D3D9', 'TimeInSeconds': elapsed / 1000,
                       'QPCTime': 100000 + elapsed * 10000, 'msBetweenPresents': interval,
                       'Dropped': index % 2, 'msBetweenDisplayChange': 20 if index % 2 == 0 else 0,
                       'msGPUActive': 2.5, 'PresentMode': 'Composed: Copy with GPU GDI'}
                writer.writerow(row)
                if second_chain:
                    writer.writerow({**row, 'SwapChainAddress': '0x2'})

    def test_presentation_fps_retains_slow_frames(self):
        with checked_temporary_directory() as directory:
            path = Path(directory) / 'frames.csv'
            self.fixture(path)
            result = summarize(path, 7)
            self.assertAlmostEqual(result['application_fps'], 1000 / 10.9)
            self.assertEqual(result['one_percent_low_fps'], 10)
            self.assertEqual(result['present_interval_ms']['maximum'], 100)
            self.assertEqual(result['frames_over_ms']['50'], 2)
            self.assertEqual(result['display_fps_from_positive_intervals'], 50)
            self.assertGreater(result['dropped_present_percent'], 49)

    def test_wrong_pid_and_ambiguous_swap_chain_are_rejected(self):
        with checked_temporary_directory() as directory:
            path = Path(directory) / 'frames.csv'
            for options in [{'wrong_pid': True}, {'second_chain': True}]:
                self.fixture(path, **options)
                with self.assertRaises(AssertionError):
                    summarize(path, 7)

    def test_imports_preserve_unspecified_weather_flags(self):
        with checked_temporary_directory() as directory:
            root = Path(directory)
            (root / 'db/import').mkdir(parents=True)
            (root / 'db/world_environment.yml').write_text('''Body:
  - Map: prt_fild08
    ClearDuration: 600000
    Weather:
      Rain: true
      Thunderstorm: true
Footer:
  Imports:
    - Path: db/import/world_environment.yml
''', encoding='utf8')
            (root / 'db/import/world_environment.yml').write_text('''Body:
  - Map: prt_fild08
    RainDuration: 30000
    Weather:
      Thunderstorm: false
''', encoding='utf8')
            profile, hashes = effective_profile(root, 'prt_fild08')
            self.assertEqual(profile['ClearDuration'], 600000)
            self.assertEqual(profile['RainDuration'], 30000)
            self.assertEqual(profile['Weather'], {'Rain': True, 'Thunderstorm': False})
            self.assertEqual(len(hashes), 2)


if __name__ == '__main__':
    unittest.main()
