#!/usr/bin/env python3
import json,pathlib,hashlib,stat,re
R=pathlib.Path(__file__).resolve().parents[2];S=R/'build-src/cosmic-files-portals-stage';O=S/'overlay-v1';L=S/'overlay-v1.lock.json'
def check():
 j=json.loads(L.read_text());files={x['path']:x for x in j['files']};assert len(files)==len(j['files']);errors=[]
 for n,r in files.items():
  p=O/n
  if pathlib.Path(n).is_absolute() or '..' in pathlib.Path(n).parts or p.is_symlink() or not p.is_file():errors.append('unsafe '+n);continue
  if hashlib.sha256(p.read_bytes()).hexdigest()!=r['sha256'] or stat.S_IMODE(p.stat().st_mode)!=r['mode']:errors.append('changed '+n)
 for n in files:
  if n.startswith('usr/share/dbus-1/services/'):
   data=(O/n).read_text();execs=re.findall(r'^Exec=(\S+)',data,re.M)
   for cmd in execs:
    if cmd.lstrip('/') not in files:errors.append('missing service Exec '+cmd)
 for p in ['usr/bin/cosmic-files','usr/bin/cosmic-files-applet','usr/libexec/xdg-desktop-portal-cosmic','usr/share/applications/com.system76.CosmicFiles.desktop','usr/share/icons/hicolor/48x48/apps/com.system76.CosmicFiles.svg','usr/share/glib-2.0/schemas/gschemas.compiled','usr/share/mime/mime.cache','usr/lib/x86_64-linux-gnu/gio/modules/giomodule.cache']:
  if p not in files:errors.append('missing '+p)
 cache=(O/'usr/lib/x86_64-linux-gnu/gio/modules/giomodule.cache').read_text()
 if '/workspace/' in cache:errors.append('host path in GIO cache')
 forbidden=['init','usr/bin/roko','usr/bin/roko-basilisk','root/.config/cosmic/com.system76.CosmicAppList/v1/favorites']
 for p in forbidden:
  if p in files:errors.append('unexpected existing behavior override '+p)
 base=R/'build/cosmic-persistent-guest/manifest.json';collision=[];mode_collision=[];same=0
 if base.exists():
  for p,r in json.loads(base.read_text())['entries'].items():
   if p in files:
    old=r['sha256'] if isinstance(r,dict) else r
    if old==files[p]['sha256']:same+=1
    if isinstance(r,dict) and 'mode' in r and stat.S_IMODE(r['mode'])!=files[p]['mode']:
     mode_collision.append({'path':p,'base_mode':stat.S_IMODE(r['mode']),'overlay_mode':files[p]['mode'],'same_content':old==files[p]['sha256']})
    if old!=files[p]['sha256']:collision.append({'path':p,'base_sha256':old,'overlay_sha256':files[p]['sha256']})
 result={'success':not errors,'errors':errors,'regular_files':len(files),'elf_objects':len(j['elfs']),'identical_base_files':same,'explicit_replacements_required':collision,'mode_collisions':mode_collision,'runtime_tested':False};(S/'overlay-v1.static-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));assert not errors
if __name__=='__main__':check()
