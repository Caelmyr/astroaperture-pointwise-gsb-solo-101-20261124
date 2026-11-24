"""Revisioned local workspaces and immutable observation records."""

import json
from hashlib import sha256
from pathlib import Path
from shutil import rmtree
from threading import RLock
from uuid import uuid4

from werkzeug.exceptions import NotFound

from image_lab.validation import Conflict, Invalid, identifier, integer, text, timestamp

from . import comparison, demo, photometry, raster


def read(path):
    try:
        return json.loads(path.read_bytes())
    except FileNotFoundError:
        raise NotFound('找不到这份星野记录。') from None


def write(path, value):
    pending = path.with_name('.' + path.name + '-' + uuid4().hex)
    try:
        pending.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        pending.replace(path)
    finally:
        pending.unlink(missing_ok=True)


def find(items, key):
    identifier(key)
    for item in items:
        if item['id'] == key:
            return item
    raise NotFound('找不到这条标注。')


def target(record):
    return next((item['id'] for item in record['stars'] if item['role'] == 'target'), None)


class Workspace:
    def __init__(self, root):
        self.root = Path(root) / 'observations'
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

    def directory(self, key):
        return self.root / identifier(key)

    def open(self, key):
        return read(self.directory(key) / 'field.json')

    def list(self):
        records = (read(path) for path in self.root.glob('[0-9a-f]*/field.json'))
        summary = [{name: record[name] for name in ('id', 'name', 'created', 'synthetic')} for record in records]
        return sorted(summary, key=lambda item: item['created'], reverse=True)

    def create(self, name, field, synthetic=False, filename=None):
        title = text(name, '星野名称', 84, False)
        key = uuid4().hex
        raw = raster.png(field)
        size = [int(field.shape[1]), int(field.shape[0])]
        state = {'id': key, 'name': title, 'created': timestamp(), 'revision': 1, 'size': size,
                 'synthetic': synthetic, 'source_name': filename, 'source_sha256': sha256(raw).hexdigest(),
                 'stars': [], 'exclusions': [], 'raster': raster.describe(field)}
        if synthetic:
            state['stars'] = [dict(id=uuid4().hex, **photometry.aperture(item, size)) for item in demo.STARS]
            state['exclusions'] = [dict(id=uuid4().hex, **photometry.exclusion(item, size)) for item in demo.EXCLUSIONS]
        directory = self.directory(key)
        staging = self.root / ('.' + key)
        staging.mkdir()
        try:
            (staging / 'observations').mkdir()
            (staging / 'source.png').write_bytes(raw)
            write(staging / 'field.json', state)
            staging.rename(directory)
        finally:
            if staging.exists():
                rmtree(staging)
        return state

    def current(self, key, revision):
        record = self.open(key)
        if integer(revision, '修订号', 1) != record['revision']:
            raise Conflict('该星野已经改变，请刷新后重试。')
        return record

    def source(self, key):
        self.open(key)
        return self.directory(key) / 'source.png'

    def raster(self, key):
        return raster.read(self.source(key))

    def commit(self, record):
        record['revision'] += 1
        write(self.directory(record['id']) / 'field.json', record)
        return record

    def annotate(self, key, revision, kind, value, annotation=None):
        parser, maximum = {'stars': (photometry.aperture, 30), 'exclusions': (photometry.exclusion, 24)}[kind]
        with self.lock:
            record = self.current(key, revision)
            items = record[kind]
            data = parser(value, record['size'])
            if annotation is None:
                if len(items) >= maximum:
                    raise Invalid(f'此类标注已达到 {maximum} 个。')
                annotation = uuid4().hex
                items.append({'id': annotation, **data})
            else:
                find(items, annotation).update(data)
            if kind == 'stars' and data['role'] == 'target':
                for item in items:
                    if item['id'] != annotation and item['role'] == 'target':
                        item['role'] = 'check'
            return self.commit(record)

    def delete(self, key, revision, kind, annotation):
        with self.lock:
            record = self.current(key, revision)
            record[kind].remove(find(record[kind], annotation))
            return self.commit(record)

    def save(self, key, revision):
        with self.lock:
            record = self.current(key, revision)
            report = comparison.read_field(self.raster(key), record['stars'], record['exclusions'], target(record))
            if report['target'] is None:
                raise Invalid('请先标记一颗目标星。')
            identity = uuid4().hex
            snapshot = {'id': identity, 'created': timestamp(), 'field': key, 'field_name': record['name'],
                        'field_revision': record['revision'], 'source_sha256': record['source_sha256'],
                        'synthetic': record['synthetic'], 'apertures': record['stars'], 'exclusions': record['exclusions'],
                        'report': report}
            write(self.directory(key) / 'observations' / (identity + '.json'), snapshot)
            return snapshot

    def observation(self, key, observation):
        return read(self.directory(key) / 'observations' / (identifier(observation) + '.json'))

    def observations(self, key):
        self.open(key)
        snapshots = (read(path) for path in (self.directory(key) / 'observations').glob('[0-9a-f]*.json'))
        summary = [{'id': value['id'], 'created': value['created'], 'revision': value['field_revision'],
                    'magnitude': value['report']['magnitude']} for value in snapshots]
        return sorted(summary, key=lambda value: value['created'], reverse=True)
