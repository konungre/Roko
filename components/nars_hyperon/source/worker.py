"""Actual pinned NAL-1 evaluation. No request text is parsed as MeTTa code."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from contract import canonical,parse_request,input_values,response_from_rows,MAX_REQUEST
from hyperon import MeTTa,Environment,E,S,ValueAtom,ExpressionAtom,SymbolAtom,GroundedAtom
import hyperon

UPSTREAM=Path(__file__).resolve().parents[1]/'upstream'
PINS={'truthfunctions.metta':'0c13d3f9b4859763ba5f9a36b29d44ee926adbe6526c5dab7fb078419879dccf',
      'nal1.metta':'205f789b4c92d072fc960c7c2093a7ae622b1f298765d4a599115ed08616772f'}


def executable_maps():
    paths=set()
    for line in Path('/proc/self/maps').read_text().splitlines():
        fields=line.split(maxsplit=5)
        if len(fields)==6 and 'x' in fields[1] and fields[5].startswith('/'):
            path=Path(fields[5])
            if not path.is_file():raise ValueError('Unresolvable executable mapping')
            paths.add(str(path.resolve()))
    return sorted(paths)


def children(atom,count):
    if not isinstance(atom,ExpressionAtom):raise ValueError('Native expression required')
    values=atom.get_children()
    if len(values)!=count:raise ValueError('Native expression shape')
    return values


def symbol(atom):
    if not isinstance(atom,SymbolAtom):raise ValueError('Native symbol required')
    return atom.get_name()


def number(atom):
    if not isinstance(atom,GroundedAtom):raise ValueError('Evaluated native number required')
    value=atom.get_object().value
    if type(value) not in (int,float):raise ValueError('Native number type')
    return value


def main():
    if hyperon.__version__!='0.2.10':raise ValueError('Runtime version mismatch')
    runner=MeTTa(env_builder=Environment.custom_env(config_dir=None,create_config=False))
    if sys.argv[1:]==['--probe']:
        print(json.dumps({'runtime_maps':executable_maps(),'hyperon_version':hyperon.__version__}))
        return
    if sys.argv[1:]:raise ValueError('No worker options accepted')
    request=parse_request(sys.stdin.buffer.read(MAX_REQUEST+1))
    for name,expected in PINS.items():
        raw=(UPSTREAM/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Upstream source mismatch')
        if runner.run(raw.decode())!=[]:raise ValueError('Unexpected import execution result')
    f1,c1,f2,c2=[ValueAtom(x/1000) for x in input_values(request)]
    expression=E(S('|-'),E(E(S('n0'),S('-->'),S('n1')),E(f1,c1)),
        E(E(S('n1'),S('-->'),S('n2')),E(f2,c2)))
    native=runner.evaluate_atom(expression)
    if len(native)!=2:raise ValueError('Exactly two native conclusions required')
    rows=[]
    for atom in native:
        statement,truth=children(atom,2)
        subject,copula,predicate=children(statement,3)
        if symbol(copula)!='-->':raise ValueError('Unexpected native relation')
        indexes={'n0':0,'n2':2};f,c=children(truth,2)
        rows.append({'subject_index':indexes[symbol(subject)],'predicate_index':indexes[symbol(predicate)],
            'frequency':number(f),'confidence':number(c)})
    packet={'schema':'roko.nars.hyperon-observation.v1','request':request,
        'native_rows':rows,'response':response_from_rows(request,rows),
        'upstream_commit':'945e2f83711b143e3f6e2eb112cc40c4f531c6f2',
        'hyperon_version':hyperon.__version__,'strict_imports':list(PINS),
        'runtime_maps':executable_maps(),
        'executed_actions':0,'full_nars':False}
    raw=canonical(packet)
    if len(raw)>16384:raise ValueError('Native packet cap')
    sys.stdout.buffer.write(raw+b'\n')


if __name__=='__main__':main()
