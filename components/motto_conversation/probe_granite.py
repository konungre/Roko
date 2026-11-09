"""Explicit native smoke probe; not an Omega/v2 integration qualification.

Run under omega-baseline/scripts/no-network.py with a qualified local fresh
profile. The model callback is FreshProvider.chat, never an echo or fixture.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'conversation'))
from fresh import FreshProvider, load_profile
from recovered import render
from adapter import chat


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profile', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    started = time.monotonic()
    provider = None
    record = {'scope': 'native-motto-granite-transport-smoke', 'status': 'failed',
              'omega_integration': False, 'durable_v2_integration': False, 'executed_actions': 0}
    try:
        profile = load_profile(args.profile)
        provider = FreshProvider(profile)
        messages = [{'role': 'system', 'content': 'Answer in one short sentence.'},
                    {'role': 'user', 'content': 'What is two plus three?'}]
        result = chat(messages, provider.chat)
        if (len(provider.receipts) != 1
                or provider.receipts[0]['prompt_sha256'] != hashlib.sha256(render(messages).encode()).hexdigest()
                or provider.receipts[0]['stdout'] != result):
            raise ValueError('Motto/Granite transport evidence mismatch')
        record.update(status='passed', messages=messages, text=result,
                      generation=provider.last_generation, native_receipts=provider.receipts)
        root = Path(__file__).resolve().parent
        record['adapter_files'] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in root.rglob('*') if p.is_file()}
    except BaseException as error:
        record['error'] = repr(error)
        if provider is not None:
            record['native_receipts'] = provider.receipts
        raise
    finally:
        try:
            if provider is not None:
                provider.close()
        finally:
            record['seconds'] = time.monotonic() - started
            Path(args.output).write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
