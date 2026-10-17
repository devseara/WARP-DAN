"""Summarize live cleanup/memory evidence; require a full normal weather sequence before acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def mib(value):
    return round(value / 1048576, 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--progress', action='store_true', help='Report provisional coverage without accepting an incomplete soak')
    args = parser.parse_args()
    directory = args.directory.resolve()
    rows = [json.loads(line) for line in (directory / 'journal.jsonl').read_text().splitlines() if line]
    assert rows, 'No completed sampling chunks'
    segments = []
    for row in rows:
        last = row['last']
        phase = 'storm' if last['weather'] & 256 else 'rain' if last['weather'] & 128 else 'clear'
        if not segments or segments[-1]['phase'] != phase:
            segments.append({'phase': phase, 'start_minutes': row['soak_elapsed_seconds'] / 60,
                             'end_minutes': row['soak_elapsed_seconds'] / 60, 'rows': []})
        segments[-1]['end_minutes'] = row['soak_elapsed_seconds'] / 60
        segments[-1]['rows'].append(row)
    clear = [row for row in rows if row['soak_elapsed_seconds'] >= 300 and row['weather_masks'] == [0]
             and row['owned_census'] and row['owned_census'].get('stable')
             and not row['owned_census']['parents'] and not row['owned_census']['primitives']]
    baselines = []
    for segment in segments:
        eligible = [row for row in segment['rows'] if row in clear]
        if len(eligible) >= 2:
            baselines.append({'start_minutes': round(eligible[0]['soak_elapsed_seconds'] / 60, 2),
                              'end_minutes': round(eligible[-1]['soak_elapsed_seconds'] / 60, 2),
                              'median_private_mib': mib(statistics.median(row['private_bytes'] for row in eligible)),
                              'median_handles': statistics.median(row['handles'] for row in eligible)})
    active = [segment['phase'] for segment in segments if segment['phase'] != 'clear']
    sequence = any(active[i:i + 3] == ['rain', 'rain', 'storm'] for i in range(len(active) - 2))
    cleanup = []
    for before, after in zip(segments, segments[1:]):
        if before['phase'] != 'clear' and after['phase'] == 'clear':
            stable = [row for row in after['rows'] if row['weather_masks'] == [0]
                      and row['owned_census'] and row['owned_census'].get('stable')]
            cleanup.append({'from': before['phase'], 'clear_minutes': round(after['start_minutes'], 2),
                            'verified': bool(stable) and all(not row['owned_census']['parents']
                                                           and not row['owned_census']['primitives'] for row in stable)})
    census = [row['owned_census'] for row in rows if row['owned_census'] and row['owned_census'].get('stable')]
    positions = [row['last'].get('position') for row in rows]
    stationary = bool(positions[0]) and all(position and all(abs(value - positions[0][axis]) <= 1
                    for axis, value in enumerate(position)) for position in positions)
    growth = baselines[-1]['median_private_mib'] - baselines[0]['median_private_mib'] if len(baselines) >= 2 else None
    report = {'provisional': args.progress, 'elapsed_minutes': round(rows[-1]['soak_elapsed_seconds'] / 60, 2),
              'chunks': len(rows), 'sampled_seconds': sum(row['seconds'] for row in rows),
              'sequence_observed': sequence, 'active_segments': active,
              'segments': [{key: value for key, value in segment.items() if key != 'rows'} for segment in segments],
              'cleanup_transitions': cleanup, 'clear_baselines_after_warmup': baselines,
              'last_minus_first_clear_private_mib': round(growth, 3) if growth is not None else None,
              'private_mib_range': [mib(min(row['private_bytes'] for row in rows)), mib(max(row['private_bytes'] for row in rows))],
              'handles_range': [min(row['handles'] for row in rows), max(row['handles'] for row in rows)],
              'max_owned_parents': max((row['parents'] for row in census), default=None),
              'max_owned_primitives': max((row['primitives'] for row in census), default=None),
              'stable_census_chunks': len(census), 'read_errors': sum(len(row['read_errors']) for row in rows),
              'updating_chunks': sum(row['observed_frame_tick_changes'] > 1 for row in rows),
              'client_hashes': sorted({row['client_sha256'] for row in rows}),
              'journal_sha256': hashlib.sha256((directory / 'journal.jsonl').read_bytes()).hexdigest(),
              'stationary_control_retained': stationary,
              'not_a_gpu_or_absolute_heap_leak_proof': True}
    if not args.progress:
        collection = json.loads((directory / 'collection.json').read_text())
        assert collection['completed'] and collection['seconds'] >= 3599 and not collection['failures']
        assert stationary, 'Movement invalidates comparable scenery/cache residency baselines'
        assert sequence and sum(item['verified'] for item in cleanup) >= 3, 'Incomplete normal-cycle cleanup coverage'
        assert all(item['verified'] for item in cleanup)
        assert len(census) >= len(rows) * .95 and report['max_owned_parents'] <= 1 and report['max_owned_primitives'] <= 96
        assert report['updating_chunks'] >= len(rows) * .95 and len(report['client_hashes']) == 1
        assert all(row['last'].get('phase_duration_ms') == 3600000 for row in rows)
        assert len(baselines) >= 3, 'Need comparable clear windows after warmup'
        # This is a bounded screening criterion, not a universal native-heap leak threshold.
        assert growth is not None and growth <= 16, 'More than 16 MiB retained across comparable late clear baselines; investigate'
        assert baselines[-1]['median_handles'] - baselines[0]['median_handles'] <= 8, 'Unexplained handle accumulation'
        assert report['read_errors'] == 0
        report['passed'] = True
    (directory / ('analysis-progress.json' if args.progress else 'analysis.json')).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
