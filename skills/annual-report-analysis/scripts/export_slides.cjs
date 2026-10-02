/* Eight-topic research summary; full workpapers remain in Word and Excel. */
const fs = require('node:fs');
const path = require('node:path');
const PptxGenJS = require('pptxgenjs');

const [input, output] = process.argv.slice(2);
if (!input || !output) throw new Error('Usage: node export_slides.cjs CALCULATED_JSON OUTPUT.pptx');
const data = JSON.parse(fs.readFileSync(input, 'utf8').replace(/^\uFEFF/, ''));
const style = JSON.parse(fs.readFileSync(path.join(__dirname, '../assets/report-style.json'), 'utf8'));
const company = data.company;
const zh = company.language === 'zh';
const t = (cn, en) => zh ? cn : en;
const font = zh ? style.font_zh : style.font_en;
const ppt = new PptxGenJS();
ppt.layout = 'LAYOUT_WIDE';
ppt.author = '';
ppt.subject = t('企业年报分析摘要', 'Annual report analysis summary');
ppt.title = `${company.name} ${ppt.subject}`;
ppt.lang = zh ? 'zh-CN' : 'en-US';
ppt.theme = { headFontFace: font, bodyFontFace: font, lang: ppt.lang };
const facts = new Map(data.facts.map(f => [f.id, f]));
const sources = new Map(data.sources.map(s => [s.id, s]));
const derived = new Map([...data.calculations, ...data.checks].map(c => [c.id, c]));
let slideNumber = 0;

const number = (value, unit = 'currency') => {
  if (value === null) return t('未获取或不适用', 'Unavailable or inapplicable');
  let amount = Number(value);
  if (unit === 'currency') amount /= Number(company.display_multiplier);
  if (unit === 'percent') amount *= 100;
  return amount.toLocaleString(zh ? 'zh-CN' : 'en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) +
    (unit === 'percent' ? '%' : unit === 'days' ? t(' 天', ' days') : unit === 'ratio' ? '×' : '');
};
function evidence(refs) {
  return [...new Set(refs.flatMap(ref => {
    const colon = ref.indexOf(':'), kind = ref.slice(0, colon), id = ref.slice(colon + 1);
    if (kind === 'fact') {
      const f = facts.get(id);
      return [`[${f.source_id}] ${f.id} ${f.locator}`];
    }
    if (kind === 'source') {
      const s = sources.get(id);
      return [`[${id}] ${s.title} ${s.locator || ''} ${s.url || ''}`];
    }
    const c = derived.get(id);
    return [`${id}: ${c.expression || c.reason}`, ...evidence(c.inputs.map(i => `fact:${i}`))];
  }))];
}

// Explicit continuation pages preserve selected summary text without shrinking it.
function wrap(text, width) {
  const lines = [];
  for (const paragraph of String(text).split('\n')) {
    let line = '', used = 0;
    for (const ch of paragraph) {
      const weight = ch.charCodeAt(0) > 255 ? 1 : 0.58;
      if (used + weight > width && line) { lines.push(line); line = ''; used = 0; }
      line += ch; used += weight;
    }
    lines.push(line);
  }
  return lines;
}

function slide(title, refs = [], dark = false) {
  const s = ppt.addSlide();
  s.background = { color: dark ? style.ink : 'FFFFFF' };
  s.addText(title, { x: 0.65, y: 0.4, w: 12, h: 0.85, fontFace: font, fontSize: 28,
    bold: true, color: dark ? 'FFFFFF' : style.ink, margin: 0 });
  const notes = evidence(refs);
  const sourceIds = [...new Set(notes.flatMap(line => [...line.matchAll(/\[([^\]]+)\]/g)].map(m => m[1])))];
  s.addText(`${company.identifier} | ${company.period_end} | ` +
    t('完整底稿见 Word / Excel', 'Full workpapers: Word / Excel') +
    (sourceIds.length ? ` | ${sourceIds.slice(0, 3).map(id => `[${id}]`).join(' ')}${sourceIds.length > 3 ? t(' 等，详见备注', ' + more in notes') : ''}` : ''), {
    x: 0.65, y: 7.02, w: 11.5, h: 0.23, fontFace: font, fontSize: 9,
    color: dark ? 'CCD8D1' : style.muted, margin: 0 });
  s.addText(String(++slideNumber), { x: 12.2, y: 7.02, w: 0.4, h: 0.23,
    fontFace: font, fontSize: 10, color: dark ? 'CCD8D1' : style.muted, margin: 0, align: 'right' });
  if (notes.length) s.addNotes(notes.join('\n'));
  return s;
}

function textPages(title, entries, refs = []) {
  const pages = [];
  let page = [];
  for (const text of entries) {
    const lines = wrap(text, 44);
    if (page.length && page.length + lines.length + 1 > 15) { pages.push(page); page = []; }
    while (lines.length > 15) pages.push(lines.splice(0, 15));
    if (page.length) page.push('');
    page.push(...lines);
  }
  if (page.length) pages.push(page);
  if (!pages.length) pages.push([t('未提供相关分析或证据。', 'No corresponding analysis or evidence supplied.')]);
  for (let index = 0; index < pages.length; index++) {
    const s = slide(title + (index ? t(' 续', ' continued') : ''), refs);
    s.addShape(ppt.ShapeType.rect, { x: 0.65, y: 1.55, w: 12.02, h: 5.05,
      fill: { color: style.paper }, line: { color: style.paper } });
    s.addText(pages[index].join('\n'), { x: 0.9, y: 1.76, w: 11.5, h: 4.65,
      fontFace: font, fontSize: 17, color: style.ink, margin: 0, valign: 'top', paraSpaceAfterPt: 3 });
  }
}

function metricPages(title, rows, refs) {
  const widths = [4.15, 2.2, 5.68];
  const expanded = rows.flatMap(row => {
    const cells = row.map((cell, i) => wrap(cell, widths[i] * 72 / 14 * 0.85));
    const parts = [];
    for (let start = 0; start < Math.max(...cells.map(c => c.length)); start += 4) {
      parts.push(cells.map((cell, i) => cell.slice(start, start + 4).join('\n') ||
        (start && i === 0 ? t('续', 'continued') : '')));
    }
    return parts;
  });
  let page = [], height = 0, count = 0;
  function render() {
    if (!page.length) return;
    const s = slide(title + (count++ ? t(' 续', ' continued') : ''), refs);
    s.addText(`${company.currency} ${company.display_unit} | ${company.scope} | ${company.accounting_standard}`, {
      x: 0.65, y: 1.3, w: 12, h: 0.35, fontFace: font, fontSize: 12, color: style.muted, margin: 0 });
    const headers = [t('项目', 'Metric'), t('结果', 'Result'), t('口径或原因', 'Basis or reason')]
      .map(text => ({ text, options: { bold: true, color: 'FFFFFF', fill: style.accent } }));
    s.addTable([headers, ...page], { x: 0.65, y: 1.85, w: 12.03, colW: widths,
      fontFace: font, fontSize: 14, color: style.ink, fill: 'FFFFFF',
      border: { type: 'solid', pt: 0.5, color: 'D9E0DB' }, margin: 0.09,
      valign: 'top', autoPage: false, paraSpaceAfterPt: 0 });
    page = []; height = 0;
  }
  for (const row of expanded) {
    const rowHeight = Math.max(...row.map(cell => cell.split('\n').length)) * 0.24 + 0.2;
    if (height + rowHeight > 4.15) render();
    page.push(row); height += rowHeight;
  }
  render();
}

function currentFact(metric) {
  const duration = ['revenue', 'net_income', 'cfo'].includes(metric);
  const candidates = data.facts.filter(f => f.metric === metric && f.basis === 'reported' &&
    f.use_for_analysis !== false && f.period_end === company.period_end && f.scope === company.scope &&
    f.period_start === (duration ? company.period_start : null) &&
    f.standard === company.accounting_standard && f.currency === company.currency);
  return candidates.length === 1 ? candidates[0] : null;
}
function metrics(factKeys, calculationKeys) {
  const rows = [], refs = [];
  for (const [key, label] of factKeys) {
    const f = currentFact(key);
    rows.push([label, number(f ? f.normalized_value : null), f ? f.period_end + ' / reported' :
      t('缺少唯一同口径数据', 'No unique comparable fact')]);
    if (f) refs.push(`fact:${f.id}`);
  }
  for (const key of calculationKeys) {
    const c = derived.get(key);
    if (c) { rows.push([c.label, number(c.value, c.unit), c.reason || c.period_end]); refs.push(`calculation:${key}`); }
  }
  return { rows, refs };
}
const kind = value => ({ fact: t('披露事实', 'Disclosed fact'), management: t('管理层表述', 'Management statement'),
  inference: t('分析判断', 'Analyst inference') }[value] || '');
const narrative = item => `${kind(item.kind) ? kind(item.kind) + ': ' : ''}${item.text}`;

async function main() {
  const analysis = data.analysis || {};
  const cover = slide(t('企业年报分析', 'Annual report analysis'), [], true);
  cover.addText(company.name, { x: 0.7, y: 1.8, w: 11.9, h: 1.2, fontFace: font,
    fontSize: 38, color: 'FFFFFF', bold: true, margin: 0 });
  cover.addText(`${company.market} | ${company.accounting_standard} | ${company.scope}\n${company.currency} ${company.display_unit}`, {
    x: 0.7, y: 3.35, w: 11.9, h: 0.85, fontFace: font, fontSize: 20, color: 'BED3C7', margin: 0 });
  cover.addText(t('研究摘要\n完整事实、计算、引用与阅读记录见 Word / Excel',
    'Research summary\nFull facts, calculations, citations and review record are in Word / Excel'), {
    x: 0.7, y: 4.8, w: 11.7, h: 1.1, fontFace: font, fontSize: 19, color: 'FFFFFF', margin: 0 });

  const summary = (analysis.summary || []).slice(0, 3);
  textPages(t('关键结论', 'Key findings'), summary.map(narrative), summary.flatMap(i => i.evidence || []));

  const revenueFacts = data.facts.filter(f => f.metric === 'revenue' && f.basis === 'reported' &&
    f.use_for_analysis !== false && f.normalized_value !== null && f.period_start && f.scope === company.scope &&
    f.currency === company.currency && f.standard === company.accounting_standard &&
    ((f.period_end === company.period_end && f.period_start === company.period_start) ||
     (f.period_end === company.prior_period_end && f.period_start === company.prior_period_start)))
    .sort((a, b) => a.period_end.localeCompare(b.period_end));
  const comparable = revenueFacts.length === 2 && revenueFacts[0].period_end !== revenueFacts[1].period_end &&
    Math.abs((Date.parse(revenueFacts[0].period_end) - Date.parse(revenueFacts[0].period_start)) -
      (Date.parse(revenueFacts[1].period_end) - Date.parse(revenueFacts[1].period_start))) <= 7 * 86400000;
  if (comparable) {
    const growth = derived.get('revenue_growth');
    const s = slide(t('经营与收入趋势', 'Operations and revenue trend'), revenueFacts.map(f => `fact:${f.id}`));
    s.addChart(ppt.ChartType.bar, [{ name: t('营业收入', 'Revenue'), labels: revenueFacts.map(f => f.period_end),
      values: revenueFacts.map(f => Number(f.normalized_value) / Number(company.display_multiplier)) }], {
      x: 0.7, y: 1.65, w: 8.25, h: 4.7, catAxisLabelFontFace: font, valAxisLabelFontFace: font,
      catAxisLabelFontSize: 13, valAxisLabelFontSize: 12, chartColors: [style.accent],
      showValue: true, showLegend: false, barDir: 'col', showTitle: true,
      title: `${company.currency} ${company.display_unit}`, titleFontSize: 14,
      valAxisMinVal: 0,
      valGridLine: { color: 'E0E6E1', size: 0.5 }, catGridLine: { style: 'none' } });
    s.addText(t('收入同比', 'Revenue growth'), { x: 9.45, y: 2, w: 3, h: 0.6, fontFace: font, fontSize: 18,
      color: style.muted, margin: 0 });
    s.addText(number(growth ? growth.value : null, 'percent'), { x: 9.45, y: 2.9, w: 3, h: 1,
      fontFace: font, fontSize: 29, color: style.accent, bold: true, margin: 0 });
    if (growth?.reason) s.addText(wrap(growth.reason, 11).join('\n'), { x: 9.45, y: 4.2, w: 3, h: 2,
      fontFace: font, fontSize: 13, color: style.ink, margin: 0 });
  } else {
    const revenue = metrics([['revenue', t('营业收入', 'Revenue')]], ['revenue_change', 'revenue_growth']);
    metricPages(t('经营与收入趋势', 'Operations and revenue trend'), revenue.rows, revenue.refs);
  }

  const profit = metrics([['net_income', t('净利润', 'Net income')], ['cfo', t('经营现金流', 'Operating cash flow')]],
    ['net_margin', 'cash_profit_ratio', 'free_cash_flow']);
  metricPages(t('利润与现金', 'Profit and cash'), profit.rows, profit.refs);
  const balance = metrics([['assets', t('资产总额', 'Total assets')], ['liabilities', t('负债总额', 'Total liabilities')],
    ['equity', t('权益总额', 'Total equity')], ['cash_equivalents', t('现金及等价物', 'Cash equivalents')]], ['liabilities_assets']);
  metricPages(t('资产负债', 'Balance sheet'), balance.rows, balance.refs);

  const riskItems = (analysis.sections || []).filter(s => /审计|会计|风险|audit|account|risk/i.test(s.title))
    .flatMap(s => s.items).slice(0, 3);
  const status = value => ({ matched: t('勾稽相符', 'matched'), difference: t('存在差额', 'difference'),
    unavailable: t('资料不足', 'unavailable'), reviewed: t('已核读', 'reviewed'), partial: t('部分核读', 'partially reviewed') }[value]);
  const checkSummary = data.checks.map(c => `${c.label}: ${status(c.status)}`).join('; ');
  textPages(t('会计与审计关注', 'Accounting and audit matters'), [...riskItems.map(narrative),
    checkSummary, t('勾稽检查仅反映已提供数据的算术关系，不构成审计意见。',
      'Reconciliation checks cover supplied numerical relationships; they are not an audit opinion.')],
    [...riskItems.flatMap(i => i.evidence || []), ...data.checks.map(c => `check:${c.id}`)]);
  const questions = (analysis.questions || []).slice(0, 3);
  textPages(t('待核问题', 'Questions for further review'), questions.map(narrative), questions.flatMap(i => i.evidence || []));

  const coverage = (data.coverage || []).map(c => `${c.section}: ${status(c.status)}`).join('; ');
  const scope = [t('实际阅读覆盖', 'Actual review coverage') + ': ' + (coverage || t('未提供记录', 'No review record supplied')),
    ...(analysis.limitations || []), t('本简报仅选取主要结论及关键指标；全部来源定位、其他指标和分析详见 Word / Excel。每页的详细引文见演讲者备注。',
      'This briefing selects key findings and metrics. Word / Excel contain the complete analysis, source locators and other metrics. Detailed slide citations are in speaker notes.')];
  textPages(t('范围与来源', 'Scope and sources'), scope, data.sources.map(s => `source:${s.id}`));
  await ppt.writeFile({ fileName: output });
}

main().catch(error => { console.error(error.message); process.exitCode = 1; });
