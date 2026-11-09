#!/usr/bin/env python3
"""Read-only exact original-sprite matching against raw compositor PPM/PNG captures.
No screenshot modification, fuzzy tolerance, image rescaling, or pass by presence.
Opaque pixels prove atlas content; partial-alpha pixels depend on GTK background.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'desktop/basilisk'))
from atlas import STATES, COUNTS, rectangle, look_rectangle
from companion import verify_asset

WIDTH, HEIGHT = 192, 208

def frames(state=None, look=None):
    if state is not None and look is not None:
        raise ValueError('Choose state or look, not both')
    with Image.open(verify_asset()) as atlas:
        result = []
        specs = [(s, f, rectangle(s, f)) for s, n in zip(STATES, COUNTS) for f in range(n)] if look is None else []
        if state is not None:
            specs = [v for v in specs if v[0] == state]
        elif look is None:
            specs += [('look', i, look_rectangle(i)) for i in range(16)]
        else:
            specs = [('look', look, look_rectangle(look))]
        for name, index, (x, y, w, h) in specs:
            rgba = atlas.crop((x, y, x+w, y+h))
            pixels = rgba.tobytes()
            opaque = [(i % w, i // w, pixels[i*4:i*4+3]) for i in range(w*h) if pixels[i*4+3] == 255]
            if not opaque:
                raise ValueError('Frame has no opaque pixels')
            counts = Counter(rgb for _, _, rgb in opaque)
            anchor = min(opaque, key=lambda p: counts[p[2]])
            result.append({'state': name, 'frame': index, 'opaque': opaque, 'anchor': anchor})
        return result

def match_at(image, frame, x, y):
    if x < 0 or y < 0 or x+WIDTH > image.width or y+HEIGHT > image.height:
        return {'passed': False, 'reason': 'crop-out-of-bounds'}
    raw = image.tobytes()
    bad = sum(raw[((y+dy)*image.width+x+dx)*3:((y+dy)*image.width+x+dx)*3+3] != rgb for dx, dy, rgb in frame['opaque'])
    return {'passed': bad == 0, 'opaque_pixels': len(frame['opaque']), 'mismatched_opaque_pixels': bad}

def find_matches(image, candidates, origin=None):
    image = image.convert('RGB')
    raw = image.tobytes()
    found = []
    for frame in candidates:
        if origin is not None:
            positions = [origin]
        else:
            ax, ay, rgb = frame['anchor']
            positions = []
            start = 0
            while True:
                at = raw.find(rgb, start)
                if at < 0:
                    break
                start = at+1
                if at % 3 == 0:
                    pixel = at//3
                    x, y = pixel % image.width-ax, pixel//image.width-ay
                    if 0 <= x <= image.width-WIDTH and 0 <= y <= image.height-HEIGHT:
                        positions.append((x, y))
        for x, y in positions:
            # Reject most coincidental anchor matches cheaply before full equality.
            subset = frame['opaque'][::max(1,len(frame['opaque'])//16)]
            if any(raw[((y+dy)*image.width+x+dx)*3:((y+dy)*image.width+x+dx)*3+3] != rgb for dx,dy,rgb in subset):
                continue
            check = match_at(image, frame, x, y)
            if check['passed']:
                found.append({'state': frame['state'], 'frame': frame['frame'], 'x': x, 'y': y, **check})
    return found

def sequence(images, candidates, times_ms, mode, origin=None):
    if mode not in ('animation', 'pause'):
        raise ValueError('Mode must be animation or pause')
    if len(images) < 3 or len(times_ms) != len(images):
        raise ValueError('At least three captures and one timestamp per capture required')
    if any(b-a < 125 for a,b in zip(times_ms,times_ms[1:])):
        raise ValueError('Capture timestamps must increase by at least 125 ms')
    details = []
    for image in images:
        image = image.convert('RGB')
        matched = find_matches(image, candidates, origin)
        locations = {(m['x'],m['y']) for m in matched}
        if len(locations) != 1:
            return {'passed': False, 'reason': 'no-unique-sprite-location', 'captures': details, 'matches': matched}
        point, = locations
        if origin is None:
            origin = point
        if point != origin:
            return {'passed': False, 'reason': 'sprite-position-changed', 'captures': details}
        x,y = origin
        digest = hashlib.sha256(image.crop((x,y,x+WIDTH,y+HEIGHT)).tobytes()).hexdigest()
        details.append({'matches':matched,'crop_rgb_sha256':digest})
    hashes = {d['crop_rgb_sha256'] for d in details}
    visible_frame_sets = {tuple((m['state'],m['frame']) for m in d['matches']) for d in details}
    passed = len(hashes) == 1 if mode == 'pause' else len(hashes) > 1 and len(visible_frame_sets) > 1
    return {'passed':passed,'mode':mode,'origin':list(origin),'capture_times_ms':times_ms,'captures':details,'timing_scope':'Caller-supplied capture timestamps; source image files do not authenticate time','pixel_scope':'Every alpha=255 source pixel must match; pause additionally requires complete RGB crop equality'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['match','animation','pause'])
    p.add_argument('captures',nargs='+',type=Path)
    g=p.add_mutually_exclusive_group()
    g.add_argument('--state',choices=STATES)
    g.add_argument('--look',type=int,choices=range(16))
    p.add_argument('--origin',nargs=2,type=int,metavar=('X','Y'))
    p.add_argument('--times-ms',nargs='+',type=int)
    args=p.parse_args()
    try:
        candidates=frames(args.state,args.look)
        images=[];sources=[]
        for path in args.captures:
            sources.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            with Image.open(path) as im:images.append(im.convert('RGB'))
        origin=tuple(args.origin) if args.origin else None
        if args.mode=='match':
            if len(images)!=1:raise ValueError('match requires exactly one capture')
            matches=find_matches(images[0],candidates,origin)
            report={'passed':len({(m['x'],m['y']) for m in matches})==1,'matches':matches}
        else:
            report=sequence(images,candidates,args.times_ms or [],args.mode,origin)
        report.update(captures_source=sources,asset_sha256=hashlib.sha256(verify_asset().read_bytes()).hexdigest(),scope='Read-only exact source opaque-pixel oracle; not independent proof of input dispatch or application process identity')
    except (ValueError,OSError) as exc:
        report={'passed':False,'error':str(exc)}
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
