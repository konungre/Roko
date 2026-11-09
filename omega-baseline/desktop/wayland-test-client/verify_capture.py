#!/usr/bin/env python3
"""Verify full 320x240 surface pixels inside a QEMU P6 screendump.

No claim about scanout is made from a client log. This verifies a separately
captured image, given a known top-left surface origin at unscaled 1:1 pixels.
"""
import argparse
from pathlib import Path

WIDTH, HEIGHT = 320, 240
COLORS = (((255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)),
          ((0, 255, 255), (255, 0, 255), (255, 128, 0), (128, 64, 255)))


def expected_pixel(x, y, state):
    if x < 4 or y < 4 or x >= WIDTH - 4 or y >= HEIGHT - 4:
        return (0, 0, 0)
    if 144 <= x < 176 and 104 <= y < 136:
        return (255, 255, 255)
    return COLORS[state][(y >= 120) * 2 + (x >= 160)]


def read_ppm(data):
    pos = 0

    def token():
        nonlocal pos
        while pos < len(data):
            if data[pos] in b' \t\r\n':
                pos += 1
            elif data[pos] == ord('#'):
                end = data.find(b'\n', pos)
                if end < 0:
                    raise ValueError('Unterminated PPM comment')
                pos = end + 1
            else:
                break
        start = pos
        while pos < len(data) and data[pos] not in b' \t\r\n':
            pos += 1
        return data[start:pos]

    if token() != b'P6':
        raise ValueError('Expected binary P6 PPM')
    width, height, maxval = int(token()), int(token()), int(token())
    if not (0 < width <= 16384 and 0 < height <= 16384 and maxval == 255):
        raise ValueError('Unsupported dimensions or maxval')
    # P6 raster follows one whitespace byte. Do not strip valid pixel bytes.
    if pos >= len(data) or data[pos] not in b' \t\r\n':
        raise ValueError('Missing PPM raster separator')
    pos += 1
    pixels = data[pos:]
    if len(pixels) != width * height * 3:
        raise ValueError('Incorrect PPM raster length')
    return width, height, pixels


def verify(data, left, top, state):
    if state not in (0, 1):
        raise ValueError('State must be 0 or 1')
    width, height, pixels = read_ppm(data)
    if left < 0 or top < 0 or left + WIDTH > width or top + HEIGHT > height:
        raise ValueError('Surface rectangle outside capture')
    for y in range(HEIGHT):
        for x in range(WIDTH):
            offset = ((top + y) * width + left + x) * 3
            actual = tuple(pixels[offset:offset + 3])
            expected = expected_pixel(x, y, state)
            if actual != expected:
                raise ValueError(f'Pixel mismatch surface ({x},{y}): {actual} != {expected}')
    return {'capture_width': width, 'capture_height': height,
            'surface_x': left, 'surface_y': top, 'state': state,
            'matched_pixels': WIDTH * HEIGHT}


def locate(data, state):
    """Find exactly one unscaled test surface, then verify every pixel."""
    if state not in (0, 1):
        raise ValueError('State must be 0 or 1')
    width, height, pixels = read_ppm(data)
    needle = bytes(channel for x in range(WIDTH)
                   for channel in expected_pixel(x, 4, state))
    matches = []
    start = 0
    while True:
        offset = pixels.find(needle, start)
        if offset < 0:
            break
        start = offset + 1
        if offset % 3:
            continue
        y, x = divmod(offset // 3, width)
        if y < 4 or y - 4 + HEIGHT > height or x + WIDTH > width:
            continue
        try:
            result = verify(data, x, y - 4, state)
        except ValueError:
            continue
        matches.append(result)
        if len(matches) > 1:
            raise ValueError('Ambiguous capture: multiple matching surfaces')
    if len(matches) != 1:
        raise ValueError('No complete unscaled test surface found')
    return matches[0]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ppm', type=Path)
    parser.add_argument('--x', type=int)
    parser.add_argument('--y', type=int)
    parser.add_argument('--state', type=int, choices=(0, 1), required=True)
    args = parser.parse_args()
    import json
    if (args.x is None) != (args.y is None):
        parser.error('Specify both --x and --y, or neither for automatic location')
    data = args.ppm.read_bytes()
    result = locate(data, args.state) if args.x is None else verify(data, args.x, args.y, args.state)
    print(json.dumps(result, sort_keys=True))
