'use strict';

const $ = id => document.getElementById(id);
const roles = {target: '目标星', reference: '比星', check: '校验星'};
const state = {field: null, active: null, selectedKind: null, method: 'growth', drawing: null,
  stretch: null, readingVersion: 0, diagnosticVersion: 0, form: null};
const apiRoot = '/astro';
const froot = () => `${apiRoot}/fields/${state.field.id}`;
const fmt = (value, digits = 1) => value === null || value === undefined ? '—' : Number(value).toFixed(digits);
const ns = 'http://www.w3.org/2000/svg';
let toastTimer;

function el(tag, value, className) {
  const node = document.createElement(tag);
  if (value !== undefined) node.textContent = value;
  if (className) node.className = className;
  return node;
}
function svg(tag, props, text) {
  const node = document.createElementNS(ns, tag);
  Object.entries(props).forEach(([key, value]) => node.setAttribute(key, value));
  if (text !== undefined) node.textContent = text;
  return node;
}
async function api(url, method = 'GET', data) {
  const options = {method};
  if (data instanceof FormData) options.body = data;
  else if (data !== undefined) {
    options.headers = {'Content-Type': 'application/json'};
    options.body = JSON.stringify(data);
  }
  const response = await fetch(url, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '请求失败');
  return result;
}
function announce(value, global = false) {
  if (!global) {
    $('status').textContent = value;
    return;
  }
  $('globalStatus').hidden = !value;
  $('globalStatus').textContent = value;
  clearTimeout(toastTimer);
  if (value) toastTimer = setTimeout(() => {$('globalStatus').hidden = true;}, 5500);
}
function safe(operation, area) {
  return async event => {
    try { await operation(event); }
    catch (error) {
      if (area) $(area).textContent = error.message;
      else announce(error.message, true);
    }
  };
}
function bind(id, operation, area) {$(id).addEventListener('click', safe(operation, area));}

function entry(parent, label, detail, tone, operation, active, attribute, value) {
  const button = el('button', undefined, `entry${active ? ' selected' : ''}`);
  button.type = 'button';
  if (attribute) button.dataset[attribute] = value;
  const name = el('span', label);
  if (detail) name.append(el('small', detail));
  button.append(el('span', undefined, `entry-bullet ${tone ? `point ${tone}` : ''}`), name);
  button.addEventListener('click', safe(operation));
  parent.append(button);
}
function placeholder(parent, text) {parent.append(el('p', text, 'muted'));}
async function listFields() {
  const fields = await api(`${apiRoot}/fields`);
  const list = $('fieldList');
  list.replaceChildren();
  if (!fields.length) placeholder(list, '暂无原片');
  fields.forEach(field => entry(list, field.name, field.synthetic ? '合成练习' : '', null,
    () => loadField(field.id), state.field?.id === field.id, 'field', field.id));
}
async function listObservations() {
  const field = state.field.id;
  const records = await api(`${froot()}/observations`);
  if (state.field?.id !== field) return;
  const list = $('observationList');
  list.replaceChildren();
  if (!records.length) placeholder(list, '暂无观测记录');
  records.forEach(record => {
    const stamp = new Date(record.created).toLocaleString('zh-CN', {hour12: false});
    const detail = record.paired_magnitude == null ? stamp : `${stamp} · 配对 ${fmt(record.paired_magnitude, 3)}`;
    entry(list, `${fmt(record.magnitude, 3)} mag`, detail, null, () => showObservation(record.id), false, 'observation', record.id);
  });
}
function choose(kind, id) {
  state.active = id;
  state.selectedKind = kind;
  renderAnnotations();
  renderReading();
  return updateDiagnostic();
}
function activeItem() {
  return state.field?.[state.selectedKind]?.find(item => item.id === state.active);
}
function defaultTarget() {
  return state.field.stars.find(star => star.role === 'target') || state.field.stars[0];
}
function renderAnnotations() {
  const stars = $('starList');
  const exclusions = $('exclusionList');
  stars.replaceChildren();
  exclusions.replaceChildren();
  if (!state.field.stars.length) placeholder(stars, '在星图上标注星点');
  if (!state.field.exclusions.length) placeholder(exclusions, '暂无排除圈');
  state.field.stars.forEach(star => entry(stars, star.name, roles[star.role], star.role,
    () => choose('stars', star.id), state.active === star.id, 'star', star.id));
  state.field.exclusions.forEach(mask => entry(exclusions, mask.name, `${fmt(mask.radius, 0)} px`, 'mask',
    () => choose('exclusions', mask.id), state.active === mask.id, 'mask', mask.id));
  const overlay = $('overlay');
  overlay.setAttribute('viewBox', `0 0 ${state.field.size.join(' ')}`);
  overlay.replaceChildren();
  for (const kind of ['exclusions', 'stars']) {
    for (const item of state.field[kind]) {
      const type = item.role || 'mask';
      const group = svg('g', {class: type});
      const activeClass = state.active === item.id ? ' chosen' : '';
      const base = {cx: item.x, cy: item.y};
      group.append(svg('circle', {...base, r: item.radius, class: `geometry${activeClass}`}));
      if (kind === 'stars') {
        group.append(svg('circle', {...base, r: item.inner, class: 'geometry ring'}),
          svg('circle', {...base, r: item.outer, class: 'geometry ring'}),
          svg('text', {x: item.x + item.outer + 5, y: item.y - 5, class: 'point-name'}, item.name.split(' · ')[0]));
      }
      const hit = svg('circle', {...base, r: item.radius + 4, class: 'point-hit'});
      hit.addEventListener('click', safe(async event => {
        if (state.drawing) return;
        event.stopPropagation();
        await choose(kind, item.id);
      }));
      group.append(hit);
      overlay.append(group);
    }
  }
}
function preview() {
  const options = new URLSearchParams();
  if (state.stretch) {
    options.set('black', state.stretch[0]);
    options.set('white', state.stretch[1]);
  }
  if ($('saturation').checked) options.set('saturated', '1');
  $('preview').src = `${froot()}/preview.png?${options}`;
}
function renderHistogram() {
  const facts = state.field.raster;
  const greatest = Math.max(1, ...facts.histogram);
  $('histogram').replaceChildren(...facts.histogram.map((count, bin) => {
    const bar = el('span');
    bar.style.height = `${Math.min(100, 100 * Math.log1p(count) / Math.log1p(greatest))}%`;
    bar.title = `${bin * 2048}–${bin * 2048 + 2047} ADU · ${count} 像素`;
    return bar;
  }));
  $('rasterFacts').textContent = `范围 ${facts.min}–${facts.max} · 中位 ${fmt(facts.median, 0)} · 饱和 ${facts.saturated} px`;
}
async function showField(field) {
  state.field = field;
  state.report = null;
  state.stretch = null;
  state.active = defaultTarget()?.id;
  state.selectedKind = state.active ? 'stars' : null;
  state.drawing = null;
  $('overlay').classList.remove('drawing');
  $('empty').hidden = true;
  $('desk').hidden = false;
  $('annotationLibrary').hidden = false;
  $('fieldName').textContent = field.name;
  $('fieldFacts').textContent = `${field.size.join(' × ')} px · 16 位线性灰度 · ${field.synthetic ? '合成练习原片' : field.source_name}`;
  $('sourceDownload').href = `${froot()}/source.png`;
  $('saturation').checked = false;
  autoStretch();
  renderHistogram();
  renderAnnotations();
  renderReading();
  history.replaceState(null, '', `/?field=${field.id}`);
  announce('');
  await Promise.all([listFields(), listObservations(), updateReadings(), updateDiagnostic()]);
}
function autoStretch() {
  state.stretch = null;
  $('black').value = Math.floor(state.field.raster.levels[0]);
  $('white').value = Math.ceil(state.field.raster.levels[1]);
  preview();
}
async function loadField(id) {await showField(await api(`${apiRoot}/fields/${id}`));}
async function demo() {await showField(await api(`${apiRoot}/demo`, 'POST'));}

function renderReadings() {
  const report = state.report;
  const caret = report?.magnitude;
  $('targetMagnitude').replaceChildren(document.createTextNode(fmt(caret, 3)));
  if (caret != null) $('targetMagnitude').append(el('small', 'mag'));
  const paired = report?.paired_magnitude;
  $('pairedMagnitude').replaceChildren(document.createTextNode(fmt(paired, 3)));
  if (paired != null) $('pairedMagnitude').append(el('small', 'mag'));
  $('targetLabel').textContent = state.field.stars.find(star => star.id === report?.target)?.name || '先标注目标星';
  $('referenceCount').textContent = `${report?.valid_count ?? 0} 颗有效比星`;
  $('pairedCount').textContent = `${report?.paired_count ?? 0} 对有效`;
  $('refSpread').textContent = report?.spread == null ? '' : `普通差分各比星结果相差 ${fmt(report.spread, 3)} mag`;
  $('pairedSpread').textContent = report?.paired_spread == null ? '' : `配对天空各对结果相差 ${fmt(report.paired_spread, 3)} mag`;
  const rows = (report?.references || []).map(item => {
    const tr = el('tr');
    const title = el('td', item.name);
    if (item.reason) title.append(el('div', item.reason, 'muted'));
    tr.append(title, el('td', fmt(item.catalog_mag, 3)), el('td', fmt(item.magnitude, 3)));
    return tr;
  });
  if (!rows.length) {
    const row = el('tr');
    const cell = el('td', '添加已知星等的比星后计算。', 'no-ref');
    cell.colSpan = 3;
    row.append(cell);
    rows.push(row);
  }
  $('references').replaceChildren(...rows);
  $('pairs').replaceChildren(...pairRows(report?.pairs || []));
}
function pairRows(pairs) {
  if (!pairs.length) {
    const row = el('tr');
    const cell = el('td', '添加比星后核对共同合格的天空扇区。', 'no-ref');
    cell.colSpan = 4;
    row.append(cell);
    return [row];
  }
  return pairs.map(item => {
    const row = el('tr');
    const title = el('td', item.name);
    const directions = item.directions.length ? item.directions.join('·') : '无共同扇区';
    title.append(el('span', item.directions.length ? `${directions} · ${item.axis_count} 轴` : directions, 'pair-direction'));
    if (item.reason) title.append(el('span', item.reason, 'pair-reason'));
    row.append(title, el('td', fmt(item.target_net, 0)), el('td', fmt(item.reference_net, 0)),
      el('td', fmt(item.magnitude, 3)));
    row.title = sectorNote(item);
    return row;
  });
}
function sectorNote(item) {
  const describe = stars => (stars || []).map(sector => `${sector.label} ${sector.pixels}/${sector.complete}`).join('，');
  return `目标星扇区像素：${describe(item.target_sectors)}\n比星扇区像素：${describe(item.reference_sectors)}`;
}
function renderReading() {
  renderReadings();
  const item = activeItem();
  const stellar = state.selectedKind === 'stars' && item;
  $('editStar').hidden = !stellar;
  $('editMask').hidden = state.selectedKind !== 'exclusions' || !item;
  $('recenter').hidden = !stellar;
  $('activeLabel').textContent = item ? item.name : '选择一颗星点。';
  const value = stellar ? state.report?.stars?.[item.id] : null;
  const container = $('reading');
  container.replaceChildren();
  if (state.selectedKind === 'exclusions' && item) {
    container.append(el('dt', '排除范围'), el('dd', `${fmt(item.radius, 1)} px`));
  }
  if (!value) return;
  const rows = [['净光', `${fmt(value.net, 0)} ADU`], ['天空中位', `${fmt(value.sky, 1)} ADU`],
    ['天空像素', `${value.sky_pixels} px`], ['孔径像素', `${value.source_pixels} px`],
    ['峰值', `${value.peak} ADU`], ['天空散布', `${fmt(value.sky_scatter, 1)} ADU`]];
  if (value.reason) rows.push(['读数状态', value.reason]);
  rows.forEach(([key, answer]) => container.append(el('dt', key), el('dd', answer)));
}
async function updateReadings() {
  const version = ++state.readingVersion;
  const report = await api(`${froot()}/measurements`);
  if (version !== state.readingVersion) return;
  state.report = report;
  renderReading();
}
function chartSeries(series, labels) {
  const chart = $('chart');
  chart.replaceChildren();
  const points = series.flatMap(line => line.points).filter(point => Number.isFinite(point.y));
  chart.toggleAttribute('hidden', !points.length);
  if (!points.length) return;
  const bounds = Object.fromEntries(['x', 'y'].map(axis => {
    const values = points.map(point => point[axis]);
    return [axis, [Math.min(...values), Math.max(...values)]];
  }));
  const scaleX = x => 52 + 495 * (x - bounds.x[0]) / (bounds.x[1] - bounds.x[0] || 1);
  const scaleY = y => 89 - 67 * (y - bounds.y[0]) / (bounds.y[1] - bounds.y[0] || 1);
  chart.append(svg('path', {d: 'M52 18V89H550', stroke: '#596a7d', fill: 'none'}));
  for (const line of series) {
    const projected = line.points.filter(point => Number.isFinite(point.y)).map(point => `${scaleX(point.x)},${scaleY(point.y)}`);
    chart.append(svg('polyline', {points: projected.join(' '), stroke: line.color, 'stroke-width': 2, fill: 'none'}));
  }
  const annotate = (x, y, value, anchor = 'start') => chart.append(svg('text', {x, y, 'text-anchor': anchor, fill: '#adb9c9', 'font-size': 11}, value));
  annotate(46, 24, fmt(bounds.y[1], 0), 'end');
  annotate(46, 90, fmt(bounds.y[0], 0), 'end');
  annotate(52, 105, fmt(bounds.x[0], 0));
  annotate(550, 105, fmt(bounds.x[1], 0), 'end');
  annotate(310, 105, labels, 'middle');
}
async function updateDiagnostic() {
  const version = ++state.diagnosticVersion;
  const item = activeItem();
  $('chart').setAttribute('hidden', '');
  $('chartHint').textContent = '选择星点孔径查看诊断。';
  if (state.selectedKind !== 'stars' || !item) return;
  const data = await api(`${froot()}/stars/${item.id}/diagnostics`);
  if (version !== state.diagnosticVersion) return;
  if (state.method === 'growth') {
    $('chartHint').textContent = `${item.name} · 孔径增大时的净光 ADU`;
    chartSeries([{color: '#a9dfc2', points: data.growth.map(read => ({x: read.radius, y: read.net}))}], '半径 / px');
  } else {
    $('chartHint').textContent = `${item.name} · 水平切线为青色，竖直切线为蓝色`;
    const lines = [data.shape.horizontal, data.shape.vertical].map((line, index) => ({
      color: index ? '#84b9fb' : '#a9dfc2',
      points: line.values.map((y, x) => ({x: x + line.start - Math.round(index ? item.y : item.x), y})),
    }));
    chartSeries(lines, '距中心 / px');
  }
}
async function setChart(value) {
  state.method = value;
  for (const [id, tab] of [['growthTab', 'growth'], ['profileTab', 'profile']]) {
    $(id).classList.toggle('current', tab === value);
    $(id).setAttribute('aria-pressed', String(tab === value));
  }
  await updateDiagnostic();
}

function setDrawing(kind) {
  state.drawing = kind;
  $('overlay').classList.add('drawing');
  announce(kind === 'stars' ? '点星图上的星点中心。' : '点星图上的干扰中心。');
}
function roleForm() {
  const role = $('annotationForm').elements.role;
  const show = state.form?.kind === 'stars' && role.value === 'reference';
  document.querySelector('.reference-only').hidden = !show;
  $('annotationForm').elements.magnitude.required = show;
}
function editAnnotation(kind, existing, center) {
  const item = existing || (kind === 'stars'
    ? {name: '', ...center, radius: 10, inner: 19, outer: 41, role: defaultTarget() ? 'check' : 'target'}
    : {name: '', ...center, radius: 15});
  state.form = {kind, id: existing?.id, prev: state.field.id};
  $('annotationTitle').textContent = kind === 'stars' ? '星点孔径' : '排除圈';
  $('annotationMessage').textContent = '';
  const form = $('annotationForm');
  form.reset();
  for (const field of Object.keys(item)) {
    if (form.elements.namedItem(field)) form.elements.namedItem(field).value = item[field] ?? '';
  }
  document.querySelectorAll('.star-only').forEach(node => {node.hidden = kind !== 'stars';});
  $('removeAnnotation').hidden = !existing;
  roleForm();
  $('annotationDialog').showModal();
  form.elements.name.focus();
}
async function afterChange(record, kind, id) {
  state.field = record;
  state.selectedKind = id ? kind : defaultTarget() ? 'stars' : null;
  state.active = id || defaultTarget()?.id;
  renderAnnotations();
  renderReading();
  await Promise.all([updateReadings(), updateDiagnostic()]);
}
async function showObservation(id) {
  const link = `${froot()}/observations/${id}`;
  const report = await api(link);
  const result = report.report;
  const list = $('observationText');
  list.replaceChildren(el('p', `${report.field_name} · 原片修订 ${report.field_revision}`, 'muted'),
    el('p', `目标星等 ${fmt(result.magnitude, 3)} mag · ${result.valid_count} 颗有效比星`));
  result.references.forEach(row => list.append(el('p', `${row.name} · ${row.reason || fmt(row.magnitude, 3) + ' mag'}`, 'muted')));
  if (result.paired_magnitude != null) list.append(el('p', `配对天空 ${fmt(result.paired_magnitude, 3)} mag · ${result.paired_count} 对有效`, 'muted'));
  (result.pairs || []).forEach(row => list.append(el('p',
    `${row.name} · ${row.usable ? `${row.directions.join('·')} · ${fmt(row.magnitude, 3)} mag` : row.reason}`, 'muted')));
  $('downloadJSON').href = `${link}/observation.json`;
  $('downloadCSV').href = `${link}/observation.csv`;
  $('downloadPairs').href = `${link}/pairs.csv`;
  $('observationDialog').showModal();
}

bind('startDemo', demo);
bind('emptyDemo', demo);
bind('openUpload', () => {
  $('uploadMessage').textContent = '';
  $('uploadForm').reset();
  $('uploadDialog').showModal();
});
$('uploadForm').addEventListener('submit', safe(async event => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button[type=submit]');
  button.disabled = true;
  $('uploadMessage').textContent = '正在读取原片…';
  try {
    const field = await api(`${apiRoot}/fields`, 'POST', new FormData(event.currentTarget));
    $('uploadDialog').close();
    await showField(field);
  } finally {button.disabled = false;}
}, 'uploadMessage'));
for (const button of document.querySelectorAll('.close-dialog')) {
  button.addEventListener('click', () => button.closest('dialog').close());
}
bind('addStar', () => setDrawing('stars'));
bind('addMask', () => setDrawing('exclusions'));
$('overlay').addEventListener('click', safe(event => {
  if (!state.drawing) return;
  const box = $('overlay').getBoundingClientRect();
  const [width, height] = state.field.size;
  const center = {x: +Math.min(width - 1, (event.clientX - box.left) * width / box.width).toFixed(2),
    y: +Math.min(height - 1, (event.clientY - box.top) * height / box.height).toFixed(2)};
  const kind = state.drawing;
  state.drawing = null;
  $('overlay').classList.remove('drawing');
  announce('');
  editAnnotation(kind, null, center);
}));
$('annotationForm').elements.role.addEventListener('change', roleForm);
$('annotationForm').addEventListener('submit', safe(async event => {
  event.preventDefault();
  const {kind, id, prev} = state.form;
  if (prev !== state.field.id) throw new Error('原片已切换，请重新打开标注。');
  const fields = event.currentTarget.elements;
  const value = {revision: state.field.revision, name: fields.name.value, x: fields.x.value,
    y: fields.y.value, radius: fields.radius.value};
  if (kind === 'stars') Object.assign(value, {inner: fields.inner.value, outer: fields.outer.value,
    role: fields.role.value, magnitude: fields.magnitude.value});
  const updated = await api(`${froot()}/${kind}${id ? `/${id}` : ''}`, id ? 'PATCH' : 'POST', value);
  $('annotationDialog').close();
  await afterChange(updated, kind, id || updated[kind].at(-1).id);
  announce('标注已保存');
}, 'annotationMessage'));
bind('removeAnnotation', async () => {
  const {kind, id, prev} = state.form;
  if (prev !== state.field.id) throw new Error('原片已切换，请重新打开标注。');
  const record = await api(`${froot()}/${kind}/${id}`, 'DELETE', {revision: state.field.revision});
  $('annotationDialog').close();
  await afterChange(record);
  announce('标注已删除');
}, 'annotationMessage');
bind('editStar', () => editAnnotation('stars', activeItem()));
bind('editMask', () => editAnnotation('exclusions', activeItem()));
bind('recenter', async () => {
  const star = activeItem();
  const updated = await api(`${froot()}/stars/${star.id}/recenter`, 'POST', {revision: state.field.revision});
  await afterChange(updated, 'stars', star.id);
  announce('已按亮度重新定位中心');
});
bind('autoStretch', autoStretch);
bind('applyStretch', () => {
  const black = $('black').valueAsNumber;
  const white = $('white').valueAsNumber;
  if (!Number.isFinite(black) || !Number.isFinite(white) || black < 0 || white > 65536 || white <= black) {
    throw new Error('显示范围须在 0 到 65536 ADU，白点须高于黑点。');
  }
  state.stretch = [black, white];
  preview();
  announce('显示范围已切换');
});
$('saturation').addEventListener('change', preview);
bind('growthTab', () => setChart('growth'));
bind('profileTab', () => setChart('profile'));
bind('saveObs', async () => {
  const record = await api(`${froot()}/observations`, 'POST', {revision: state.field.revision});
  await Promise.all([listObservations(), showObservation(record.id)]);
  announce('本次测光已保存');
});
bind('copyPrepare', async () => {
  const {url} = await api(`${froot()}/prepare`, 'POST');
  location.assign(url);
});
void safe(async () => {
  const selected = new URLSearchParams(location.search).get('field');
  if (selected) await loadField(selected);
  else await listFields();
})();
