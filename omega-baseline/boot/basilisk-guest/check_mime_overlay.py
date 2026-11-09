#!/usr/bin/env python3
"""Positive/negative decoder checks excluding host MIME and module caches."""
import json,os,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];STAGE=ROOT/'build-src/basilisk-stage';runtime=STAGE/'overlay-v2';mime=STAGE/'mime-overlay-v1'
code='''
import gi,json,sys
from pathlib import Path
gi.require_version('GdkPixbuf','2.0')
from gi.repository import GdkPixbuf,GLib
formats=[f.get_name() for f in GdkPixbuf.Pixbuf.get_formats()]
try:
 p=GdkPixbuf.Pixbuf.new_from_file(sys.argv[1]); result={'decoded':True,'dimensions':[p.get_width(),p.get_height()]}
except GLib.Error as exc: result={'decoded':False,'error':str(exc)}
result['registered_formats']=formats
result['decoder_library_maps']=sorted({line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines() if any(x in line for x in ('libgdk_pixbuf','libpng','libpixbufloader'))})
print(json.dumps(result))
'''
with tempfile.TemporaryDirectory(prefix='basilisk-mime-',dir=STAGE) as temp:
 empty=Path(temp);(empty/'loaders.cache').write_text('')
 env={'HOME':str(empty),'PATH':'/nonexistent','LC_ALL':'C','PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1','PYTHONHOME':str(runtime/'usr'),'PYTHONPATH':str(runtime/'usr/lib/python3/dist-packages'),'GI_TYPELIB_PATH':str(runtime/'usr/lib/x86_64-linux-gnu/girepository-1.0'),'LD_LIBRARY_PATH':str(runtime/'usr/lib/x86_64-linux-gnu'),'GDK_PIXBUF_MODULE_FILE':str(empty/'loaders.cache'),'GDK_PIXBUF_MODULEDIR':str(empty),'XDG_DATA_HOME':str(empty)}
 results={}
 for name,data in [('without_mime',empty),('with_mime',mime/'usr/share')]:
  env['XDG_DATA_DIRS']=str(data)
  p=subprocess.run([str(runtime/'lib64/ld-linux-x86-64.so.2'),str(runtime/'usr/bin/python3'),'-c',code,str(ROOT/'desktop/basilisk/assets/roko.png')],env=env,capture_output=True,text=True,check=True)
  result=json.loads(p.stdout)
  assert all(path.startswith(str(runtime)) for path in result['decoder_library_maps']),result
  assert 'png' in result['registered_formats']
  results[name]=result
 assert not results['without_mime']['decoded'],results
 assert results['with_mime']['decoded'] and results['with_mime']['dimensions']==[1536,2288],results
 results['passed']=True
 results['scope']='No host MIME/module cache fallback: empty private loader cache/module dir and XDG_DATA_HOME; XDG_DATA_DIRS only new overlay for positive. No real guest/display claim.'
 print(json.dumps(results,indent=2))
