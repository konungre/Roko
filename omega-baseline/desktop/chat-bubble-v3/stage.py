#!/usr/bin/env python3
"""Build a new uninstalled avatar overlay; never modify an existing stage."""
import argparse,hashlib,json,pathlib,shutil
BASE=pathlib.Path(__file__).resolve().parent

def stage(destination):
    destination=pathlib.Path(destination)
    if destination.exists() or destination.is_symlink():raise FileExistsError(destination)
    manifest=json.loads((BASE/'app/manifest.json').read_text())
    for name,key in [('character.png','sha256'),('corner.png','corner_sha256')]:
        if hashlib.sha256((BASE/'app/assets'/name).read_bytes()).hexdigest()!=manifest[key]:
            raise ValueError('Artwork integrity failure: '+name)
    destination.mkdir(parents=False)
    app=destination/'usr/share/roko/showcase'
    shutil.copytree(BASE/'app',app,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    launcher=destination/'usr/bin/roko-companion';launcher.parent.mkdir(parents=True)
    launcher.write_text('''#!/bin/sh
exec "${ROKO_GUI_PYTHON:-/usr/bin/python3}" /usr/share/roko/showcase/companion.py --conversation-python "${ROKO_CONVERSATION_PYTHON:-/usr/bin/python3}" --conversation-runner "${ROKO_CONVERSATION_RUNNER:-/opt/roko/components/conversation/run.py}" "$@"
''')
    launcher.chmod(0o755)
    entry='''[Desktop Entry]
Type=Application
Name=Roko
Comment=Your Omega desktop companion
Exec=/usr/bin/roko-companion
Terminal=false
Categories=Utility;
'''
    for name in ['usr/share/applications/roko-companion.desktop','etc/xdg/autostart/roko-companion.desktop']:
        path=destination/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(entry)
    record={'schema':'roko-bubble-stage-v3','installed':False,'native_tested':False,
            'omega_runtime_included':False,'files':{str(p.relative_to(destination)):hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in sorted(destination.rglob('*')) if p.is_file()}}
    (destination/'STAGE.json').write_text(json.dumps(record,indent=2)+'\n')
    return record

if __name__=='__main__':
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('new_destination',type=pathlib.Path)
    print(json.dumps(stage(parser.parse_args().new_destination),indent=2))
