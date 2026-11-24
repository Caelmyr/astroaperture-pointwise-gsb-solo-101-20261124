"""Differential photometry: a conventional reading and a shared-sky pair check."""

from math import log10
from statistics import median

import numpy as np

from .photometry import measure
from . import sectors


def read_field(field, stars, exclusions, target_id):
    readings = {star['id']: measure(field, star, exclusions) for star in stars}
    found = next((star for star in stars if star['id'] == target_id), None)
    target = readings.get(target_id)
    references = []
    pairs = []
    for star in stars:
        if star['role'] != 'reference':
            continue
        comparison = readings[star['id']]
        reason = comparison['reason']
        estimated = None
        if reason is None:
            if target and target['usable']:
                estimated = star['magnitude'] - 2.5 * log10(target['net'] / comparison['net'])
            else:
                reason = '目标星尚无有效净光'
        references.append({'id': star['id'], 'name': star['name'], 'catalog_mag': star['magnitude'],
                           'net': comparison['net'], 'magnitude': estimated, 'reason': reason})
        pair = sectors.compare(field, found, star, exclusions) if found else {
            'id': star['id'], 'name': star['name'], 'catalog_mag': star['magnitude'], 'directions': [],
            'axis_count': 0, 'usable': False, 'reason': '尚未标记目标星', 'target_net': None,
            'reference_net': None, 'magnitude': None, 'target': None, 'reference': None,
            'target_sectors': [], 'reference_sectors': []}
        if pair['usable']:
            pair['magnitude'] = float(star['magnitude']
                                      - 2.5 * np.log10(pair['target_net'] / pair['reference_net']))
        pairs.append(pair)
    estimates = [row['magnitude'] for row in references if row['magnitude'] is not None]
    paired = [item['magnitude'] for item in pairs if item['magnitude'] is not None]
    return {'target': target_id, 'stars': readings, 'references': references, 'pairs': pairs,
            'valid_count': len(estimates), 'magnitude': median(estimates) if estimates else None,
            'spread': max(estimates) - min(estimates) if len(estimates) > 1 else None,
            'paired_count': len(paired), 'paired_magnitude': median(paired) if paired else None,
            'paired_spread': max(paired) - min(paired) if len(paired) > 1 else None}
