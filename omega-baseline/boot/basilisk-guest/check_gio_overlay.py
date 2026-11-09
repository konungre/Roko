#!/usr/bin/env python3
"""Exercise actual Gio.AppInfo launcher with explicit missing/staged helper paths."""
import json,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];STAGE=ROOT/'build-src/basilisk-stage';runtime=STAGE/'overlay-v2';helper=STAGE/'gio-overlay-v1/usr/lib/x86_64-linux-gnu/glib-2.0/gio-launch-desktop'
code='''
import json,sys,shlex,time
from pathlib import Path
import gi
gi.require_version('Gio','2.0')
from gi.repository import Gio,GLib
runtime=Path(sys.argv[1]);marker=Path(sys.argv[2])
command=shlex.join([str(runtime/'lib64/ld-linux-x86-64.so.2'),str(runtime/'usr/bin/python3'),'-c',"from pathlib import Path; Path("+repr(str(marker))+").write_text('GIO_HELPER_EXEC_OK')"])
try:
 info=Gio.AppInfo.create_from_commandline(command,'Private Gio helper test',Gio.AppInfoCreateFlags.NONE)
 success=info.launch([],None)
 for i in range(100):
  if marker.exists():break
  time.sleep(.02)
 print(json.dumps({'launch_return':success,'child_marker':marker.read_text() if marker.exists() else None}))
except GLib.Error as exc:print(json.dumps({'launch_return':False,'error':str(exc)}))
'''
with tempfile.TemporaryDirectory(prefix='basilisk-gio-',dir=STAGE) as temp:
 empty=Path(temp)
 env={'HOME':str(empty),'PATH':'/nonexistent','LC_ALL':'C','PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1','PYTHONHOME':str(runtime/'usr'),'PYTHONPATH':str(runtime/'usr/lib/python3/dist-packages'),'GI_TYPELIB_PATH':str(runtime/'usr/lib/x86_64-linux-gnu/girepository-1.0'),'LD_LIBRARY_PATH':str(runtime/'usr/lib/x86_64-linux-gnu'),'XDG_DATA_HOME':str(empty),'XDG_DATA_DIRS':str(STAGE/'mime-overlay-v1/usr/share')}
 results={}
 for name,path in [('missing',empty/'no-helper'),('staged',helper)]:
  env['GIO_LAUNCH_DESKTOP']=str(path)
  p=subprocess.run([str(runtime/'lib64/ld-linux-x86-64.so.2'),str(runtime/'usr/bin/python3'),'-c',code,str(runtime),str(empty/(name+'.marker'))],env=env,capture_output=True,text=True,check=True)
  results[name]=json.loads(p.stdout)
 assert not results['missing']['launch_return'],results
 assert results['staged']['launch_return'] and results['staged']['child_marker']=='GIO_HELPER_EXEC_OK',results
 results.update(passed=True,scope='Actual Gio.AppInfo.launch with explicit helper override, no host helper/PATH fallback. Child target is staged Python via staged loader; host kernel/ELF interpreter used. Not desktop-file matching or GUI launch proof.')
 print(json.dumps(results,indent=2))
