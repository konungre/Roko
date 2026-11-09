"""Read-only plan for the exact future disk-backed root. Never creates an image."""
import hashlib
import json
from pathlib import Path
import shutil
import stat

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE=ROOT/'build/cosmic-files-portals-guest'
BASE_ID='17f986b6887a9b5554cd91c1854458307d961faa7966c2e0b5797994881f0566'
BASE_SHA='aef59dfa4d9b4c3603906a96ecf48be6ad3b7694e7ae94776e183fd7103d4092'
ROOT_BYTES=3*1024**3
RESERVE_BYTES=4*1024**3
FUTURE_MODEL_BYTES=0  # Qwen outputs already occupy space; parent explicitly confirmed no double counting.

def summary():
    raw=(BASE/'manifest.json').read_bytes();manifest=json.loads(raw)
    if manifest['build_id']!=BASE_ID or manifest['initramfs_sha256']!=BASE_SHA:
        raise ValueError('Fixed source runtime changed; coordinate a new plan')
    entries=manifest['entries']
    for name,e in entries.items():
        if e['uid']!=0 or e['gid']!=0 or e['mode'] & 0o6000:
            raise ValueError('Unexpected owner/setid; requires explicit preservation design: '+name)
        kind=stat.S_IFMT(e['mode'])
        if kind not in (stat.S_IFREG,stat.S_IFDIR,stat.S_IFLNK) and name!='dev/console':
            raise ValueError('Unexpected special inode: '+name)
    payload=sum(e['bytes'] for e in entries.values())
    rounded=sum((e['bytes']+4095)//4096*4096 for e in entries.values())
    staging=rounded+len(entries)*2048+16*1024**2
    required=ROOT_BYTES+staging+RESERVE_BYTES+FUTURE_MODEL_BYTES
    free=shutil.disk_usage(ROOT).free
    return {'schema':1,'source_build_id':BASE_ID,'source_archive_sha256':BASE_SHA,
            'source_manifest_sha256':hashlib.sha256(raw).hexdigest(),'source_entries':len(entries),
            'payload_bytes':payload,'block_rounded_payload_bytes':rounded,'root_image_bytes':ROOT_BYTES,
            'streaming_required_free_bytes':ROOT_BYTES+RESERVE_BYTES+FUTURE_MODEL_BYTES,
            'streaming_space_budget_passed':free>=ROOT_BYTES+RESERVE_BYTES+FUTURE_MODEL_BYTES,
            'estimated_staging_bytes':staging,'reserve_bytes':RESERVE_BYTES,'future_model_reserve_bytes':FUTURE_MODEL_BYTES,'required_free_bytes':required,
            'available_bytes':free,'space_budget_passed':free>=required,
            'source_capabilities':'newc manifest has no xattrs/capabilities; do not infer package-level preservation',
            'source_guest_owners':'all 0:0; no setuid/setgid',
            'population':'Prefer owned uid0/gid0 tar via approved mke2fs -d/libarchive; plain host directory -d requires explicit ownership repair',
            'assembly_permitted':False,'formatting_permitted':False,'boot_tested':False}
if __name__=='__main__':print(json.dumps(summary(),indent=2))
