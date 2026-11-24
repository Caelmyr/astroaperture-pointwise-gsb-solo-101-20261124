"""Export the independent aperture readings and reference comparisons."""

import csv
from io import StringIO


def spreadsheet_text(value):
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


def as_csv(snapshot):
    stream = StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['observation', 'source_sha256', 'role', 'aperture', 'x_px', 'y_px', 'r_px', 'net_adu',
                     'sky_adu', 'sky_pixels', 'peak_adu', 'usable', 'catalog_mag', 'estimated_target_mag', 'reason'])
    report = snapshot['report']
    references = {item['id']: item for item in report['references']}
    for star in snapshot['apertures']:
        result = report['stars'][star['id']]
        reference = references.get(star['id'], {})
        writer.writerow([snapshot['id'], snapshot['source_sha256'], star['role'], spreadsheet_text(star['name']),
                         star['x'], star['y'], star['radius'], result['net'], result['sky'], result['sky_pixels'],
                         result['peak'], result['usable'], star['magnitude'], reference.get('magnitude'),
                         reference.get('reason') or result['reason']])
    return stream.getvalue().encode('utf-8-sig')
