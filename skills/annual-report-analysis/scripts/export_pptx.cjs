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
    const tokens = [];
    for (const {segment} of segmenter.segment(paragraph)) {
      if (tokens.length && (/^[，。；：！？、）】”’]+$/.test(segment) ||
          (/^\d/.test(segment) && /^[+−-]$/.test(tokens.at(-1))))) tokens[tokens.length - 1] += segment;
      else tokens.push(segment);
    }
    for (const tokenPart of tokens) {
      const chars = Array.from(tokenPart);
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
    const wrapped = lines(text, width, size), capacity = Math.max(1, Math.floor(height * 72 / (size * 1.3)));
    const result = [];
    for (let start = 0; start < wrapped.length;) {
      while (start < wrapped.length && !wrapped[start].trim()) start++;
      if (start === wrapped.length) break;
      let end = Math.min(start + capacity, wrapped.length);
      if (end < wrapped.length) {
        for (let boundary = end; boundary > start; boundary--) {
          if (!wrapped[boundary].trim()) {end = boundary; break;}
        }
        if (wrapped[end].trim() && (end + 1 === wrapped.length || !wrapped[end + 1].trim()) && end - start > 1) end--;
      }
      result.push(wrapped.slice(start, end).join('\n').trimEnd());
      start = end;
    }
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
  const evidence = Object.fromEntries(d.evidence.map(e => [e.id, e]));
  const sourcesById = Object.fromEntries(d.sources.map(source => [source.id, source]));
  const usedEvidence = new Set();
  const sourceRefs = refs => [...new Set(refs.flatMap(ref => d.figures[ref] ? d.figures[ref].evidence : [ref]))];
  const sourceNotes = refs => sourceRefs(refs).map(ref => {
    usedEvidence.add(ref);
    const e = evidence[ref], source = sourcesById[e.source];
    return `[${ref}] ${source.title} | ${e.locator}\n${source.url}`;
  }).join('\n');
  const findings = Object.fromEntries(d.findings.map(f => [f.id, f]));
  let s = page(d.mandate.title, true);
  const purpose = fitted(d.mandate.purpose, 11.8, 1.25, 24);
  s.addText(purpose.text, { x: 0.7, y: 1.8, w: 11.8, h: 1.25, fontSize: purpose.size, color: 'FFFFFF', margin: 0, valign:'top', lineSpacingMultiple:1 });
  s.addText(`会计基础 ${d.mandate.accounting_basis}\n范围 ${d.mandate.scope}\n信息截止 ${d.mandate.cutoff}`, { x: 0.7, y: 3.5, w: 11.8, h: 1.5, fontSize: 19, color: 'C6DEDA', margin: 0 });
  s.addNotes(d.mandate.limitations.join('\n'));
  const unknownDates = d.sources.filter(source => source.published === null).map(source => source.id);
  if (unknownDates.length) s.addText(`来源 ${unknownDates.join(', ')} 公布日期未核验。不得将当前内容分析称为历史时点可用性验证。`,
    {x:0.7,y:5.35,w:11.8,h:0.95,fontSize:16,color:'FFFFFF',margin:0,fit:'shrink'});
  if (d.presentation?.length) {
    for (const [index, item] of d.presentation.entries()) {
      const selected = item.findings.map(id => findings[id]);
      const figures = item.figures.map(id => d.figures[id]);
      const ids = [...new Set([...item.findings, ...item.figures, ...item.figure_refs])];
      const refs = sourceRefs([...item.figures, ...item.figure_refs,
        ...selected.flatMap(f => [...f.evidence, ...f.counterevidence, ...f.figure_refs])]);
      const sourceIds = [...new Set(refs.map(ref => evidence[ref].source))];
      const trace = `底稿 ${item.findings.join(' / ')}；来源 ${sourceIds.join(' / ')}\n原文定位、URL及完整引用见本页备注；完整方法和明细见同名底稿及 Word/Excel。`;
      const width = figures.length ? 7.9 : 12;
      const status = selected.map(f => `[${f.id}] ${f.status}`).join(' / ');
      const bodies = paragraphs(item.body, width, 4.15, 18);
      const cards = paragraphs(figures.map(f => `${f.label}\n${f.display}`).join('\n\n'), 3.55, 4.15, 16);
      const count = Math.max(1, bodies.length, cards.length);
      for (let i = 0; i < count; i++) {
        s = page(item.title + (count > 1 ? ` ${i + 1}/${count}` : ''), false, true);
        s.addText(bodies[i] || '', {x:0.65,y:1.55,w:width,h:4.15,fontSize:18,color:ink,margin:0,valign:'top',lineSpacingMultiple:1});
        if (cards[i]) {
          s.addShape(pptx.ShapeType.rect, {x:8.8,y:1.45,w:3.9,h:4.45,fill:{color:'E6EFEC'},line:{color:'E6EFEC'}});
          s.addText(cards[i], {x:8.98,y:1.55,w:3.55,h:4.15,fontSize:16,color:green,margin:0,valign:'top',lineSpacingMultiple:1});
        }
        s.addText(lines(status, 12, 11).join('\n'), {x:0.65,y:5.82,w:12,h:0.4,fontSize:11,color:dark,margin:0,valign:'top',lineSpacingMultiple:1});
        s.addText(lines(trace, 12, 10).join('\n'), {x:0.65,y:6.25,w:12,h:0.8,fontSize:10,color:'586874',margin:0,valign:'top',lineSpacingMultiple:1});
        s.addNotes([`底稿 ${ids.join(', ')}`, sourceNotes(refs),
          ...(index === 0 ? [...d.mandate.methods, ...d.mandate.limitations] : [])].join('\n'));
      }
    }
    await pptx.writeFile({ fileName: output });
    console.log(JSON.stringify({node:process.version, pptxgenjs:pptx.version}));
    return;
  }
  if (d.mandate.methods.length) {
    for (const body of paragraphs(d.mandate.methods.join('\n\n'), 12, 4.9, 16)) {
      s = page('采用方法与适用范围');
      s.addText(body, {x:0.65,y:1.6,w:12,h:4.9,fontSize:16,color:ink,margin:0,valign:'top',lineSpacingMultiple:1});
    }
  }
  if (d.mandate.limitations.length) {
    for (const body of paragraphs(d.mandate.limitations.join('\n\n'), 12, 4.9, 16)) {
      s = page('分析范围与限制');
      s.addText(body, {x:0.65,y:1.6,w:12,h:4.9,fontSize:16,color:ink,margin:0,valign:'top',lineSpacingMultiple:1});
    }
  }
  const counterText = ref => d.figures[ref]
    ? `${d.figures[ref].label}：${d.figures[ref].display}` : evidence[ref].observation;
  for (const section of d.sections) {
    const selected = section.findings.map(id => findings[id]);
    const allFigures = section.figures.map(id => d.figures[id]);
    if (!selected.length && !allFigures.length) continue;
    const shown = new Set();
    const pages = selected.flatMap(f => {
      const figures = allFigures.filter(v => (f.figure_refs || []).includes(v.id));
      figures.forEach(v => shown.add(v.id));
      const width = figures.length ? 7.65 : 12;
      const text = [f.conclusion, `解释与依据\n${f.mechanism}`,
        ...(f.alternatives.length ? [`其他解释\n${f.alternatives.join('\n')}`] : []),
        ...(f.counterevidence.length ? [`反证\n${f.counterevidence.map(counterText).join('\n')}`] : []),
        `判断改变条件\n${f.changes_if}`].join('\n\n');
      const body = fitted(text, width, 3.35, 18);
      const chunks = body.size >= 16 ? [{body:body.text,size:body.size}]
        : paragraphs(text, width, 3.35, 18).map(body => ({body,size:18}));
      return Array.from({length: Math.max(chunks.length, Math.ceil(figures.length / 4))}, (_, index) =>
        ({f, width, ...(chunks[index] || {body:'', size:18}), figures:figures.slice(index * 4, index * 4 + 4)}));
    });
    const independent = allFigures.filter(v => !shown.has(v.id));
    for (let i = 0; i < independent.length; i += 6) pages.push({figures:independent.slice(i, i + 6)});
    for (let index = 0; index < pages.length; index++) {
      const chunk = pages[index];
      const figures = chunk.figures, width = chunk.width;
      s = page(section.title + (chunk.f ? '' : '：章节指标') + (pages.length > 1 ? ` ${index + 1}` : ''));
      const f = chunk.f;
      if (f) {
        const heading = fitted(`[${f.status}] ${f.title}`, width, 1.1, 22);
        s.addText(heading.text, { x: 0.65, y: 1.58, w: width, h: 1.1, fontSize: heading.size, color: dark, bold: true, margin: 0, valign:'top', lineSpacingMultiple:1 });
        s.addText(chunk.body, { x: 0.65, y: 2.87, w: width, h: 3.35, fontSize: chunk.size, color: ink, margin: 0, valign:'top', lineSpacingMultiple:1 });
        s.addNotes([f.id, `Status: ${f.status}`, f.question, f.mechanism, ...f.alternatives, `Evidence: ${f.evidence.join(', ')}`, `Counterevidence: ${f.counterevidence.join(', ')}`].join('\n'));
      }
      figures.forEach((v, i) => {
        const scale = f ? Math.min(1, 4 / figures.length) : 1;
        const x = f ? 8.7 : 0.65 + i % 2 * 6.1, y = f ? 1.65 + i * 1.18 * scale : 1.65 + Math.floor(i / 2) * 1.7;
        const w = f ? 4 : 5.9;
        s.addShape(pptx.ShapeType.rect, { x, y, w, h: 1.04 * scale, fill: { color: 'E6EFEC' }, line: { color: 'E6EFEC' } });
        const label = fitted(v.label, w - 0.4, 0.3 * scale, 12), value = fitted(v.display, w - 0.4, 0.43 * scale, 18);
        s.addText(label.text, { x: x + 0.2, y: y + 0.09 * scale, w: w - 0.4, h: 0.3 * scale, fontSize: label.size, color: dark, margin: 0, valign:'top', lineSpacingMultiple:1 });
        s.addText(value.text, { x: x + 0.2, y: y + 0.49 * scale, w: w - 0.4, h: 0.43 * scale, fontSize: value.size, bold: true, color: green, margin: 0, valign:'top', lineSpacingMultiple:1 });
      });
      const refs = sourceRefs([...figures.map(v => v.id), ...(f ? [...f.evidence, ...f.counterevidence, ...f.figure_refs] : [])]);
      const sources = fitted(`来源记录 ${refs.slice(0,3).join(' / ')}${refs.length>3 ? ' 等' : ''}；完整原文与位置见本演示文稿来源附页及备注`, 12, 0.3, 9);
      s.addText(sources.text, { x: 0.65, y: 6.57, w: 12, h: 0.3, fontSize: sources.size, color: '586874', margin: 0, valign:'top', lineSpacingMultiple:1 });
      s.addNotes(sourceNotes(refs));
    }
  }
  const qtext = (slide, text, x, y, w, h, size = 17, color = ink, bold = false) => {
    const body = fitted(text, w, h, size);
    slide.addText(body.text, { x, y, w, h, fontSize: body.size, color, bold, margin: 0, valign: 'top', lineSpacingMultiple:1 });
  };
  const number = value => value === null || value === undefined ? '未计算' : Number(value).toLocaleString('en-US', { maximumFractionDigits: 4 });
  for (const q of d.quantitative || []) {
    const a = q.artifact;
    const originalSources = sourceNotes([...q.evidence, ...q.input_refs, ...q.figures.map(f => f.id)]);
    if (q.method === 'operating_cash_scenario_v1') throw new Error('Historical operating_cash_scenario_v1 requires its frozen exporter or documented v2 cost decomposition');
    if (q.method === 'operating_cash_scenario_v2') {
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
      qtext(s, a.contracts?.length ? '全部输入约束及真实状态见后续条件页。' : '未输入合同条件；不推造行业门槛。', 0.65, 5.98, 7.65, 0.85, 11, '56646C');
      s.addNotes([q.id, ...q.assumptions, ...q.limitations, JSON.stringify(a.contracts), originalSources].join('\n'));
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
        s.addNotes([q.id, r.source || '', ...q.limitations, JSON.stringify(r.rows || []), originalSources].join('\n'));
        if (r.rows?.length) {
          const boundary = r.rows.map(row => `${row.period_end} | ${row.status}\n收入 ${number(row.revenue)}；EBITDA ${number(row.ebitda)}；EBIT ${number(row.ebit)}\n净利润 ${number(row.net_income)}；CFO ${number(row.cfo)}\n期末现金 ${number(row.cash_end)}；期末债务 ${number(row.debt_end)}\n现金余量 ${number(row.cash_headroom)}；补至现金底线 ${number(row.funding_needed_to_floor)}\n债务/EBITDA ${number(row.debt_to_ebitda)}；利息覆盖倍数 ${number(row.interest_coverage)}`).join('\n\n');
          for (const body of paragraphs(boundary, 12, 4.75, 17)) {
            s = page(q.label + '：逆根盈利与杠杆');
            qtext(s, `金额单位 ${a.currency} × ${number(a.amount_scale)}；已运行边界快照，修改输入后须重跑。`, 0.65, 1.45, 12, 0.45, 13, '56646C');
            qtext(s, body, 0.65, 2.0, 12, 4.75, 17);
            s.addNotes([q.id, r.source || '', originalSources].join('\n'));
          }
        }
      }
      for (const [title, result] of [['全部输入约束', a], ['逆根处全部输入约束', a.reverse || {}]]) {
        const conditions = (result.contracts || []).map(c => `${c.label} | ${c.test_date}\n${c.definition}\n${c.metric} ${c.relation} ${number(c.threshold)}；计算值 ${number(c.value)}；${c.status}\n${c.reason || ''}\n来源 ${c.source}`).join('\n\n');
        for (const body of paragraphs(conditions, 12, 4.9, 16)) {
          s = page(q.label + '：' + title);
          qtext(s, body, 0.65, 1.6, 12, 4.9, 16);
          s.addNotes([q.id, originalSources].join('\n'));
        }
      }
      for (const [title, result] of [['实际累计与全期假设桥', a], ['逆根处实际累计与全期假设桥', a.reverse || {}]]) {
        if (result.actual_bridge?.length) {
          const bridge = [`path_basis: ${a.path_basis || '未提供'}；实际桥仅比较累计实际与全期输入。remaining 不重建剩余期间，也不重设现金路径；same_scope 是输入声明，未知值不替换为零。`,
            ...result.actual_bridge.map(row => `${row.period_start} 至 ${row.period_end} | ${row.metric}\n全期 ${number(row.period_total)}；累计 ${number(row.actual)}；remaining ${number(row.remaining)}\n${row.status}；same_scope ${row.same_scope}；conflict ${row.conflict}\n截至 ${row.through_date || '未提供'}；公布 ${row.available_at || '未提供'}\n来源 ${row.source || '未提供'}`)].join('\n\n');
          for (const body of paragraphs(bridge, 12, 4.9, 16)) {
            s = page(q.label + '：' + title);
            qtext(s, body, 0.65, 1.6, 12, 4.9, 16);
            s.addNotes([q.id, originalSources].join('\n'));
          }
        }
      }
      for (const body of paragraphs(q.limitations.join('\n\n'), 12, 4.9, 16)) {
        s = page(q.label + '：适用限制');
        qtext(s, body, 0.65, 1.6, 12, 4.9, 16);
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
        s.addNotes([q.id, ...q.assumptions, ...q.limitations, JSON.stringify(a.rows), originalSources].join('\n'));
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
      s.addNotes([q.id, ...q.assumptions, ...q.limitations, JSON.stringify(a.training_pairs), originalSources].join('\n'));
    } else {
      const value = item => item === null ? 'null' : typeof item === 'object' ? JSON.stringify(item) : String(item);
      const rows = a.rows || [];
      const figures = q.figures.map(f => d.figures[f.id]);
      const trace = `${q.id}\n${q.method}\n截至 ${q.as_of}\n输入 ${q.input_refs.join(', ')}\n${originalSources}\n指标 ${figures.map(f => f.id).join(', ')}`;
      const summaries = figures.length ? [figures.map(f => `${f.label}：${f.display}`).join('\n\n')]
        : rows.map(row => Object.entries(row).map(([key, item]) => `${key}：${value(item)}`).join('\n\n'));
      for (let index = 0; index < summaries.length; index++) {
        const text = summaries[index];
        for (const body of paragraphs(text, 12, 4.5, 16)) {
          s = page(`${q.label}：${figures.length ? '指标摘要' : '结果行 '+index}`);
          qtext(s, body, 0.65, 1.6, 12, 4.5, 16);
          qtext(s, `证据 ${q.evidence.slice(0,3).join(', ')}${q.evidence.length > 3 ? ' 等' : ''}；完整出处见来源附页及备注。已运行快照，全量结果与公式见Excel/JSON。`, 0.65, 6.35, 12, 0.55, 11, '56646C');
          s.addNotes(trace);
        }
      }
      const details = [`方法 ${q.method}；截至 ${q.as_of}`, '已运行专门结果快照；本次导出未重新计算或校验。输入或方法改变后须重跑专门脚本并重新导出。',
        ...(!rows.length ? ['未提供 artifact.rows 结果行。'] : []), `证据记录 ${q.evidence.join(', ')}；完整输入记录见备注。`,
        ...q.assumptions.map(text => `假设：${text}`), ...q.limitations.map(text => `限制：${text}`)];
      for (const body of paragraphs(details.join('\n\n'), 12, 4.9, 16)) {
        s = page(q.label + '：方法、假设与限制');
        qtext(s, body, 0.65, 1.6, 12, 4.9, 16);
        s.addNotes(trace);
      }
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
  const sourcePages = [];
  for (const source of d.sources) {
    const records = d.evidence.filter(e => e.source === source.id && usedEvidence.has(e.id));
    if (!records.length) continue;
    const text = [`[${source.id}] ${source.title}`, source.url,
      ...records.map(e => `[${e.id}] ${e.locator}`)].join('\n');
    for (const body of paragraphs(text, 12, 4.9, 16)) {
      const previous = sourcePages.at(-1), refs = records.map(e => e.id);
      const combined = previous ? `${previous.body}\n\n${body}` : body;
      if (previous && lines(combined, 12, 16).length * 16 * 1.3 <= 4.9 * 72) {
        previous.body = combined;
        previous.refs.push(...refs);
      } else sourcePages.push({body, refs});
    }
  }
  for (const sourcePage of sourcePages) {
    s = page('原文来源与定位');
    qtext(s, sourcePage.body, 0.65, 1.6, 12, 4.9, 16);
    s.addNotes(sourceNotes(sourcePage.refs));
  }
  await pptx.writeFile({ fileName: output });
  console.log(JSON.stringify({node:process.version, pptxgenjs:pptx.version}));
}
main().catch(err => { console.error(err.message); process.exitCode = 1; });
