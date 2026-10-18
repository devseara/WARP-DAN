"""Capture PID-scoped ETW presents with read-only WENV scene guards; never change game state."""
import argparse
import csv
import datetime
import hashlib
import json
import math
import re
from pathlib import Path
import statistics
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
PRESENTMON_SHA256 = '364e5d98d4d134bd54dd25c22ed2ca2f4883f8bc3ed6502bee0c151e3436d30c'


def percentile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower = math.floor(position)
    return values[lower] + (values[math.ceil(position)] - values[lower]) * (position - lower)


def summarize(path, pid):
    with path.open(newline='', encoding='utf-8-sig') as stream:
        rows = list(csv.DictReader(stream))
    assert rows and all(int(row['ProcessID']) == pid for row in rows), 'Empty or wrong-PID capture'
    chains = {}
    for row in rows:
        chains.setdefault(row['SwapChainAddress'], []).append(row)
    main = max(chains, key=lambda key: len(chains[key]))
    selected = chains[main]
    assert len(selected) >= len(rows) * .95, 'Multiple substantial swap chains need manual selection'
    assert len(selected) >= 100, 'Too few frames to summarize'
    assert {row['Runtime'] for row in selected} == {'D3D9'}, 'Unexpected presentation API'
    # The first interval can begin before recording; exclude it without trimming stalls.
    intervals = [float(row['msBetweenPresents']) for row in selected[1:]]
    assert all(math.isfinite(value) and value > 0 for value in intervals)
    qpc = [int(row['QPCTime']) for row in selected]
    assert all(a < b for a, b in zip(qpc, qpc[1:])), 'Nonmonotonic presents'
    duration = float(selected[-1]['TimeInSeconds']) - float(selected[0]['TimeInSeconds'])
    assert abs(sum(intervals) / 1000 - duration) < max(.1, duration * .01), 'Present intervals have gaps'
    worst = sorted(intervals, reverse=True)
    displayed = [float(row['msBetweenDisplayChange']) for row in selected[1:]
                 if row['Dropped'] == '0' and float(row['msBetweenDisplayChange']) > 0]
    gpu = [float(row['msGPUActive']) for row in selected if row.get('msGPUActive') not in (None, '', 'NA')]
    result = {'frames': len(selected), 'duration_seconds': duration,
              'swap_chain': main, 'swap_chain_counts': {key: len(value) for key, value in chains.items()},
              'application_fps': 1000 / statistics.mean(intervals),
              'one_percent_low_fps': 1000 / statistics.mean(worst[:max(1, math.ceil(len(worst) * .01))]),
              'present_interval_ms': {'mean': statistics.mean(intervals), 'median': statistics.median(intervals),
                                      'p95': percentile(intervals, .95), 'p99': percentile(intervals, .99),
                                      'maximum': max(intervals)},
              'frames_over_ms': {str(limit): sum(value > limit for value in intervals)
                                 for limit in [16.667, 33.333, 50, 100]},
              'dropped_present_percent': 100 * sum(row['Dropped'] == '1' for row in selected) / len(selected),
              'display_fps_from_positive_intervals': 1000 / statistics.mean(displayed) if displayed else None,
              'gpu_active_ms_median': statistics.median(gpu) if gpu else None,
              'present_modes': sorted({row['PresentMode'] for row in selected}),
              'qpc_range': [min(qpc), max(qpc)]}
    return result


def effective_profile(server, name):
    import yaml
    profile, visited = {}, set()

    def read(path):
        path = path.resolve()
        assert server.resolve() in path.parents, 'Benchmark profile imports must remain inside the server'
        assert path not in visited, 'Cyclic or repeated config import'
        visited.add(path)
        document = yaml.safe_load(path.read_text(encoding='utf8'))
        for entry in document.get('Body', []):
            if entry.get('Map') == name:
                for key, value in entry.items():
                    if key == 'Weather':
                        profile.setdefault(key, {}).update(value)
                    else:
                        profile[key] = value
        for entry in document.get('Footer', {}).get('Imports', []):
            assert set(entry) == {'Path'}, 'Conditional imports require explicit benchmark review'
            read(server / entry['Path'])

    read(server / 'db/world_environment.yml')
    return profile, {str(path.relative_to(server.resolve())): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in sorted(visited)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pid', type=int)
    parser.add_argument('--condition', choices=['clear', 'rain', 'storm'], required=True)
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--presentmon', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--server', type=Path, default=ROOT.parent / 'BanquetOfHeroes')
    parser.add_argument('--reference', type=Path, help='A prior trial report for matched scene/phase/viewport checks')
    parser.add_argument('--allow-showcase', action='store_true', help='Explicitly label a short-timing capture as a showcase trial')
    args = parser.parse_args()
    assert 5 <= args.seconds <= 120
    assert hashlib.sha256(args.presentmon.read_bytes()).hexdigest() == PRESENTMON_SHA256, 'Use the pinned official PresentMon 2.3.1 console'
    profile, config_hashes = effective_profile(args.server.resolve(), 'prt_fild08')
    if not args.allow_showcase:
        for name, value in [('ClearDuration', 600000), ('RainDuration', 180000), ('StormDuration', 180000), ('StormEvery', 3)]:
            assert profile.get(name) == value, 'Restore normal timings before benchmarking: ' + name
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    session = 'BOHWeather-' + uuid.uuid4().hex
    rows, summaries, files = [], [], []

    def sample(index, seconds):
        target = output / f'state-{index:02d}.json'
        result = subprocess.run([sys.executable, str(ROOT / 'tools/sample_celestial_weather.py'), str(args.pid),
            '--seconds', str(seconds), '--interval', '.1', '--census', '--output', str(target)], capture_output=True)
        (output / f'state-{index:02d}.log').write_bytes(result.stdout + result.stderr)
        assert result.returncode == 0, 'Read-only state capture failed'
        data = json.loads(target.read_text(encoding='utf8'))
        summaries.append(data['summary'])
        rows.extend(data['samples'])
        files.append(target)

    sample(0, 2)
    recorded_start = datetime.datetime.now(datetime.timezone.utc).isoformat()
    context = rows[-1]
    assert context['ready'] and context['map'] == 'prt_fild08' and context['protocol'] == 6
    current_kind = 'storm' if context['weather'] & 256 else 'rain' if context['weather'] & 128 else 'clear'
    assert current_kind == args.condition, 'Requested weather is not active'
    if not args.allow_showcase:
        assert context['phase_duration_ms'] == 3600000, 'Restore one-hour phases before benchmarking'
    frame_csv = output / 'frames.csv'
    command = [str(args.presentmon.resolve()), '--process_id', str(args.pid), '--timed', str(args.seconds),
        '--terminate_after_timed', '--terminate_on_proc_exit', '--no_console_stats', '--no_track_input',
        '--v1_metrics', '--qpc_time', '--session_name', session, '--output_file', str(frame_csv)]
    with (output / 'presentmon.log').open('w', encoding='utf8') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        started = time.monotonic()
        try:
            index = 1
            while time.monotonic() - started < args.seconds:
                sample(index, min(30, max(2, args.seconds - int(time.monotonic() - started) + 1)))
                index += 1
            assert process.wait(timeout=15) == 0, 'PresentMon failed'
        finally:
            if process.poll() is None:
                subprocess.run([str(args.presentmon.resolve()), '--session_name', session,
                                '--terminate_existing_session'], stdout=log, stderr=subprocess.STDOUT, timeout=10)
                process.wait(timeout=10)
    metrics = summarize(frame_csv, args.pid)
    trace_log = (output / 'presentmon.log').read_text(encoding='utf8', errors='replace')
    assert not re.search(r'\b(?:warning|error)\b', trace_log, re.I), 'Review PresentMon warnings/errors before accepting the capture'
    assert metrics['duration_seconds'] >= args.seconds - 2, 'Partial presentation capture'
    frequency = summaries[0]['qpc_frequency']
    assert all(summary['qpc_frequency'] == frequency and not summary['read_errors'] for summary in summaries)
    assert all(summary['weather_payload_matches_disk'] for summary in summaries)
    start, end = metrics['qpc_range']
    guarded = [row for row in rows if start <= row['qpc_before'] <= end]
    assert guarded and guarded[0]['qpc_before'] - start < 5 * frequency
    assert end - guarded[-1]['qpc_after'] < frequency
    assert all(b['qpc_before'] - a['qpc_before'] < 5 * frequency for a, b in zip(guarded, guarded[1:]))
    position, viewport, phase = context['position'], context['viewport'], context['phase']
    native_masks = {row['weather'] & ~(128 | 256 | 512) for row in guarded}
    assert len(native_masks) == 1, 'Native map weather changed during capture'
    native_mask = native_masks.pop()
    for row in guarded:
        kind = 'storm' if row['weather'] & 256 else 'rain' if row['weather'] & 128 else 'clear'
        assert row['ready'] and row['map'] == 'prt_fild08' and row['protocol'] == 6
        assert kind == args.condition, 'Weather changed during capture; retain this data as invalid'
        assert row['phase'] == phase and row['viewport'] == viewport, 'Phase or viewport changed during capture'
        assert row['world'] == context['world'], 'World/session changed during capture'
        assert all(abs(value - position[axis]) <= 1 for axis, value in enumerate(row['position'])), 'Character moved'
    if args.reference:
        reference = json.loads(args.reference.read_text(encoding='utf8'))
        assert reference['client_sha256'] == summaries[0]['client_sha256']
        assert reference['phase'] == phase and reference['viewport'] == viewport
        assert reference['native_weather_mask'] == native_mask and reference['world'] == context['world']
        assert all(abs(value - position[axis]) <= 1 for axis, value in enumerate(reference['position']))
    current_profile, current_hashes = effective_profile(args.server.resolve(), 'prt_fild08')
    assert current_hashes == config_hashes and current_profile == profile, 'Weather configuration changed'
    result = {'passed': True, 'condition': args.condition, 'showcase': args.allow_showcase,
              'client_sha256': summaries[0]['client_sha256'], 'pid': args.pid, 'phase': phase,
              'viewport': viewport, 'position': position, 'qpc_frequency': frequency,
              'world': context['world'], 'native_weather_mask': native_mask,
              'guarded_state_samples': len(guarded), 'configuration_sha256': config_hashes,
              'presentmon_version': '2.3.1', 'presentmon_sha256': PRESENTMON_SHA256,
              'recorded_utc_start': recorded_start,
              'recorded_utc_end': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'weather_payload_matches_disk': True,
              'frames_csv_sha256': hashlib.sha256(frame_csv.read_bytes()).hexdigest(),
              'metrics': metrics, 'operator_controls': 'Camera and foreground focus held fixed by the operator; not programmatically enforced.'}
    (output / 'report.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
