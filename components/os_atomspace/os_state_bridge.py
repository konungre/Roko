"""Fixed PeTTa callbacks; source data is never evaluated as executable MeTTa."""
import json
from pathlib import Path
import socket
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from components.os_atomspace.contract import validate,atoms,PHASES,check_rows,digest

packet=None
results={}


def initialize():
    global packet
    try:probe=socket.socket()
    except PermissionError:pass
    else:
        probe.close();raise ValueError('Require inherited network denial')
    raw=sys.stdin.buffer.read(16385)
    if len(raw)>16384:raise ValueError('OS claim byte cap')
    packet=validate(json.loads(raw));return True


def expressions():return atoms(packet)
def phases():return list(PHASES)
def query(phase):
    if phase not in PHASES:raise ValueError('Fixed phase only')
    return '!(rokoOSState '+phase+')'
def observed(phase,rows):
    if phase in results:raise ValueError('Duplicate phase query')
    results[phase]=check_rows(packet,phase,rows);return True
def finish():
    if set(results)!=set(PHASES):raise ValueError('Incomplete native phase query')
    return json.dumps({'schema':'roko.os-state.query.v0','snapshot_sha256':digest(packet),
        'machine':packet['machine'],'boot':packet['boot'],'sequence':packet['sequence'],
        'results':results,'verified_native_os_state':False,'mutation_authority':False,
        'executed_actions':0,'network_denied':True})
