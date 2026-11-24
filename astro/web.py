"""Browser workflow for one calibrated image and its aperture photometry."""

from io import BytesIO
import json
from pathlib import Path

import numpy as np
from flask import Blueprint, jsonify, render_template, request, send_file

from image_lab import create_app as preparation_app
from image_lab.validation import Invalid, object_value

from . import comparison, demo, photometry, raster, reporting
from .workspace import Workspace, find, target


def body():
    return object_value(request.get_json(silent=True), '星野操作')


def binary(data, media, filename=None):
    return send_file(BytesIO(data), mimetype=media, max_age=0, as_attachment=filename is not None,
                     download_name=filename)


def create_app(root):
    app = preparation_app(root / 'prepare')
    workspace = Workspace(root)
    api = Blueprint('astro', __name__, url_prefix='/astro')

    @app.get('/')
    def home():
        return render_template('astro.html')

    @api.get('/health')
    def health():
        return jsonify(status='ready', service='astroaperture')

    @api.get('/fields')
    def fields():
        return jsonify(workspace.list())

    @api.post('/fields')
    def upload():
        file = request.files.get('image')
        if file is None or not file.filename:
            raise Invalid('请选择一张星野原片。')
        filename = Path(file.filename).name[:120]
        field = raster.decode(file.stream.read(raster.MAX_UPLOAD + 1))
        name = request.form.get('name') or Path(filename).stem[:84]
        return jsonify(workspace.create(name, field, filename=filename)), 201

    @api.post('/demo')
    def practice():
        return jsonify(workspace.create('南天练习场 · 合成图', demo.image(), synthetic=True)), 201

    @api.get('/fields/<key>')
    def field(key):
        return jsonify(workspace.open(key))

    @api.get('/fields/<key>/preview.png')
    def preview(key):
        data = raster.preview(workspace.raster(key), request.args.get('black'), request.args.get('white'),
                              flag=request.args.get('saturated') == '1')
        return binary(data, 'image/png')

    @api.get('/fields/<key>/source.png')
    def source(key):
        return send_file(workspace.source(key), mimetype='image/png', as_attachment=True,
                         download_name=f'star-field-{key[:8]}.png')

    @api.post('/fields/<key>/stars')
    def star_add(key):
        value = body()
        return jsonify(workspace.annotate(key, value.get('revision'), 'stars', value)), 201

    @api.route('/fields/<key>/stars/<annotation>', methods=['PATCH', 'DELETE'])
    def star_edit(key, annotation):
        value = body()
        if request.method == 'DELETE':
            return jsonify(workspace.delete(key, value.get('revision'), 'stars', annotation))
        return jsonify(workspace.annotate(key, value.get('revision'), 'stars', value, annotation))

    @api.post('/fields/<key>/exclusions')
    def mask_add(key):
        value = body()
        return jsonify(workspace.annotate(key, value.get('revision'), 'exclusions', value)), 201

    @api.route('/fields/<key>/exclusions/<annotation>', methods=['PATCH', 'DELETE'])
    def mask_edit(key, annotation):
        value = body()
        if request.method == 'DELETE':
            return jsonify(workspace.delete(key, value.get('revision'), 'exclusions', annotation))
        return jsonify(workspace.annotate(key, value.get('revision'), 'exclusions', value, annotation))

    @api.get('/fields/<key>/measurements')
    def measurements(key):
        current = workspace.open(key)
        return jsonify(comparison.read_field(workspace.raster(key), current['stars'], current['exclusions'], target(current)))

    @api.get('/fields/<key>/stars/<annotation>/diagnostics')
    def diagnostics(key, annotation):
        record = workspace.open(key)
        star = find(record['stars'], annotation)
        field = workspace.raster(key)
        return jsonify(growth=photometry.growth(field, star, record['exclusions']), shape=photometry.profile(field, star))

    @api.post('/fields/<key>/stars/<annotation>/recenter')
    def recenter(key, annotation):
        value = body()
        record = workspace.open(key)
        star = find(record['stars'], annotation)
        center = photometry.recenter(workspace.raster(key), star)
        return jsonify(workspace.annotate(key, value.get('revision'), 'stars', {**star, **center}, annotation))

    @api.route('/fields/<key>/observations', methods=['GET', 'POST'])
    def observations(key):
        if request.method == 'GET':
            return jsonify(workspace.observations(key))
        return jsonify(workspace.save(key, body().get('revision'))), 201

    @api.get('/fields/<key>/observations/<record>')
    def observation(key, record):
        return jsonify(workspace.observation(key, record))

    @api.get('/fields/<key>/observations/<record>/<file>')
    def export(key, record, file):
        snapshot = workspace.observation(key, record)
        if file == 'observation.json':
            data = json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
            return binary(data, 'application/json', file)
        if file == 'observation.csv':
            return binary(reporting.as_csv(snapshot), 'text/csv', file)
        if file == 'pairs.csv':
            return binary(reporting.as_pairs_csv(snapshot), 'text/csv', file)
        raise Invalid('观测记录仅提供 JSON、比星表和配对天空 CSV。')

    @api.post('/fields/<key>/prepare')
    def prepare(key):
        record = workspace.open(key)
        pixels = workspace.raster(key).astype(np.float32) / 65535
        rgb = np.repeat(pixels[..., None], 3, axis=-1)
        asset = app.extensions['assets'].put(rgb, record['name'], {'astro_source_sha256': record['source_sha256']})
        draft = app.extensions['store'].create('星野准备 · ' + record['name'])
        project = app.extensions['frames'].add(draft['id'], draft['revision'], [asset['id']])['project']
        return jsonify(url=f"/prepare?project={project['id']}"), 201

    app.register_blueprint(api)
    return app
