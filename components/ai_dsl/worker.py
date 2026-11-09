"""Execute unchanged upstream AI-DSL definitions; never execute synthesized services."""
import hashlib
import json
from pathlib import Path
import socket
import resource
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parents[1]))
from contract import validate, GOALS
from components.nars_hyperon.source.runtime import verify


def main():
    manifest = json.loads(Path(sys.argv[1]).read_bytes())
    verify(manifest, sys.argv[2])
    if (resource.getrlimit(resource.RLIMIT_CPU) != (5, 5)
            or resource.getrlimit(resource.RLIMIT_AS) != (536870912, 536870912)):
        raise ValueError('Require bounded native CPU/address space')
    try:
        probe = socket.socket()
    except PermissionError:
        pass
    else:
        probe.close()
        raise ValueError('Require native network denial')
    raw = sys.stdin.buffer.read(1025)
    if len(raw) > 1024:
        raise ValueError('Request byte cap')
    request = validate(json.loads(raw))
    upstream = ROOT / 'upstream'
    lock = json.loads((upstream/'source-lock.json').read_bytes())
    for name, row in lock['files'].items():
        data = (upstream/name).read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Upstream source identity mismatch')
    # Preserve the exact prefix; omit only upstream's unbounded demo invocations.
    source = (upstream/'rse-combinator-xp.metta').read_text()
    marker = ';;;;;;;;;;\n;; Test ;;\n;;;;;;;;;;'
    if source.count(marker) != 1:
        raise ValueError('Upstream demo boundary changed')
    definitions = source.split(marker)[0]
    from hyperon import MeTTa, Environment, ExpressionAtom, SymbolAtom
    runner = MeTTa(env_builder=Environment.custom_env(config_dir=None, create_config=False))
    loaded = runner.run(definitions)
    if any(str(atom) != '()' for row in loaded for atom in row):
        raise ValueError('Upstream definition load failed')
    start, end, _ = GOALS[request['goal']]
    # All substituted values come from closed enums and bounded integer validation.
    query = f'!(unique (bc &kb (fromNumber {request["depth"]}) (: $prg (-> {start} {end}))))'
    rows = runner.run(query)
    if len(rows) != 1:
        raise ValueError('Unexpected native query count')
    def tree(atom):
        if isinstance(atom, ExpressionAtom):
            return [tree(child) for child in atom.get_children()]
        if isinstance(atom, SymbolAtom):
            return atom.get_name()
        raise ValueError('Native proof contains unsupported atom')
    proofs = [tree(atom) for atom in rows[0]]
    verify(manifest, sys.argv[2])
    print(json.dumps({'request':request, 'proofs':proofs, 'query':query,
                      'definitions_sha256':hashlib.sha256(definitions.encode()).hexdigest(),
                      'upstream_commit':lock['commit'], 'network_denied':True,
                      'executed_services':0, 'executed_actions':0}))


if __name__ == '__main__':
    main()
