"""One fixed JSON request on stdin, one bounded JSON result on stdout."""
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys

INSTALL = Path('/opt/roko/desktop/live-request')

def main():
    if len(sys.argv) != 1 or Path(__file__).resolve() != INSTALL / 'cli.py':
        raise ValueError('Only the installed fixed live endpoint may run')
    sys.path.insert(0, str(INSTALL))
    import live_contract
    import live_controller
    report = live_controller.result_base()
    try:
        request = live_contract.decode_request(sys.stdin.buffer.read(live_contract.INPUT_CAP + 1))
        with redirect_stdout(sys.stderr):
            report = live_controller.run(request)
    except BaseException as exc:
        report['error'] = type(exc).__name__ + ': ' + str(exc)[:1000]
    raw = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if len(raw) > live_controller.RESULT_CAP:
        raise ValueError('Live result output cap')
    sys.stdout.buffer.write(raw + b'\n')
    sys.stdout.buffer.flush()
    # A checker rejection is a completed request, not a transport failure.
    return 0 if report['error'] is None else 1

if __name__ == '__main__':
    raise SystemExit(main())
