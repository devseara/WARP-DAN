#!/usr/bin/env python3
"""Execute the canonical-name PE regressions, including rename and UI footers.

--before supplies the original Main 2025-07-16 client for the footer regression.
Select --npc-overlay only when AlwaysShowNpcName is included in the tested build.
These checks execute native code with stubbed services; they do not prove live UI.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pe', type=Path, required=True)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--deps', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--npc-overlay', action='store_true')
    args = parser.parse_args()
    for path in (args.pe, args.before):
        if not path.is_file():
            parser.error(f'PE does not exist: {path}')
    args.output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parent
    suites = [
        'verify_extname_cache_pe.py', 'verify_extname_party_pe.py',
        'verify_character_create_actions_pe.py', 'verify_character_create_callback_pe.py',
        'verify_character_select_footer_pe.py', 'verify_extname_character_rename_pe.py',
        'verify_extname_companion_pe.py', 'verify_extname_companion_rename_pe.py',
        'verify_extname_social_reuse_pe.py', 'verify_extname_mail_pe.py',
        'verify_extname_quest_pe.py', 'verify_extname_star_pe.py',
        'verify_extname_battleground_pe.py', 'verify_extname_guild_log_pe.py',
        'verify_extname_boss_tracker_pe.py', 'verify_auxiliary_identity_pe.py',
        'verify_name_eh_frames_pe.py', 'verify_legacy_creation_enter_pe.py',
    ]
    if args.npc_overlay:
        suites.append('verify_extname_npc_pe.py')
    result = {
        'pe': str(args.pe.resolve()),
        'sha256': hashlib.sha256(args.pe.read_bytes()).hexdigest(),
        'before': str(args.before.resolve()),
        'npc_overlay': args.npc_overlay,
        'suites': [],
    }
    for suite in suites:
        command = [sys.executable, '-u', str(root / suite)]
        command += ([str(args.pe)] if suite == 'verify_extname_cache_pe.py'
                    else ['--pe', str(args.pe)])
        command += ['--deps', str(args.deps)]
        if suite == 'verify_character_select_footer_pe.py':
            command += ['--before', str(args.before), '--report',
                        str(args.output / 'character-footer.json')]
        try:
            process = subprocess.run(command, capture_output=True, text=True,
                                     encoding='utf-8', errors='replace', timeout=600)
            code, output = process.returncode, process.stdout + process.stderr
        except subprocess.TimeoutExpired as error:
            code = 124
            chunks = [error.stdout or b'', error.stderr or b'']
            output = ''.join(x.decode('utf-8', 'replace') if isinstance(x, bytes) else x
                             for x in chunks) + '\nTIMEOUT after 600 seconds\n'
        log = args.output / (Path(suite).stem + '.log')
        log.write_text(output, encoding='utf-8')
        result['suites'].append({'suite': suite, 'passed': code == 0,
                                'returncode': code, 'log': str(log.resolve())})
        print(('PASS ' if code == 0 else 'FAIL ') + suite, flush=True)
        if code:
            print(output[-5000:], flush=True)
    result['passed'] = all(row['passed'] for row in result['suites'])
    (args.output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f"{'PASS' if result['passed'] else 'FAIL'} {len(suites)} canonical-name suites", flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
