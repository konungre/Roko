import json,pathlib,hashlib,shutil
R=pathlib.Path(__file__).resolve().parents[2];O=pathlib.Path(__file__).parent
load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def rec(p):return {'path':str(p.relative_to(R)),'sha256':sha(p)}
a=load(O/'acquired-sources.json');auth=load(O/'authentication.json');i=load(O/'inventory.json')
assert a['complete'] and len(a['files'])==55 and not a['errors']
for f in a['files']:assert sha(R/f['path'])==f['sha256']
assert sha(R/'build/cosmic-files-portals-guest/manifest.json')==i['files_image']['sha256']
assert sha(R/'build/disk-root-guest/root-source.json')==i['root_source']['sha256']
assert sha(R/'build/roko-corner-guest/bootstrap.json')==i['corner_bootstrap']['sha256']
r={'schema':1,'scope':'Files/portal incremental source acquisition and bounded authentication; no root disk scan, source execution, build or new boot claim.','files_build_id':i['files_build_id'],'root_build_id':i['root_build_id'],'corner_delta_id':i['corner_delta_id'],'bound_manifests':[i['files_image'],i['root_source'],i['corner_bootstrap']],'source_file_count':55,'source_package_count':16,'verified_source_bytes':sum(f['bytes'] for f in a['files']),'remaining_planned_source_files':0,'runtime_owner_package_count':97,'notice_only_package_count':382,'count_scope':'Overlay-local; includes inherited overlap, not whole image totals.','authenticated_runtime_package_mappings':97,'new_runtime_archive_count':len(auth['new_runtime_archives_verified']),'new_runtime_archive_bytes':sum(p['bytes'] for p in auth['new_runtime_archives_verified']),'authentication':rec(O/'authentication.json'),'acquisition':rec(O/'acquired-sources.json'),'inventory':rec(O/'inventory.json'),'original_budget_unchanged':{'successful_unique_bytes':940273510,'conservative_bound_bytes':1059760437,'remaining_1GiB_bytes':13981387},'separate_incremental_budget':{'cap_bytes':26214400,'received_body_bytes_including_retries':a['incremental_received_bytes'],'remaining_bytes':26214400-a['incremental_received_bytes'],'ledger':rec(O/'incremental-download-ledger.json'),'meter_scope':'Downloaded HTTP response body bytes, not TLS/header overhead.'},'free_disk_bytes':shutil.disk_usage(R).free,'required_free_reserve_bytes':4294967296,'prior_audits':[rec(R/'boot/cosmic-session-source-closure.json'),rec(R/'boot/avatar-source-closure.json')],'limits':['Prior verified archive/source caches reused, not all rehashed this pass.','New selected .deb complete hashes and control ownership checked; selected payload bytes were not independently extracted/compared.','814 resolved Rust records are not exact linked closure; 17 lack license/license_file metadata, archive checksums not reverified here.','Tracker seven protocol XMLs and fourteen generated bindings/notices retained; exact upstream commit origins not separately recorded.','Authored avatar code/art rights and distribution terms require review separately from tracker MIT and native notices.','Generated cache transformations/inputs recorded, not regenerated.','No complete corresponding-source delivery or legal compliance claim.']}
assert r['free_disk_bytes']>=r['required_free_reserve_bytes']
(R/'boot/files-corner-source-acquisition.json').write_text(json.dumps(r,indent=2)+'\n')
(R/'boot/FILES_CORNER_SOURCE_ACQUISITION.md').write_text('''# Files/portal incremental source acquisition

All 55 planned official source files (16 source packages; 21,466,411 bytes) were retrieved and SHA-256/size verified against freshly authenticated retained Debian snapshot indexes. Both InRelease signatures and all four Packages/Sources indexes passed. All 97 runtime package/source mappings passed; 17 newly selected runtime package archives (5,747,920 bytes) were hash-verified against signed Packages. Control-index ownership is now authenticated; package payload files were not extracted or independently compared.

The separate 25 MiB ledger records '''+str(a['incremental_received_bytes'])+''' downloaded response-body bytes including retries, leaving '''+str(26214400-a['incremental_received_bytes'])+''' bytes. Original 1 GiB accounting is unchanged: conservative bound 1,059,760,437 bytes, remaining 13,981,387. The 4 GiB free-space reserve held. No sources were executed, installed or built; no root disk scan or new boot test occurred.

`files-corner-source-acquisition.json` binds exact unchanged Files/root/corner manifests, authentication results, source receipt and ledger. `files-corner-source-plan.json` and `FILES_CORNER_SOURCES.md` remain the planning record; their pre-acquisition versions are preserved under `build-src/files-corner-source-plan/pre-acquisition/`. A mistaken corner_bootstrap path in the planning report was corrected: a copyright-loop variable had shadowed the bootstrap path, while corner input checks and delta identity were already correct.

Runtime-owner/notice-only counts remain 97/382 for this overlay only. All earlier release audits remain unchanged. The original planning missing-source list is retained as the acquisition plan; its 55-file native source gap is now resolved, not deleted from history.

## Remaining review

- Resolved Rust inventory has 814 records, including 17 without license/license_file metadata. It is not proof of exact static-linked closure; existing registry archives were not rehashed this pass.
- Caller-authored tracker sources, seven third-party protocol XMLs, fourteen generated C/H files and notices are recorded. Exact upstream protocol commit origins remain unspecified. Tracker MIT does not supersede protocol, native, Python or artwork terms.
- Caller-selected/authored avatar code/art rights and final distribution licensing require separate review. Generated cache commands/inputs are recorded but not regenerated.
- Prior source/package verification is reused where already established. This bounded pass does not establish root-disk byte identity, complete corresponding-source delivery or legal compliance.
''')
print(json.dumps(r,indent=2))
