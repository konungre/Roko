#!/usr/bin/env python3
"""Produce tiny next-image regular-file overlays; never edits a guest archive."""
import hashlib,json,pathlib,stat
ROOT=pathlib.Path(__file__).resolve().parents[2]
INDEX='usr/share/icons/hicolor/index.theme'
FAVORITES='root/.config/cosmic/com.system76.CosmicAppList/v1/favorites'
PACKAGE_SHA='d91fef83a186d3fc9fff293bfd7da4f684f736d15459d258a5a0d251168c1a35'
INDEX_SHA='a02db5e1b203d981701481bbef8b6fae1c576baf34927eecbc0feae0d2cb9bc5'
def sha(data):return hashlib.sha256(data).hexdigest()
def favorite_bytes(installed,avatar=False):
 wanted=['com.system76.CosmicTerm']+(['roko'] if avatar else [])
 for name in wanted:
  if 'usr/share/applications/'+name+'.desktop' not in installed:raise ValueError('Favorite lacks installed desktop: '+name)
 return (json.dumps(wanted)+'\n').encode() # String arrays are valid RON.
def verified_index(stage):
 lock=json.loads((stage/'debian-packages.lock.json').read_text())
 p=next(x for x in lock['packages'] if x['package']=='hicolor-icon-theme')
 if p['version']!='0.18-2' or p['sha256']!=PACKAGE_SHA:raise ValueError('Unexpected signed package pin')
 archive=stage/'apt/archives'/pathlib.Path(p['filename']).name
 if sha(archive.read_bytes())!=PACKAGE_SHA:raise ValueError('Package archive changed')
 files=json.loads((stage/'debian-files.lock.json').read_text())['files']
 r=next(x for x in files if x['path']==INDEX)
 data=(stage/'sysroot'/INDEX).read_bytes()
 if r['sha256']!=INDEX_SHA or sha(data)!=INDEX_SHA:raise ValueError('Hicolor index changed')
 return data,{'package':'hicolor-icon-theme','version':p['version'],'archive_sha256':PACKAGE_SHA,'index_sha256':INDEX_SHA,'signed_package_lock':str((stage/'debian-packages.lock.json').relative_to(ROOT))}
def build():
 stage=ROOT/'build-src/basilisk-stage';data,provenance=verified_index(stage)
 manifest=ROOT/'build/cosmic-session-guest-history/061e179a-passed/manifest.json'
 installed=set(json.loads(manifest.read_text())['entries'])
 controller=ROOT/'build-src/omega-avatar-controller-stage/overlay-v1/usr/share/applications/roko.desktop'
 for avatar in [False,True]:
  names=set(installed)
  if avatar:
   if not controller.is_file():raise ValueError('Real controller desktop absent')
   names.add('usr/share/applications/roko.desktop')
  label='avatar' if avatar else 'terminal';out=ROOT/f'build-src/cosmic-dock-stage/{label}-v1';out.mkdir(parents=True,exist_ok=True)
  records=[]
  for name,value in [(INDEX,data),(FAVORITES,favorite_bytes(names,avatar))]:
   p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value);p.chmod(0o444)
   records.append({'path':name,'sha256':sha(value),'mode':0o444})
  receipt={'schema':1,'files':records,'hicolor_provenance':provenance,'base_manifest_sha256':sha(manifest.read_bytes()),'favorites':['com.system76.CosmicTerm']+(['roko'] if avatar else []),'controller_desktop_sha256':sha(controller.read_bytes()) if avatar else None,'scope':'Next derived image only; real installed favorites; no added applications or changed executables'}
  (out.parent/(out.name+'.lock.json')).write_text(json.dumps(receipt,indent=2)+'\n')
  print(out.relative_to(ROOT))
if __name__=='__main__':build()
