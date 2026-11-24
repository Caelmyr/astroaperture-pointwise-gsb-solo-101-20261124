"""Export the independent aperture readings and reference comparisons."""

import csv
from io import StringIO


def spreadsheet_text(value):
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


def as_csv(snapshot):
    stream = StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['observation', 'source_sha256', 'role', 'aperture', 'x_px', 'y_px', 'r_px', 'net_adu',
                     'sky_adu', 'sky_pixels', 'peak_adu', 'usable', 'catalog_mag', 'estimated_target_mag', 'reason',
                     'pair_directions', 'paired_target_net_adu', 'paired_reference_net_adu', 'paired_target_mag',
                     'paired_reason'])
    report = snapshot['report']
    references = {item['id']: item for item in report['references']}
    pairs = {item['id']: item for item in report.get('pairs', [])}
    for star in snapshot['apertures']:
        result = report['stars'][star['id']]
        reference = references.get(star['id'], {})
        pair = pairs.get(star['id'], {})
        writer.writerow([snapshot['id'], snapshot['source_sha256'], star['role'], spreadsheet_text(star['name']),
                         star['x'], star['y'], star['radius'], result['net'], result['sky'], result['sky_pixels'],
                         result['peak'], result['usable'], star['magnitude'], reference.get('magnitude'),
                         reference.get('reason') or result['reason'], '·'.join(pair.get('directions') or []),
                         pair.get('target_net'), pair.get('reference_net'), pair.get('magnitude'),
                         pair.get('reason')])
    return stream.getvalue().encode('utf-8-sig')


def as_pairs_csv(snapshot):
    stream = StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['observation', 'source_sha256', 'reference', 'catalog_mag', 'directions', 'axes',
                     'target_net_adu', 'reference_net_adu', 'target_sky_adu', 'reference_sky_adu',
                     'target_sky_gradient', 'reference_sky_gradient', 'paired_target_mag', 'usable', 'reason'])
    report = snapshot['report']
    for pair in report.get('pairs', []):
        left = pair.get('target') or {}
        right = pair.get('reference') or {}
        writer.writerow([snapshot['id'], snapshot['source_sha256'], spreadsheet_text(pair['name']),
                         pair['catalog_mag'], '·'.join(pair['directions']), pair['axis_count'],
                         pair['target_net'], pair['reference_net'], left.get('sky'), right.get('sky'),
                         ' '.join(f'{value:.3f}' for value in left['sky_gradient']) if left.get('sky_gradient') else '',
                         ' '.join(f'{value:.3f}' for value in right['sky_gradient']) if right.get('sky_gradient') else '',
                         pair['magnitude'], str(pair['usable']).lower(), pair['reason'] or ''])
    return stream.getvalue().encode('utf-8-sig')
