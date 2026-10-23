"""Export-only coordinate formatting; never quantize saved drawing geometry."""
import math

import numpy as np


def _fixed(value, places):
    if not math.isfinite(float(value)):
        raise ValueError('TikZ coordinates must be finite')
    if places is None:
        return '0' if value == 0 else np.format_float_positional(float(value), unique=True, trim='-')
    text = format(float(value), f'.{places}f').rstrip('0').rstrip('.')
    return '0' if text in ('', '-0') else text


class TexCoordinates:
    """Four decimal places, increased if vertices or a nonzero segment collapse.

    All coordinates in a drawing share the chosen precision. At most 15 fixed
    places are tried before falling back to round-trip decimal formatting.
    Control handles may coincide, but an entire nonzero segment must not vanish.
    """
    def __init__(self, points=(), *, vertices=(), segments=(), normalize=False,
                 size_cm=10, literal_limit=None):
        self.offset = np.zeros(2)
        self.factor = 1.
        self.literal_limit = literal_limit if not normalize else None
        points = list(points)
        if normalize:
            if not math.isfinite(size_cm) or not 0 < size_cm <= 50:
                raise ValueError('size_cm must be finite in (0,50]')
            if points:
                values = np.asarray(points, dtype=float)
                low, high = values.min(axis=0), values.max(axis=0)
                span = float((high-low).max())
                self.offset = low/2+high/2
                self.factor = size_cm/span if span else 1.
                if not math.isfinite(self.factor):
                    raise ValueError('Coordinate span is too small for TikZ normalization')
        protected = [tuple(self.transform(p)) for p in vertices]
        groups = [[tuple(self.transform(p)) for p in segment] for segment in segments]
        self.places = None
        for places in range(4, 16):
            def rounded(p):
                return tuple(_fixed(v, places) for v in p)
            if len({rounded(p) for p in protected}) != len(set(protected)):
                continue
            if any(len(set(group)) > 1 and len({rounded(p) for p in group}) == 1 for group in groups):
                continue
            self.places = places
            break

    def transform(self, point):
        value = (np.asarray(point, dtype=float)-self.offset)*self.factor
        if value.shape != (2,) or not np.isfinite(value).all():
            raise ValueError('TikZ coordinates must be finite 2D points')
        if self.literal_limit is not None and np.max(np.abs(value)) > self.literal_limit:
            raise ValueError('Literal coordinates exceed100cm; use normalize=True')
        return value

    def pair(self, point):
        return tuple(_fixed(value, self.places) for value in self.transform(point))

    def number(self, value):
        """Format a label offset in its own units, without layout transformation."""
        return _fixed(value, self.places)

    def point(self, point):
        return '('+','.join(self.pair(point))+')'


def path_segments(path):
    """List line/cubic segments, including their starting point."""
    result = []
    previous = None
    i = 0
    while i < len(path.codes):
        code = int(path.codes[i])
        if code == 1:
            previous = path.vertices[i]
            i += 1
        elif code in (2, 4):
            count = 1 if code == 2 else 3
            points = path.vertices[i:i+count]
            result.append([previous, *points])
            previous = points[-1]
            i += count
        else:
            i += 1
    return result


def for_paths(positions, paths, *, normalize=True, size_cm=10):
    """Share the exact TeX transform between exporters and live coordinate labels."""
    vertices = list(positions.values())
    return TexCoordinates(vertices+[p for path in paths for p in path.vertices],
                          vertices=vertices, segments=[s for path in paths for s in path_segments(path)],
                          normalize=normalize, size_cm=size_cm, literal_limit=100)
