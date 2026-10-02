const fs = require('node:fs');
const pptxgen = require('pptxgenjs');

async function main() {
  const [input, output] = process.argv.slice(2);
  if (!input || !output) throw new Error('Usage: node export_pptx.cjs presentation-data.json output.pptx');
  const d = JSON.parse(fs.readFileSync(input, 'utf8'));
  const pptx = new pptxgen();
  pptx.layout = 'LAYOUT_WIDE';
  pptx.author = 'annual-report-analysis';
  pptx.subject = d.mandate.purpose;
  pptx.title = d.mandate.title;
  pptx.lang = d.mandate.language;
  pptx.theme = { headFontFace: 'Microsoft YaHei', bodyFontFace: 'Microsoft YaHei', lang: d.mandate.language };
  const dark = '213B45', green = '237F72', paper = 'F5F7F6', ink = '1F2933';
  const segmenter = new Intl.Segmenter('zh', {granularity:'word'});
  // Reserve one em per character so CJK text is laid out before PowerPoint opens it.
  const lines = (text, width, size) => String(text).split('\n').flatMap(paragraph => {
    const count = Math.max(1, Math.floor(width * 72 / (size * 1.04)));
    const result = []; let line = '';
    for (const {segment} of segmenter.segment(paragraph)) {
      const chars = Array.from(segment);
      for (let i = 0; i < chars.length; i += count) {
        const token = chars.slice(i, i + count).join('');
        if (Array.from(line + token).length > count) {result.push(line); line = '';}
        line += token;
      }
    }
    result.push(line);
    return result;
  });
  const fitted = (text, width, height, maximum) => {
    let size = maximum;
    while (size > 8 && lines(text, width, size).length * size * 1.3 > height * 72) size--;
    return {text:lines(text, width, size).join('\n'), size};
  };
  const paragraphs = (text, width, height, size) => {
    const wrapped = lines(text, width, size), count = Math.max(1, Math.floor(height * 72 / (size * 1.3)));
    const result = [];
    for (let i = 0; i < wrapped.length; i += count) result.push(wrapped.slice(i, i + count).join('\n'));
    return result;
  };
  let n = 0;
  const page = (title, darkPage = false, quantitative = false) => {
    const s = pptx.addSlide();
    s.background = { color: darkPage ? dark : paper };
    const heading = fitted(title, 12.1, 0.8, 27);
    s.addText(heading.text, { x: 0.6, y: 0.4, w: 12.1, h: 0.8, fontSize: heading.size, bold: true, color: darkPage ? 'FFFFFF' : dark, margin: 0, valign:'top', lineSpacingMultiple:1 });
    if (!quantitative) s.addShape(pptx.ShapeType.line, { x: 0.6, y: 1.3, w: 12.1, h: 0, line: { color: green, width: 2 } });
    s.addText(`${d.mandate.entity}  |  ${d.mandate.period_end}  |  ${d.mandate.version}  |  ${++n}`, { x: 0.6, y: 7.08, w: 12.1, h: 0.2, fontSize: 9, color: darkPage ? 'B9D1CC' : '586874', margin: 0 });
    return s;
  };
  let s = page(d.mandate.title, true);
  const purpose = fitted(d.mandate.purpose, 11.8, 1.25, 24);
  s.addText(purpose.text, { x: 0.7, y: 1.8, w: 11.8, h: 1.25, fontSize: purpose.size, color: 'FFFFFF', margin: 0, valign:'top', lineSpacingMultiple:1 });
  s.addText(`会计基础 ${d.mandate.accounting_basis}\n范围 ${d.mandate.scope}\n信息截止 ${d.mandate.cutoff}`, { x: 0.7, y: 3.5, w: 11.8, h: 1.5, fontSize: 19, color: 'C6DEDA', margin: 0 });
  s.addNotes(d.mandate.limitations.join('\n'));
  const unknownDates = d.sources.filter(source => source.published === null).map(source => source.id);
  if (unknownDates.length) s.addText(`来源 ${unknownDates.join(', ')} 公布日期未核验。不得将当前内容分析称为历史时点可用性验证。`,
    {x:0.7,y:5.35,w:11.8,h:0.95,fontSize:16,color:'FFFFFF',margin:0,fit:'shrink'});
  if (d.mandate.limitations.length) {
    for (const body of paragraphs(d.mandate.limitations.join('\n\n'), 12, 4.9, 16)) {
      s = page('分析范围与限制');
      s.addText(body, {x:0.65,y:1.6,w:12,h:4.9,fontSize:16,color:ink,margin:0,valign:'top',lineSpacingMultiple:1});
    }
  }
  const findings = Object.fromEntries(d.findings.map(f => [f.id, f]));
  for (const section of d.sections) {
    const selected = section.findings.map(id => findings[id]);
    const figures = section.figures.slice(0, 4).map(id => d.figures[id]);
    const width = figures.length ? 7.65 : 12;
    const chunks = selected.length ? selected.flatMap(f => paragraphs(`${f.conclusion}\n\n判断改变条件\n${f.changes_if}`, width, 3.35, 18).map(body => ({f,body}))) : [{}];
    for (const [index, chunk] of chunks.entries()) {
      s = page(section.title + (chunks.length > 1 ? ` ${index + 1}` : ''));
      const f = chunk.f;
      if (f) {
        const heading = fitted(f.title, width, 1.1, 22);
        s.addText(heading.text, { x: 0.65, y: 1.58, w: width, h: 1.1, fontSize: heading.size, color: dark, bold: true, margin: 0, valign:'top', lineSpacingMultiple:1 });
        s.addText(chunk.body, { x: 0.65, y: 2.87, w: width, h: 3.35, fontSize: 18, color: ink, margin: 0, valign:'top', lineSpacingMultiple:1 });
        s.addNotes([f.id, f.question, f.mechanism, ...f.alternatives, `Evidence: ${f.evidence.join(', ')}`, `Counterevidence: ${f.counterevidence.join(', ')}`].join('\n'));
      }
      figures.forEach((v, i) => {
        const y = 1.65 + i * 1.18;
        s.addShape(pptx.ShapeType.rect, { x: 8.7, y, w: 4, h: 1.04, fill: { color: 'E6EFEC' }, line: { color: 'E6EFEC' } });
        const label = fitted(v.label, 3.6, 0.3, 12), value = fitted(v.display, 3.6, 0.43, 18);
        s.addText(label.text, { x: 8.9, y: y + 0.09, w: 3.6, h: 0.3, fontSize: label.size, color: dark, margin: 0, valign:'top', lineSpacingMultiple:1 });
        s.addText(value.text, { x: 8.9, y: y + 0.49, w: 3.6, h: 0.43, fontSize: value.size, bold: true, color: green, margin: 0, valign:'top', lineSpacingMultiple:1 });
      });
      const refs = [...new Set([...figures.flatMap(v => v.evidence), ...(f ? f.evidence : [])])];
      const sources = fitted(`来源记录 ${refs.slice(0,3).join(' / ')}${refs.length>3 ? ' 等' : ''}；全部来源及位置见报告、底稿与备注`, 12, 0.3, 9);
      s.addText(sources.text, { x: 0.65, y: 6.57, w: 12, h: 0.3, fontSize: sources.size, color: '586874', margin: 0, valign:'top', lineSpacingMultiple:1 });
      s.addNotes(`All source records: ${refs.join(', ')}`);
    }
  }
  const qtext = (slide, text, x, y, w, h, size = 17, color = ink, bold = false) => {
    const body = fitted(text, w, h, size);
    slide.addText(body.text, { x, y, w, h, fontSize: body.size, color, bold, margin: 0, valign: 'top', lineSpacingMultiple:1 });
  };
  const number = value => value === null || value === undefined ? '未计算' : Number(value).toLocaleString('en-US', { maximumFractionDigits: 4 });
  for (const q of d.quantitative || []) {
    const a = q.artifact;
    if (q.method === 'operating_cash_scenario_v1') {
      s = page(q.label, false, true);
      const low = a.rows.reduce((best, row) => row.cash_end < best.cash_end ? row : best);
      qtext(s, `最低期末现金  ${number(low.cash_end)}`, 0.65, 1.45, 7.8, 0.6, 29, low.cash_end < 0 ? 'A13D35' : green, true);
      qtext(s, `${low.period_end}  |  补至现金底线需要 ${number(low.funding_needed_to_floor)}\n金额单位 ${a.currency} × ${number(a.amount_scale)}；未自动融资`, 0.65, 2.13, 7.8, 0.75, 15);
      s.addChart(pptx.ChartType.bar, [
        { name: '期末现金', labels: a.rows.map(r => r.period_end), values: a.rows.map(r => r.cash_end) },
        { name: '输入最低现金', labels: a.rows.map(r => r.period_end), values: a.rows.map(() => a.input_snapshot.minimum_cash.value) }
      ], { x: 0.65, y: 3.05, w: 7.55, h: 2.7, barDir: 'col', showLegend: true, legendPos: 'b', legendFontSize: 10,
           showValue: true, showCatName: false, catAxisLabelFontSize: 10, valAxisLabelFontSize: 10,
           chartColors: [green, 'B5C4C0'], dataLabelFormatCode: '0.00', valGridLine: { color: 'D9E2DF', size: 0.5 }, showBorder: false });
      s.addShape(pptx.ShapeType.rect, { x: 8.65, y: 1.48, w: 4.05, h: 4.9, fill: { color: 'E6EFEC' }, line: { color: 'E6EFEC' } });
      const p = a.input_snapshot.periods[0];
      qtext(s, '明确的业务与融资假设', 8.88, 1.7, 3.55, 0.55, 19, dark, true);
      qtext(s, `首期数量 ${number(p.volume)}\n单位价格 ${number(p.unit_price)}\nDSO ${number(p.dso)} 天\n资本开支 ${number(p.capex)}\n新增借款 ${number(p.drawdown)}\n还本 ${number(p.principal)} / 股利 ${number(p.dividends)}`, 8.88, 2.43, 3.55, 2.5, 17);
      qtext(s, '按期初债务计息；期末融资及还本。负现金后停止预测。逐期输入与证据见工作簿。', 8.88, 5.13, 3.55, 1, 12, '56646C');
      const contractText = (a.contracts || []).slice(0, 2).map(c => `${c.label} ${c.test_date}：${number(c.value)} / 阈值 ${number(c.threshold)}，${c.status}`).join('\n');
      qtext(s, contractText || '未输入合同条件；不推造行业门槛。', 0.65, 5.98, 7.65, 0.85, 11, '56646C');
      s.addNotes([q.id, ...q.assumptions, ...q.limitations, JSON.stringify(a.contracts), `Evidence: ${q.evidence.join(', ')}`].join('\n'));
      if (a.reverse) {
        const r = a.reverse;
        s = page(q.label + ' 逆向现金边界', false, true);
        qtext(s, r.definition, 0.65, 1.45, 12, 0.65, 20, dark, true);
        if (r.status === 'converged') {
          s.addShape(pptx.ShapeType.rect, { x: 0.65, y: 2.5, w: 5.75, h: 2.1, fill: { color: 'E6EFEC' }, line: { color: 'E6EFEC' } });
          qtext(s, `${r.driver} = ${number(r.driver_value)}`, 0.95, 2.8, 5.15, 0.75, 32, green, true);
          qtext(s, `第 ${r.period_index + 1} 期的驱动绝对值`, 0.95, 3.77, 5.15, 0.4, 15);
          qtext(s, `目标现金 ${number(r.target_cash)}\n目标日期 ${r.test_date}\n求解残差 ${Number(r.cash_residual).toPrecision(3)}`, 7.1, 2.65, 5.1, 1.8, 21);
          qtext(s, `搜索区间 ${r.bounds.map(number).join(' 至 ')}；端点现金残差 ${r.endpoint_cash_residuals.map(number).join(' / ')}`, 0.65, 5.05, 12, 0.6, 17);
        } else {
          qtext(s, r.status, 0.65, 2.7, 12, 0.85, 32, 'A13D35', true);
          qtext(s, r.reason || '未取得收敛边界', 0.65, 3.8, 12, 1.0, 21);
        }
        qtext(s, '条件边界不表示发生概率。改变假设、区间或目标后须重跑SciPy求根；根处完整现金路径随artifact保存。', 0.65, 6.0, 12, 0.72, 15, '56646C');
        s.addNotes([q.id, r.source || '', ...q.limitations, JSON.stringify(r.rows || [])].join('\n'));
      }
    } else if (q.method === 'single_entity_recovery_waterfall') {
      const totals = a.rows.filter(r => r.kind === 'claim_total');
      const claims = Object.fromEntries(a.input_snapshot.claims.map(c => [c.id, c]));
      for (let offset = 0; offset < totals.length; offset += 6) {
        s = page(q.label);
        qtext(s, `单一法人 ${a.input_snapshot.entity} | 金额单位 ${a.input_snapshot.currency} ${a.input_snapshot.unit}`, 0.65, 1.43, 12, 0.5, 17);
        const rows = [['债权', '原金额', '担保池回收', '一般回收', '总回收', '未偿', '回收比例'], ...totals.slice(offset, offset + 6).map(r =>
          [claims[r.claim_id].label, number(r.original_claim), number(r.secured), number(r.general), number(r.result), number(r.unpaid), r.recovery_rate === null ? '未定义' : `${number(Number(r.recovery_rate)*100)}%`])];
        s.addTable(rows, {x:0.65, y:2.0, w:12, colW:[3,1.5,1.5,1.5,1.5,1.5,1.5], rowH:0.4, fontSize:13, color:ink,
          border:{type:'solid',pt:0.5,color:'D9D9D9'}, fill:'FFFFFF', margin:0.1});
        const summary = a.rows.find(r => r.kind === 'reconciliation');
        qtext(s, summary.raw_input.replaceAll('gross=', '总价值 ').replaceAll('costs_paid=', '实付费用 ').replaceAll('debt_paid=', '债权分配 ').replaceAll('residual=', '余值 ')+`\n价值守恒残差 ${summary.result}`, 0.65, 5.06, 12, 0.68, 14, dark);
        qtext(s, `估值基础：${a.input_snapshot.value_basis}\n顺位依据：${a.input_snapshot.priority_basis}`, 0.65, 5.85, 12, 0.6, 12, '56646C');
        qtext(s, '未折现条件回收，不是违约概率或官方回收评级；逐项轨迹见报告与工作簿。', 0.65, 6.58, 12, 0.3, 11, '56646C');
        s.addNotes([q.id, ...q.assumptions, ...q.limitations, JSON.stringify(a.rows), `Evidence: ${q.evidence.join(', ')}`].join('\n'));
      }
      for (const body of paragraphs([...q.assumptions, ...q.limitations].join('\n\n'), 12, 4.9, 16)) {
        s = page(q.label + '：适用条件');
        qtext(s, body, 0.65, 1.6, 12, 4.9, 16);
      }
    } else if (q.method === 'pit_margin_persistence_v1') {
      s = page(q.label, false, true);
      const model = a.model;
      qtext(s, `成熟训练样本 ${model.training_n}  |  时间外留出样本 ${model.test_n}`, 0.65, 1.48, 12, 0.7, 28, dark, true);
      qtext(s, `训练截止 ${a.input_snapshot.training_cutoff}\n首次公告作为历史预测起点；后续修订只影响当前同业版本。`, 0.65, 2.27, 12, 0.85, 15);
      if (model.test_mae !== undefined && model.test_mae !== null) {
        s.addChart(pptx.ChartType.bar, [{ name: '留出MAE 百分点', labels: ['单变量OLS', 'Last-value基准'], values: [model.test_mae*100, model.baseline_mae*100] }],
          { x: 0.65, y: 3.38, w: 6.7, h: 2.9, barDir: 'bar', showValue: true, showLegend: false,
            chartColors: [green], valAxisMinVal:0, dataLabelFormatCode:'0.00', catAxisLabelFontSize: 13, valAxisLabelFontSize: 10, valGridLine: { color: 'D9E2DF', size: 0.5 } });
        qtext(s, `模型MAE ${number(model.test_mae*100)} 个百分点\n基准MAE ${number(model.baseline_mae*100)} 个百分点`, 7.8, 3.65, 4.8, 1.25, 22, green, true);
      } else {
        s.addShape(pptx.ShapeType.rect, { x: 0.65, y: 3.5, w: 6.7, h: 2.25, fill: { color: 'E6EFEC' }, line: { color: 'E6EFEC' } });
        qtext(s, '没有可报告的成熟留出误差', 0.95, 3.9, 6.1, 1, 26, dark, true);
      }
      qtext(s, `未成熟结果 ${a.pending_outcomes.length} 条\n其他排除 ${a.excluded_pairs.length} 条\n状态 ${model.validation_status || model.status}`, 7.8, 5.1, 4.8, 1, 15);
      qtext(s, '误差仅描述此样本；不是训练准确率、PD、投资收益或因果证据。真实用途还需行业周期和样本外代表性。', 0.65, 6.45, 12, 0.38, 12, '56646C');
      s.addNotes([q.id, ...q.assumptions, ...q.limitations, JSON.stringify(a.training_pairs), `Evidence: ${q.evidence.join(', ')}`].join('\n'));
    }
  }
  for (let i = 0; i < d.requests.length; i += 3) {
    s = page('下一步核查');
    d.requests.slice(i, i + 3).forEach((r, j) => {
      s.addText(String(i + j + 1).padStart(2, '0'), { x: 0.65, y: 1.65 + j * 1.5, w: 1, h: 0.4, fontSize: 20, color: green, bold: true, margin: 0 });
      const request = fitted(r.request, 10.6, 0.85, 18);
      s.addText(request.text, { x: 1.8, y: 1.65 + j * 1.5, w: 10.6, h: 0.85, fontSize: request.size, color: ink, margin: 0, valign:'top',lineSpacingMultiple:1 });
      s.addText(r.owner_role, { x: 1.8, y: 2.52 + j * 1.5, w: 10.6, h: 0.3, fontSize: 12, color: '586874', margin: 0 });
      s.addNotes(`${r.id}: ${r.reason}\nClose when: ${r.close_when}`);
    });
  }
  await pptx.writeFile({ fileName: output });
  console.log(JSON.stringify({node:process.version, pptxgenjs:pptx.version}));
}
main().catch(err => { console.error(err.message); process.exitCode = 1; });
