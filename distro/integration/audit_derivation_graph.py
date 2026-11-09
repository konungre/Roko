"""Read-only declared build-graph/local-availability audit, not runtime closure proof."""
import argparse,hashlib,json
from pathlib import Path

def audit(graph_path,identities,output):
 graph_path=Path(graph_path)
 if graph_path.stat().st_size>64*1024**2:raise ValueError('graph bound')
 graph=json.loads(graph_path.read_text());roots=json.loads(Path(identities).read_text())['evaluations'];rows=[]
 for root in roots:
  if root['mode'] not in ('headless','cosmic'):continue
  queue=[root['identities']['imageDerivation']];seen=set();required={(queue[0],'out')};incomplete=[]
  while queue:
   name=queue.pop()
   if name in seen:continue
   seen.add(name)
   if name not in graph:incomplete.append(name);continue
   for child,spec in graph[name]['inputDrvs'].items():
    if isinstance(spec,list):outputs=spec
    else:
     outputs=spec['outputs']
     if spec.get('dynamicOutputs'):incomplete.append('dynamic:'+child)
    required.update((child,n) for n in outputs);queue.append(child)
  missing=[];present=0;unknown=[]
  for name,outname in sorted(required):
   info=graph.get(name,{}).get('outputs',{}).get(outname,{})
   path=info.get('path')
   if not path:unknown.append([name,outname]);continue
   if Path(path).exists():present+=1
   else:missing.append({'derivation':name,'output':outname,'path':path,'name':graph[name]['env'].get('name',Path(path).name)})
  groups={}
  for role,needle in [('cosmic','cosmic'),('iso-tool','xorriso'),('squashfs','squashfs'),('init-system','systemd'),('python','python3-'),('shell','bash-')]:groups[role]=[m for m in missing if needle in m['name'].lower()][:3]
  rows.append({'mode':root['mode'],'declared_derivations_reachable':len(seen),'required_output_pairs':len(required),'required_outputs_present':present,'required_outputs_missing':len(missing),'unknown_outputs':unknown,'incomplete_metadata':incomplete,'missing_examples':groups})
 report={'roots':rows,'metadata_nodes':len(graph),'graph_bytes':graph_path.stat().st_size,'graph_sha256':hashlib.sha256(graph_path.read_bytes()).hexdigest(),'scope':'declared source-build graph and requested outputs; includes bootstrap/fetch derivations; NOT runtime closure or binary-cache availability/size','substituters_queried':False,'packages_built':False,'host_activation':False}
 with Path(output).open('x') as f:json.dump(report,f,indent=2);f.write('\n')
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('graph');p.add_argument('identities');p.add_argument('output');a=p.parse_args();r=audit(a.graph,a.identities,a.output);print(json.dumps([{k:v for k,v in x.items() if k!='missing_examples'} for x in r['roots']]))
