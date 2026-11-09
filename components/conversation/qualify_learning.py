"""Add reviewed local component closures to a freshly prepared profile."""
import argparse
import hashlib
import json
from pathlib import Path
from fresh import load_profile
from learning import validate_profile


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',type=Path,required=True)
    for name in ('metamo','airis','nace','guard'):p.add_argument('--'+name+'-manifest',type=Path,required=True)
    p.add_argument('--ai-dsl-manifest',type=Path)
    p.add_argument('--evidence-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();profile=load_profile(a.profile);components={}
    names=['metamo','airis','nace','guard']+(['ai_dsl'] if a.ai_dsl_manifest else [])
    for name in names:
        path=getattr(a,name+'_manifest').resolve(strict=True);m=json.loads(path.read_bytes())
        for file,h in m['files'].items():
            if sha(file)!=h:raise ValueError('Changed component closure: '+file)
            if file in profile['files'] and profile['files'][file]!=h:raise ValueError('Conflicting closure pin')
            profile['files'][file]=h
        profile['files'][str(path)]=sha(path)
        if name!='guard':components[name]={'manifest':str(path),'sha256':sha(path)}
    profile['learning_components']={'components':components,'evidence_root':str(a.evidence_root.absolute()),
        'guard_manifest':str(a.guard_manifest.resolve()),'guard_admission':sha(a.guard_manifest)}
    validate_profile(profile)
    with a.output.open('x') as stream:json.dump(profile,stream,indent=2);stream.write('\n')
    load_profile(a.output);print(a.output)
if __name__=='__main__':main()
