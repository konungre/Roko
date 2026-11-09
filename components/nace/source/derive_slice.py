"""Generate, but never import or execute, the exact reviewed NACE function slice."""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = '361fddf5f6885a60b6d5e0d179e0394da876df4c'
SELECTION = {
    'nace.py': ('NACE_Predict', '_MatchHypotheses', '_RuleApplicable'),
    'hypothesis.py': ('Hypothesis_TruthValue', 'Hypothesis_TruthExpectation',
                      'Hypothesis_Choice', '_AddEvidence'),
}
HEADER = '''# Generated from exact MIT-licensed upstream function bytes; do not edit.
# No upstream module imports or top-level simulation initialization are retained.
# Fixed 3x3 fixture world. Operation names are inert strings, never callables.
from copy import deepcopy
BOARD, VALUES, TIMES = 0, 1, 2
width, height = 3, 3
'''

def derive():
    lock = json.loads((ROOT / 'proof/upstream-lock.json').read_text())
    if lock['commit'] != PIN:
        raise ValueError('wrong source pin')
    pieces = [HEADER]
    records = []
    for filename, names in SELECTION.items():
        p = ROOT / 'upstream' / filename
        raw = p.read_bytes()
        entry = next(x for x in lock['files'] if x['path'] == 'upstream/' + filename)
        if hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('source hash mismatch')
        source = raw.decode('utf-8')
        lines = source.splitlines(keepends=True)
        tree = ast.parse(source)
        # Preserve the entire copyright and MIT notice in each source module.
        notice = ''.join(lines[tree.body[0].lineno - 1:tree.body[0].end_lineno])
        pieces.append(notice.rstrip('\n') + '\n\n')
        for name in names:
            node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
            if node.decorator_list:
                raise ValueError('unexpected decorator')
            part = ''.join(lines[node.lineno - 1:node.end_lineno])
            pieces.append(part.rstrip('\n') + '\n\n')
            records.append({'upstream_file': filename, 'function': name,
                            'first_line': node.lineno, 'last_line': node.end_lineno,
                            'sha256': hashlib.sha256(part.encode()).hexdigest(),
                            'bytes': len(part.encode())})
    return ''.join(pieces).rstrip('\n') + '\n', records

if __name__ == '__main__':
    data, records = derive()
    (ROOT / 'source/nace_slice.py').write_text(data)
    (ROOT / 'proof/slice-lineage.json').write_text(json.dumps({
        'commit': PIN, 'functions': records,
        'slice_sha256': hashlib.sha256(data.encode()).hexdigest(),
        'bindings': {'BOARD': 0, 'VALUES': 1, 'TIMES': 2, 'width': 3, 'height': 3},
        'execution': 'not executed by derivation'}, indent=2) + '\n')
