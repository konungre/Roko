"""Static tracked-source inventory; not proof that external/dynamic callers are absent."""
import argparse,ast,hashlib,json,subprocess
from pathlib import Path
TARGETS={'package_planning','package_planning_v2','package_bridge','package_bridge_v2'}
def audit(repository):
 root=Path(repository).resolve();files=subprocess.check_output(['git','ls-files'],cwd=root,text=True).splitlines();imports=[];references=[];errors=[]
 for name in files:
  path=root/name
  if '/evidence/' in name or '/provenance/' in name or path.suffix not in ('.py','.toml','.metta','.sh','.service','.nix') or not path.is_file() or path.stat().st_size>2*1024**2:continue
  text=path.read_text(errors='replace');relevant=any(word in text for word in ('omega_pm','omega-pm','package_planning','package_bridge'))
  if not relevant:continue
  kind='test-or-qualification' if '/tests/' in name or Path(name).name.startswith(('test_','qualify_','audit_')) else 'consumer-or-interface'
  sha=hashlib.sha256(path.read_bytes()).hexdigest()
  references.append({'file':name,'sha256':sha,'category':kind,'lines':[i for i,line in enumerate(text.splitlines(),1) if any(w in line for w in ('omega_pm','omega-pm','package_planning','package_bridge'))]})
  if path.suffix!='.py':continue
  try:tree=ast.parse(text,filename=name)
  except SyntaxError as e:errors.append({'file':name,'line':e.lineno});continue
  for node in ast.walk(tree):
   if isinstance(node,ast.ImportFrom):
    module=node.module or ''
    if module in TARGETS or module=='omega_pm' or module.startswith('omega_pm.'):
     imports.append({'file':name,'line':node.lineno,'module':module,'names':[x.name for x in node.names],'category':kind,'sha256':sha})
   elif isinstance(node,ast.Import):
    for n in node.names:
     if n.name in TARGETS or n.name=='omega_pm' or n.name.startswith('omega_pm.'):
      imports.append({'file':name,'line':node.lineno,'module':n.name,'names':[],'category':kind,'sha256':sha})
 return {'schema':'roko-planner-consumers-v1','repository_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),'worktree_changes_present':bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()),'imports':imports,'text_references':references,'parse_errors':errors,'external_callers_known_complete':False,'dynamic_imports_known_complete':False,'deletion_authorized':False,'license_clearance':False,'scope':'tracked static-source inventory; conditional/test imports do not establish execution'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('repository');p.add_argument('output');a=p.parse_args();r=audit(a.repository)
 with Path(a.output).open('x') as f:json.dump(r,f,indent=2);f.write('\n')
 print(json.dumps({'imports':len(r['imports']),'reference_files':len(r['text_references']),'parse_errors':r['parse_errors']}))
