"""Differential photometry, with one conventional local-sky reading per star."""

from math import log10
from statistics import median

from .photometry import measure


def read_field(field, stars, exclusions, target_id):
    readings = {star['id']: measure(field, star, exclusions) for star in stars}
    target = readings.get(target_id)
    references = []
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
    estimates = [row['magnitude'] for row in references if row['magnitude'] is not None]
    return {'target': target_id, 'stars': readings, 'references': references,
            'valid_count': len(estimates), 'magnitude': median(estimates) if estimates else None,
            'spread': max(estimates) - min(estimates) if len(estimates) > 1 else None}
