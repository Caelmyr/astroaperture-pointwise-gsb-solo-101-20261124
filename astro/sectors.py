"""Shared sky sectors for a target/reference pair, with a tilted-sky model."""

from math import ceil, floor

import numpy as np

from .raster import SATURATION

LABELS = ('右', '右下', '下', '左下', '左', '左上', '上', '右上')
AXES = ((0, 4), (1, 5), (2, 6), (3, 7))
MINIMUM = 12


def _window(field, x, y, radius):
    """Nominal window including pixels outside the frame, so sectors keep their real size."""
    height, width = field.shape
    left, right = floor(x - radius), ceil(x + radius)
    top, bottom = floor(y - radius), ceil(y + radius)
    xx, yy = np.meshgrid(np.arange(left, right + 1), np.arange(top, bottom + 1))
    inside = (xx >= 0) & (xx < width) & (yy >= 0) & (yy < height)
    values = field[np.clip(yy, 0, height - 1), np.clip(xx, 0, width - 1)].astype(np.float64)
    return xx, yy, inside, values


def inspect(field, star, exclusions):
    """Sample one star's annulus by direction, discarding frame, mask and saturated pixels."""
    x, y = star['x'], star['y']
    xx, yy, inside, values = _window(field, x, y, star['outer'])
    dx, dy = xx - x, yy - y
    distance = dx * dx + dy * dy
    annulus = (distance >= star['inner'] ** 2) & (distance <= star['outer'] ** 2)
    index = np.floor(((np.degrees(np.arctan2(dy, dx)) + 22.5) % 360) / 45).astype(np.int8)
    keep = annulus & inside & (values < SATURATION)
    for excluded in exclusions:
        keep &= (xx - excluded['x']) ** 2 + (yy - excluded['y']) ** 2 > excluded['radius'] ** 2
    complete = np.bincount(index[annulus], minlength=8)
    retained = np.bincount(index[keep], minlength=8)
    sectors = []
    for order, label in enumerate(LABELS):
        count = int(retained[order])
        total = int(complete[order])
        chosen = keep & (index == order)
        sectors.append({'label': label, 'complete': total, 'pixels': count,
                        'usable': count >= MINIMUM and 2 * count >= total,
                        'median': float(np.median(values[chosen])) if count else None})
    return {'x': x, 'y': y, 'radius': star['radius'], 'xx': xx, 'yy': yy, 'inside': inside,
            'values': values, 'dx': dx, 'dy': dy, 'distance': distance, 'index': index,
            'keep': keep, 'sectors': sectors, 'size': (field.shape[1], field.shape[0])}


def _background(dx, dy, values):
    design = np.column_stack((np.ones_like(dx), dx, dy))
    coefficients = np.linalg.lstsq(design, values, rcond=None)[0]
    for _ in range(3):
        residual = values - design @ coefficients
        center = float(np.median(residual))
        scatter = float(np.median(np.abs(residual - center)) * 1.4826)
        trim = np.abs(residual - center) <= 3.5 * scatter
        if scatter <= 0 or trim.all() or np.count_nonzero(trim) < MINIMUM:
            break
        design, values = design[trim], values[trim]
        coefficients = np.linalg.lstsq(design, values, rcond=None)[0]
    residual = values - design @ coefficients
    scatter = float(np.median(np.abs(residual - np.median(residual))) * 1.4826)
    return coefficients, scatter, int(values.size)


def reading(samples, directions):
    """Net aperture light after removing a plane fitted to the shared sky directions."""
    chosen = np.zeros(8, dtype=bool)
    chosen[list(directions)] = True
    sky = samples['keep'] & chosen[samples['index']]
    source = samples['distance'] <= samples['radius'] ** 2
    facts = {'net': None, 'sky': None, 'sky_scatter': None, 'sky_pixels': int(np.count_nonzero(sky)),
             'sky_gradient': None, 'source_pixels': int(np.count_nonzero(source)),
             'peak': int(samples['values'][source].max()), 'saturated': int(np.count_nonzero(
                 samples['values'][source] >= SATURATION)), 'usable': False, 'reason': None}
    coefficients, scatter, samples_used = _background(samples['dx'][sky], samples['dy'][sky],
                                                      samples['values'][sky])
    model = coefficients[0] + coefficients[1] * samples['dx'][source] + coefficients[2] * samples['dy'][source]
    net = float(samples['values'][source].sum() - model.sum())
    facts.update(net=net, sky=float(coefficients[0]), sky_scatter=scatter,
                 sky_gradient=[float(coefficients[1]), float(coefficients[2])], used_pixels=samples_used)
    width, height = samples['size']
    if (samples['x'] - samples['radius'] < 0 or samples['y'] - samples['radius'] < 0
            or samples['x'] + samples['radius'] > width or samples['y'] + samples['radius'] > height):
        facts['reason'] = '孔径超出画幅'
    elif facts['saturated']:
        facts['reason'] = '星点饱和'
    elif facts['net'] <= 0:
        facts['reason'] = '扣天空后净光不为正'
    else:
        facts['usable'] = True
    return facts


def compare(field, target, reference, exclusions):
    """One target/reference pair, sharing only directions usable on both stars."""
    left = inspect(field, target, exclusions)
    right = inspect(field, reference, exclusions)
    left_usable = [number for number, sector in enumerate(left['sectors']) if sector['usable']]
    right_usable = [number for number, sector in enumerate(right['sectors']) if sector['usable']]
    common = [number for number in range(8) if number in left_usable and number in right_usable]
    axes = [axis for axis in AXES if axis[0] in common and axis[1] in common]
    directions = [LABELS[number] for number in common]
    pair = {'id': reference['id'], 'name': reference['name'], 'catalog_mag': reference['magnitude'],
            'directions': directions, 'axis_count': len(axes), 'usable': False, 'reason': None,
            'target_net': None, 'reference_net': None, 'magnitude': None,
            'target': None, 'reference': None,
            'target_sectors': left['sectors'], 'reference_sectors': right['sectors']}
    if not left_usable:
        pair['reason'] = '目标星的天空扇区都不合格'
        return pair
    if not right_usable:
        pair['reason'] = '比星的天空扇区都不合格'
        return pair
    if not common:
        pair['reason'] = '两颗星没有共同合格的天空扇区'
        return pair
    measured_target = reading(left, common)
    measured_reference = reading(right, common)
    pair.update(target=measured_target, reference=measured_reference)
    if measured_target['reason']:
        pair['reason'] = '目标星：' + measured_target['reason']
    elif measured_reference['reason']:
        pair['reason'] = '比星：' + measured_reference['reason']
    elif len(axes) < 2:
        pair['reason'] = f'共同合格扇区只覆盖 {len(axes)} 条反向轴，不足两条'
    else:
        pair['usable'] = True
        pair['target_net'] = measured_target['net']
        pair['reference_net'] = measured_reference['net']
    return pair
