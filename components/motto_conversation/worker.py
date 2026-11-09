"""One typed Motto call over bounded JSON lines, with an externally supplied model."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from components.nars_hyperon.source.runtime import verify


def read(limit):
    raw = sys.stdin.buffer.readline(limit + 1)
    if not raw.endswith(b'\n') or len(raw) > limit:
        raise ValueError('Motto protocol byte cap or incomplete line')
    return json.loads(raw)


def main():
    manifest = json.loads(Path(sys.argv[1]).read_bytes())
    verify(manifest, sys.argv[2])
    from adapter import chat
    request = read(65536)
    if set(request) != {'messages', 'snapshot_sha256'}:
        raise ValueError('Motto request schema')
    def model(messages):
        print(json.dumps({'stage': 'model_request', 'messages': messages,
                          'snapshot_sha256': request['snapshot_sha256']}), flush=True)
        response = read(262144)
        if set(response) != {'text'}:
            raise ValueError('Motto model response schema')
        return response['text']
    text = chat(request['messages'], model)
    verify(manifest, sys.argv[2])
    print(json.dumps({'stage': 'completed', 'text': text,
                      'snapshot_sha256': request['snapshot_sha256']}), flush=True)


if __name__ == '__main__':
    main()
