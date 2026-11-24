"""Deterministic practice data with a tilted sky, nearby stars and hot pixels."""

import numpy as np

SIZE = (780, 560)
STARS = [
    dict(name='V · 目标星', x=312, y=304, radius=10, inner=19, outer=41, role='target'),
    dict(name='C1 · 东侧比星', x=582, y=180, radius=10, inner=19, outer=41, role='reference', magnitude=11.65),
    dict(name='C2 · 西侧比星', x=179, y=166, radius=10, inner=19, outer=41, role='reference', magnitude=12.29),
    dict(name='K · 校验星', x=492, y=400, radius=10, inner=19, outer=41, role='check'),
]
EXCLUSIONS = [
    dict(name='目标星西侧邻星', x=281, y=306, radius=16),
    dict(name='C1 北侧邻星', x=580, y=149, radius=16),
    dict(name='C2 南东侧邻星', x=204, y=191, radius=16),
]


def image():
    rng = np.random.default_rng(135)
    width, height = SIZE
    yy, xx = np.mgrid[:height, :width]
    field = 482 + 1.37 * xx + .89 * yy + .0012 * (xx - 395) ** 2
    field = field + rng.normal(0, 13, field.shape)
    for star, peak in zip(STARS, (2200, 3100, 1730, 1120)):
        distance = (xx - star['x'] - .23) ** 2 + (yy - star['y'] + .44) ** 2
        field += peak * np.exp(-distance / (2 * 2.65 ** 2))
    for artifact in EXCLUSIONS:
        distance = (xx - artifact['x']) ** 2 + (yy - artifact['y']) ** 2
        field += 1280 * np.exp(-distance / (2 * 3.1 ** 2))
    for _ in range(138):
        x, y = int(rng.integers(8, width - 8)), int(rng.integers(8, height - 8))
        if any((x - star['x']) ** 2 + (y - star['y']) ** 2 < 58 ** 2 for star in STARS):
            continue
        sigma = float(rng.uniform(.7, 2.1))
        amplitude = float(rng.uniform(25, 500))
        slices = np.s_[y-7:y+8, x-7:x+8]
        squared = (xx[slices] - x) ** 2 + (yy[slices] - y) ** 2
        field[slices] += amplitude * np.exp(-squared / (2 * sigma ** 2))
    field[111, 538], field[431, 644] = 65535, 65535
    return np.rint(field).clip(0, 65535).astype(np.uint16)
