#!/usr/bin/env python3
"""Package source/reports/small runtime artifacts, explicitly excluding large assets."""
import hashlib,json,sys,zipfile,os,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
version=sys.argv[1]
if re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}',version) is None:raise ValueError('Expected numeric milestone version')
out=ROOT.parent/f'roko-omega-baseline-{version}.zip'
excluded={'.git','.venv','.offline-test-venv','.component-offline-venv','.embedding-offline-venv','__pycache__','.pytest_cache','test-wheels','component-wheels','embedding-wheels','models','model-research','build','user-state','tooling'}
# Keep small, self-authored recipes and provenance, never staged third-party code/binaries.
receipts={
 'cosmic-comp-stage': {'README.md','build-provenance.json','build-nightly-provenance.json','compositor-artifact.json','debian-packages.lock.json','debian-files.lock.json','rust-toolchain.lock.json','rust-sources.lock.json','env.sh','build-compositor.sh','prepare_debian.py','provision_rust.py','verify_stage.py'},
 'cosmic-source-closure': {'audit.py','enrich.py','fetch_kernel_sources.py','fetch_egl_sources.py','fetch_cosmic_runtime_sources.py','map_base_guest.py','finalize_bundle_report.py','inventory.json','inherited-guest-source-map.json','cosmic-runtime-source-bundle.manifest.json','kernel-source-bundle.manifest.json','egl-source-bundle.manifest.json','cosmic-additional-source-files.json','archive-ownership.json','archive-ownership-lock.sha256'},
 'cosmic-desktop-stage': {'README.md','build_component.sh','sources.lock.json','debian-packages.lock.json','fetch_deps.sh','dependency-sources.lock.json','run_build.py','verify_native.py','renderer-features.json','pin_artifact.py','debian-files.lock.json','stage_sources.py','inventory_sources.py','env.sh','update_build_report.py','prepare_debian.py',
  'artifacts/cosmic-app-library.json','artifacts/cosmic-applets.json','artifacts/cosmic-bg.json','artifacts/cosmic-launcher.json','artifacts/cosmic-notifications.json','artifacts/cosmic-panel.json','artifacts/cosmic-session.json','artifacts/cosmic-settings-daemon.json','artifacts/cosmic-term.json','artifacts/pop-launcher.json','artifacts/original-dev/pop-launcher.json','artifacts/original-dev/pop-launcher-build.json'},
 'cosmic-termdata-stage': {'prepare_debian.py','debian-packages.lock.json','debian-files.lock.json'},
 'cosmic-session-source-closure': {'audit.py','acquire_missing.py','retrieve-missing-native-sources.sh','inventory.json','ownership.json','acquisition-plan.json','acquired-native-sources.json','missing-native-sources.json','pre-acquisition-summary.json','pre-acquisition-inventory.json',
  'history/eab3ae7a29b8cf283538275a97db266d0eef9e3910ded39a73e3ecba8b4ba7ef/cosmic-session-source-closure.json',
  'history/eab3ae7a29b8cf283538275a97db266d0eef9e3910ded39a73e3ecba8b4ba7ef/inventory.json',
  'history/eab3ae7a29b8cf283538275a97db266d0eef9e3910ded39a73e3ecba8b4ba7ef/COSMIC_SESSION_SOURCES.md'},
 'filesystem-stage': {'README.md','prepare_debian.py','debian-packages.lock.json','debian-files.lock.json','runtime-closure.json','provenance.json'},
 'basilisk-stage': {'prepare_debian.py','debian-packages.lock.json','debian-files.lock.json','overlay.lock.json','overlay-v2.lock.json','mime-overlay-v1.lock.json','gio-overlay-v1.lock.json'},
 'basilisk-layer-stage': {'prepare_debian.py','debian-packages.lock.json','debian-files.lock.json','overlay-v1.lock.json'},
 'omega-avatar-controller-stage': {'overlay-v1.lock.json','python313-validation-v1.json'},
 'cosmic-dock-stage': {'terminal-v1.lock.json','avatar-v1.lock.json'},
 'avatar-source-closure': {'audit.py','acquire_missing.py','retrieve-missing-sources.sh','inventory.json','archive-ownership.json','acquisition-plan.json','acquired-sources.json','download-ledger.json','missing-native-sources.json','pre-acquisition-inventory.json','pre-acquisition-summary.json'}
}
def candidates():
 for directory, dirs, names in os.walk(ROOT, followlinks=False):
  relative=Path(directory).relative_to(ROOT);parts=relative.parts
  dirs[:]=sorted(d for d in dirs if d not in excluded and not (Path(directory)/d).is_symlink())
  if not parts:
   dirs[:]=[d for d in dirs if not d.startswith(('granite-test-','native-provider-','embedding-persistence-','omega-components-','retrieval-proposal-','roko-console-','mork-facts-','ecan-advisory-','package-native-'))]
   names=[n for n in names if not n.lower().endswith(('.png','.jpg','.jpeg','.webp','.gif'))]
  if parts==('build-src',):
   dirs[:]=[d for d in dirs if d=='swipl-10.0.2' or d in receipts]
   names=[n for n in names if n=='cosmic-runtime-source-evidence.json']
  if len(parts)>=2 and parts[0]=='build-src' and parts[1]!='swipl-10.0.2':
   allowed=receipts.get(parts[1],set())
   prefix='/'.join(parts[2:])
   prefix=prefix+'/' if prefix else ''
   dirs[:]=[d for d in dirs if any(n.startswith(prefix+d+'/') for n in allowed)]
   names=[n for n in names if prefix+n in allowed]
  if parts==('results',):
   # Failed session raw captures remain in the workspace; the completed run is delivered.
   dirs[:]=[d for d in dirs if d!='cosmic-session-guest-attempts'
            and (not d.startswith('basilisk-') or d=='basilisk-avatar-guest')
            and not d.startswith(('cosmic-files-portals','granite-guest'))]
   names=[n for n in names if not n.startswith(('cosmic-files-portals','granite-guest'))]
  if parts==('boot',):
   # Unfinished new desktop/model integrations are separate from this milestone.
   dirs[:]=[d for d in dirs if d not in {'basilisk-layer-guest','cosmic-files-portals-guest','granite-guest'}]
   names=[n for n in names if n!='cosmic-files-portals-build.json']
  if parts==('tests',):
   names=[n for n in names if n!='test_cosmic_files_portals_plan.py']
  if parts==('desktop',):
   dirs[:]=[d for d in dirs if d not in {'basilisk-v3','basilisk-v3-tested'}]
  for name in sorted(names):
   if name in {'.git','.DS_Store'}:continue
   if name=='roko-persistence-tested.cpio.gz':continue
   if name.endswith(('.raw','.ext4','.qcow','.qcow2','.vmdk','.iso')):continue
   if name.endswith('.cpio.gz') and str(relative/name) not in {
    'boot/artifacts/roko-initramfs.cpio.gz','boot/artifacts/roko-probe-0.14.cpio.gz',
    'boot/artifacts/graphics-probe-0.17.cpio.gz'}:continue
   if parts==('results',) and re.fullmatch(r'package-v[0-9]+\.json',name):continue
   path=Path(directory)/name
   if path.is_file() and not path.is_symlink():yield path
# Never overwrite an earlier delivery, including a previously frozen current version.
with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
 for path in candidates():
  archive.write(path,Path('omega-baseline')/path.relative_to(ROOT))
with zipfile.ZipFile(out) as archive:
 assert archive.testzip() is None
report={'artifact':str(out),'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'zip_crc_verified':True}
print(json.dumps(report,indent=2))
