"""Original-pixel aperture and local sky measurements."""

from math import ceil, floor

import numpy as np

from image_lab.validation import Invalid, choice, number, object_value, text

from .raster import SATURATION


def point(value, size):
    return (number(value.get('x'), '中心 X', 0, size[0] - 1),
            number(value.get('y'), '中心 Y', 0, size[1] - 1))


def aperture(value, size):
    value = object_value(value, '孔径')
    x, y = point(value, size)
    radius = number(value.get('radius'), '孔径半径', 2, 45)
    inner = number(value.get('inner'), '天空环内半径', 3, 85)
    outer = number(value.get('outer'), '天空环外半径', 5, 110)
    if inner < radius + 1 or outer < inner + 2:
        raise Invalid('天空环内边须离孔径至少 1 像素，环宽至少 2 像素。')
    role = choice(value.get('role'), '星点用途', ['target', 'reference', 'check'])
    magnitude = number(value.get('magnitude'), '已知星等', -5, 30) if role == 'reference' else None
    return {'name': text(value.get('name'), '星点名', 44, False), 'x': x, 'y': y, 'radius': radius,
            'inner': inner, 'outer': outer, 'role': role, 'magnitude': magnitude}


def exclusion(value, size):
    value = object_value(value, '排除圈')
    x, y = point(value, size)
    return {'name': text(value.get('name'), '排除圈名', 36, False), 'x': x, 'y': y,
            'radius': number(value.get('radius'), '排除圈半径', 2, 110)}


def window(field, x, y, radius):
    height, width = field.shape
    left, right = max(0, floor(x - radius)), min(width, ceil(x + radius) + 1)
    top, bottom = max(0, floor(y - radius)), min(height, ceil(y + radius) + 1)
    xx, yy = np.meshgrid(np.arange(left, right), np.arange(top, bottom))
    return field[top:bottom, left:right], xx, yy


def samples(field, star, exclusions):
    x, y = star['x'], star['y']
    raster, xx, yy = window(field, x, y, star['outer'])
    dx, dy = xx - x, yy - y
    distance = dx * dx + dy * dy
    source = distance <= star['radius'] ** 2
    sky = (distance >= star['inner'] ** 2) & (distance <= star['outer'] ** 2)
    sky &= raster < SATURATION
    for excluded in exclusions:
        near = (xx - excluded['x']) ** 2 + (yy - excluded['y']) ** 2 <= excluded['radius'] ** 2
        sky &= ~near
    return raster, source, sky


def measure(field, star, exclusions):
    raster, source, sky = samples(field, star, exclusions)
    signal, background = raster[source], raster[sky]
    width, height = field.shape[1], field.shape[0]
    x, y, radius = star['x'], star['y'], star['radius']
    facts = {'id': star['id'], 'source_pixels': int(signal.size), 'sky_pixels': int(background.size),
             'peak': int(signal.max()), 'saturated': int(np.count_nonzero(signal >= SATURATION)),
             'sum': int(signal.sum(dtype=np.int64)), 'sky': None, 'sky_scatter': None, 'net': None,
             'sky_error': None, 'usable': False, 'reason': None}
    if background.size >= 12:
        level = float(np.median(background))
        scatter = float(np.median(np.abs(background.astype(np.float64) - level)) * 1.4826)
        facts.update(sky=level, sky_scatter=scatter, net=facts['sum'] - signal.size * level,
                     sky_error=scatter * np.sqrt(signal.size + signal.size ** 2 / background.size))
    if x - radius < 0 or y - radius < 0 or x + radius >= width or y + radius >= height:
        facts['reason'] = '孔径超出画幅'
    elif facts['saturated']:
        facts['reason'] = '星点饱和'
    elif facts['sky'] is None:
        facts['reason'] = '有效天空像素少于 12'
    elif facts['net'] <= 0:
        facts['reason'] = '扣天空后净光不为正'
    else:
        facts['usable'] = True
    return facts


def growth(field, star, exclusions):
    largest = min(int(star['inner'] - 1), 45)
    radii = sorted(set(map(int, np.rint(np.linspace(2, largest, min(14, largest - 1))))) | {star['radius']})
    return [{'radius': radius, 'net': measure(field, {**star, 'radius': radius}, exclusions)['net']}
            for radius in radii]


def recenter(field, star):
    x, y = star['x'], star['y']
    radius = max(3, min(star['radius'], 10))
    raster, xx, yy = window(field, x, y, radius)
    support = (xx - x) ** 2 + (yy - y) ** 2 <= radius ** 2
    values = raster[support].astype(np.float64)
    weights = np.maximum(values - np.percentile(values, 45), 0)
    if not np.any(weights):
        raise Invalid('这里没有可定位的亮斑。')
    return dict(x=round(float(np.average(xx[support], weights=weights)), 2),
                y=round(float(np.average(yy[support], weights=weights)), 2))


def profile(field, star):
    radius = min(110, ceil(star['outer']))
    width, height = field.shape[1], field.shape[0]
    x, y = round(star['x']), round(star['y'])
    left, right = max(0, x - radius), min(width - 1, x + radius)
    top, bottom = max(0, y - radius), min(height - 1, y + radius)
    return {'horizontal': {'at': y, 'start': left, 'values': field[y, left:right+1].tolist()},
            'vertical': {'at': x, 'start': top, 'values': field[top:bottom+1, x].tolist()}}
