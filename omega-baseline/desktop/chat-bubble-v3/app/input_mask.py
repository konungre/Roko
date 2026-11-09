"""Pointer region shared by visible poses, excluding transparent/soft edges.

The supplied artwork's solid body is predominantly alpha 252–253, not 255.
Requiring exactly 255 made most of the visibly opaque dragon unclickable.
"""
OPAQUE_THRESHOLD = 240
def opaque_intersection(planes, width, height):
    if not planes:
        return ()
    if any(len(plane) != width * height for plane in planes):
        raise ValueError('Invalid alpha plane')
    rows = []
    for y in range(height):
        start = None
        for x in range(width + 1):
            solid = x < width and all(p[y * width + x] >= OPAQUE_THRESHOLD for p in planes)
            if solid and start is None:
                start = x
            elif not solid and start is not None:
                rows.append((start, y, x - start, 1))
                start = None
    return tuple(rows)
