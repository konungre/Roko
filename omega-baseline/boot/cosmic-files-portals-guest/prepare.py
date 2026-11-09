#!/usr/bin/env python3
"""Prepare a versioned authentic runtime overlay, never a VM or host daemon."""
import importlib.util,json,pathlib,stat,subprocess,os
R=pathlib.Path(__file__).resolve().parents[2];S=R/'build-src/cosmic-files-portals-stage';D=R/'build-src/cosmic-desktop-stage';O=S/'overlay-v1'
spec=importlib.util.spec_from_file_location('closure',R/'boot/cosmic-guest/build.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
def prepare():
 if O.exists():raise ValueError('Refusing existing versioned overlay')
 c=base.Closure(S/'sysroot',json.loads((S/'debian-files.lock.json').read_text()));sources={};transforms={}
 def put(name,data,mode=0o444):c.files[name]=(data,stat.S_IFREG|mode)
 def source(path,dest):
  if not path.is_file() or path.is_symlink():raise ValueError('Expected regular source '+str(path))
  data=path.read_bytes();sources[str(path.relative_to(R))]=base.sha(data);put(dest,data)
 def tree(path,dest):
  for p in sorted(path.rglob('*')):
   if p.is_file():source(p,dest+'/'+str(p.relative_to(path)))
 for name,dest in [('files','usr/bin/cosmic-files'),('files-applet','usr/bin/cosmic-files-applet'),('portal','usr/libexec/xdg-desktop-portal-cosmic')]:
  rec=json.loads((S/'artifacts'/f'{name}.json').read_text());a=rec['artifact'];assert rec['exit_code']==0;assert c.external(R/a['path'],dest)==a['sha256']
 for name in ['xdg-desktop-portal','xdg-document-portal','xdg-permission-store','xdg-desktop-portal-gtk','xdg-desktop-portal-validate-icon','xdg-desktop-portal-validate-sound','gvfsd','gvfsd-trash','gvfsd-computer','gvfsd-metadata']:
  c.add('usr/libexec/'+name)
 for name in ['gio','gdbus','dbus-update-activation-environment','xdg-open','xdg-mime']:
  c.add('usr/bin/'+name)
 for name in ['libgvfsdbus.so','libdconfsettings.so']:c.add('usr/lib/x86_64-linux-gnu/gio/modules/'+name)
 for name in ['usr/lib/x86_64-linux-gnu/glib-2.0/gio-launch-desktop','usr/lib/x86_64-linux-gnu/glib-2.0/glib-compile-schemas','usr/lib/x86_64-linux-gnu/glib-2.0/gio-querymodules','usr/libexec/dconf-service']:
  c.add(name)
 for prefix in ['usr/share/glib-2.0/schemas','usr/share/gtk-3.0','usr/share/icons/Adwaita','usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0','usr/share/xdg-desktop-portal']:
  c.tree(prefix)
 c.add('usr/share/icons/hicolor/index.theme')
 for service in ['org.freedesktop.portal.Desktop','org.freedesktop.portal.Documents','org.freedesktop.impl.portal.PermissionStore','org.freedesktop.impl.portal.desktop.gtk','org.gtk.vfs.Daemon','org.gtk.vfs.Metadata','ca.desrt.dconf']:
  c.add('usr/share/dbus-1/services/'+service+'.service')
 for mount in ['computer.mount','trash.mount']:c.add('usr/share/gvfs/mounts/'+mount)
 files=D/'sources/cosmic-files';portal=S/'sources/xdg-desktop-portal-cosmic'
 source(files/'target/xdgen/com.system76.CosmicFiles.desktop','usr/share/applications/com.system76.CosmicFiles.desktop')
 source(files/'target/xdgen/com.system76.CosmicFiles.metainfo.xml','usr/share/metainfo/com.system76.CosmicFiles.metainfo.xml')
 tree(files/'res/icons','usr/share/icons')
 for name in ['cosmic.portal','cosmic-portals.conf']:source(portal/'data'/name,'usr/share/xdg-desktop-portal/'+('portals/' if name.endswith('.portal') else '')+name)
 tree(portal/'data/icons','usr/share/icons/hicolor')
 template=portal/'data/dbus-1/org.freedesktop.impl.portal.desktop.cosmic.service.in';raw=template.read_bytes();data=raw.replace(b'@libexecdir@/xdg-desktop-portal-cosmic',b'/usr/libexec/roko-cosmic-portal')
 put('usr/share/dbus-1/services/org.freedesktop.impl.portal.desktop.cosmic.service',data);transforms[str(template.relative_to(R))]={'sha256':base.sha(raw),'change':'Exec wraps unchanged backend with supported CPU renderer environment'}
 put('usr/libexec/roko-cosmic-portal',b'#!/bin/sh\nexport ICED_BACKEND=tiny-skia\nexec /usr/libexec/xdg-desktop-portal-cosmic "$@"\n',0o755)
 # Include exact debug localization roots from all source/dependency commits, not only root crates.
 deps=json.loads((S/'dependency-sources.lock.json').read_text())
 roots=[files,portal]+[R/p for p in deps['git_checkouts']]
 for root in roots:
  if (root/'i18n').is_dir():tree(root/'i18n',str(root/'i18n').lstrip('/'))
 for root in [files,portal]:
  for p in root.iterdir():
   if p.is_file() and p.name.upper().startswith(('LICENSE','COPYING')):source(p,'usr/share/doc/'+root.name+'/'+p.name)
 for p in json.loads((S/'debian-packages.lock.json').read_text())['packages']:
  path='usr/share/doc/'+p['package']+'/copyright'
  if c.resolve(path) in c.lock:c.add(path)
 # Reuse fully locked, generated MIME data rather than rerunning package scripts.
 mime=R/'build-src/basilisk-stage/mime-overlay-v1';ml=json.loads(mime.with_name(mime.name+'.lock.json').read_text())
 for rec in ml['files']:
  data=(mime/rec['path']).read_bytes();assert base.sha(data)==rec['sha256'];put(rec['path'],data,rec['mode'])
 for name,(data,mode) in c.files.items():
  p=O/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data);p.chmod(stat.S_IMODE(mode))
 # Data compilers are pinned official tools; only private generated caches change.
 loader=O/'lib64/ld-linux-x86-64.so.2';libs=O/'usr/lib/x86_64-linux-gnu'
 commands=[['usr/lib/x86_64-linux-gnu/glib-2.0/glib-compile-schemas','--strict',str(O/'usr/share/glib-2.0/schemas')],['usr/lib/x86_64-linux-gnu/glib-2.0/gio-querymodules',str(O/'usr/lib/x86_64-linux-gnu/gio/modules')]]
 for cmd in commands:subprocess.run([str(loader),'--library-path',str(libs),str(O/cmd[0]),*cmd[1:]],check=True,env=dict(os.environ,LD_PRELOAD=''))
 records=[{'path':str(p.relative_to(O)),'sha256':base.sha(p.read_bytes()),'mode':stat.S_IMODE(p.stat().st_mode),'kind':'file'} for p in sorted(O.rglob('*')) if p.is_file()]
 result={'schema':1,'files':records,'runtime_sources':c.sources,'elfs':c.elfs,'upstream_assets':sources,'transforms':transforms,'native_lock_sha256':base.sha((S/'debian-files.lock.json').read_bytes()),'mime_lock_sha256':base.sha(mime.with_name(mime.name+'.lock.json').read_bytes()),'generated_cache_commands':commands,'scope':'New Files/portal overlay; no host service, VM, remote mount or renderer success claim','bytes':sum((O/r['path']).stat().st_size for r in records),'guest_tested':False}
 (S/'overlay-v1.lock.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'files':len(records),'bytes':result['bytes']}))
if __name__=='__main__':prepare()
