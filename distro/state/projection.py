"""Project the latest durable real observation, never a simulation."""
from facts import Fact,Stage
from ledger import Ledger
def latest_atom(path,machine,backend):
 ledger=Ledger(path)
 try:row=ledger.latest(machine,backend)
 finally:ledger.close()
 if row is None:raise ValueError('missing observation')
 body,_=row
 if body['mode']!='observed':raise ValueError('simulation is not a real observation')
 f=dict(body['fact']);f.pop('schema');f['stage']=Stage(f['stage'])
 return Fact(**f).atom()
