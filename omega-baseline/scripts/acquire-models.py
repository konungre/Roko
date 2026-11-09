#!/usr/bin/env python3
"""Explicit online acquisition of pinned public model data, never remote code."""
from pathlib import Path
import hashlib,json,os
ROOT=Path(__file__).resolve().parents[1]
os.environ["HF_HOME"]=str(ROOT/"models")
os.environ["HF_XET_CACHE"]=str(ROOT/"models/xet")
os.environ["HF_HUB_DISABLE_TELEMETRY"]="1"
from huggingface_hub import snapshot_download
models=[('intfloat/e5-large-v2','f169b11e22de13617baa190a028a32f3493550b6'),('Qwen/Qwen2.5-0.5B-Instruct','7ae557604adf67be50417f59c2c2f167def9a775')]
lock=ROOT/"models.lock.json"
known={r["repo"]:r for r in json.loads(lock.read_text())} if lock.exists() else {}
records=dict(known)
for repo,revision in models:
 path=Path(snapshot_download(repo,revision=revision,cache_dir=ROOT/'models/hub',token=False,allow_patterns=['*.json','*.safetensors','*.txt','README.md','LICENSE','LICENSE*'],max_workers=2))
 files={str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}
 if repo in known and (known[repo]['revision'] != revision or known[repo]['files'] != files):
  raise SystemExit('Model content differs from existing lock: '+repo)
 records[repo]={'repo':repo,'revision':revision,'snapshot':str(path.relative_to(ROOT)),'files':files}
 (ROOT/'models.lock.json').write_text(json.dumps(list(records.values()),indent=2)+'\n')
 print(repo,revision,len(files),'files',flush=True)
