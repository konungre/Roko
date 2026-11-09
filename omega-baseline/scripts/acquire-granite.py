#!/usr/bin/env python3
"""Explicit online acquisition of locked public Granite model data, no remote code."""
import os,json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
os.environ['HF_HOME']=str(ROOT/'models');os.environ['HF_XET_CACHE']=str(ROOT/'models/xet')
os.environ['HF_HUB_DISABLE_TELEMETRY']='1'
from huggingface_hub import hf_hub_download
lock=json.loads((ROOT/'granite-model.lock.json').read_text())
def acquire(repo,revision,name,digest):
 path=Path(hf_hub_download(repo,name,revision=revision,cache_dir=ROOT/'models/hub',token=False))
 with path.open('rb') as stream:
  if hashlib.file_digest(stream,'sha256').hexdigest()!=digest:raise SystemExit('Hash mismatch: '+name)
 print('Verified',repo,name,flush=True)
acquire(lock['repo'],lock['revision'],lock['file'],lock['sha256'])
for name,digest in lock['tokenizer_files'].items():
 acquire(lock['tokenizer_repository'],lock['tokenizer_revision'],name,digest)
