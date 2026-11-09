#!/usr/bin/env python3
"""Exercise the actual persistent conversation runner without a graphical session."""
import argparse,json,pathlib,sys,threading
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent/'app'))
from omega_transport import OmegaTransport

def main():
 p=argparse.ArgumentParser(__doc__)
 p.add_argument('--runner',required=True,type=pathlib.Path);p.add_argument('--python',default=sys.executable)
 p.add_argument('--text',action='append',required=True);args=p.parse_args()
 if not args.runner.is_absolute():p.error('--runner must be absolute')
 t=OmegaTransport([args.python,'-u','-B',str(args.runner)]);rows=[]
 try:
  for text in args.text:
   event=threading.Event();row={'request':text}
   def done(answer,error):row.update(answer=answer,error=error);event.set()
   t.submit(text,done)
   if not event.wait(190):raise TimeoutError('Transport callback did not complete')
   rows.append(row)
   if row['error']:break
 finally:t.close()
 print(json.dumps({'turns':rows,'diagnostics':t.diagnostics,'gui_tested':False},ensure_ascii=False,indent=2))
 return 0 if len(rows)==len(args.text) and all(not r['error'] for r in rows) else 2
if __name__=='__main__':raise SystemExit(main())
