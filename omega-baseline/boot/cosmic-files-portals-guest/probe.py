#!/usr/bin/python3.13
"""Real guest D-Bus probes. Never run on host; does not answer dialogs itself."""
import argparse,json,pathlib,sys
from gi.repository import Gio,GLib
FIXTURE=pathlib.Path('/root/.local/share/roko-portal-fixture/input.txt')
CONTENT=b'ROKO_LOCAL_FILE_FIXTURE_v1\n'
def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['settings','show-items','chooser-cancel','chooser-select']);p.add_argument('--timeout',type=int,default=90);a=p.parse_args()
 if not 1<=a.timeout<=120:raise ValueError('Timeout must be1..120 seconds')
 # Explicit opt-in prevents unintended execution against an ordinary host session.
 if not pathlib.Path('/run/roko-files-portals-guest').is_file():raise RuntimeError('Guest-only probe marker absent')
 FIXTURE.parent.mkdir(parents=True,exist_ok=True)
 if FIXTURE.exists() and FIXTURE.read_bytes()!=CONTENT:raise RuntimeError('Refusing unrelated fixture overwrite')
 FIXTURE.write_bytes(CONTENT)
 bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
 def call(dest,path,interface,method,args):return bus.call_sync(dest,path,interface,method,args,None,Gio.DBusCallFlags.NONE,10000,None)
 if a.mode=='settings':
  values={}
  for key in ['color-scheme','contrast']:
   value=call('org.freedesktop.portal.Desktop','/org/freedesktop/portal/desktop','org.freedesktop.portal.Settings','Read',GLib.Variant('(ss)',('org.freedesktop.appearance',key)))
   values[key]=value.print_(True)
  print(json.dumps({'passed':True,'real_broker_settings':values}));return
 if a.mode=='show-items':
  call('org.freedesktop.FileManager1','/org/freedesktop/FileManager1','org.freedesktop.FileManager1','ShowItems',GLib.Variant('(ass)',([FIXTURE.as_uri()],'')))
  print(json.dumps({'method_acknowledged':True,'uri':FIXTURE.as_uri(),'visual_confirmation_still_required':True}));return
 loop=GLib.MainLoop();result={};expected=[None]
 def response(conn,sender,path,interface,signal,parameters):
  if path!=expected[0]:return
  code,values=parameters.unpack();result.update(code=code,values=values);loop.quit()
 token='roko_local_fixture'
 sub=bus.signal_subscribe(None,'org.freedesktop.portal.Request','Response',None,None,Gio.DBusSignalFlags.NONE,response)
 options={'handle_token':GLib.Variant('s',token),'modal':GLib.Variant('b',True),'multiple':GLib.Variant('b',False),'current_folder':GLib.Variant('ay',list(str(FIXTURE.parent).encode()+b'\0'))}
 reply=call('org.freedesktop.portal.Desktop','/org/freedesktop/portal/desktop','org.freedesktop.portal.FileChooser','OpenFile',GLib.Variant('(ssa{sv})',('','Roko local fixture only',options)))
 expected[0]=reply.unpack()[0];print(json.dumps({'request_path':expected[0],'waiting_for_real_user_dialog':True}),flush=True)
 def expired():result['timeout']=True;loop.quit();return False
 GLib.timeout_add_seconds(a.timeout,expired);loop.run();bus.signal_unsubscribe(sub)
 if result.get('timeout'):
  try:call('org.freedesktop.portal.Desktop',expected[0],'org.freedesktop.portal.Request','Close',None)
  except GLib.Error:pass
  raise RuntimeError('Real chooser response timed out')
 if a.mode=='chooser-cancel':assert result['code']==1,result
 else:
  assert result['code']==0,result
  assert result['values'].get('uris')==[FIXTURE.as_uri()],result
  assert FIXTURE.read_bytes()==CONTENT
 print(json.dumps({'passed':True,'real_portal_response':result},default=str))
if __name__=='__main__':main()
