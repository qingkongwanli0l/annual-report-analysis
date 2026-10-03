const fs = require('node:fs');
const pptxgen = require('pptxgenjs');

async function main() {
  const [input, output] = process.argv.slice(2);
  const d = JSON.parse(fs.readFileSync(input, 'utf8'));
  const p = new pptxgen();
  p.layout = 'LAYOUT_WIDE';
  p.author = 'annual-report-analysis';
  p.title = d.mandate.title + '｜研究汇报';
  p.subject = d.mandate.purpose;
  p.lang = 'zh-CN';
  p.theme = { headFontFace: 'Microsoft YaHei', bodyFontFace: 'Microsoft YaHei', lang: 'zh-CN' };
  const dark = '213B45', green = '237F72', red = 'A34638', paper = 'F5F7F6';
  const q = id => d.quantitative.find(x => x.id === id).artifact.rows;
  const value = id => d.figures[id].display;
  const amount = id => Number(d.figures[id].value) * Number(d.figures[id].context.scale) / 1e8;
  const text = (s, body, x, y, w, h, size = 19, color = dark, bold = false) =>
    s.addText(body, { x, y, w, h, fontSize: size, color, bold, margin: 0, valign: 'top', breakLine: false });
  let n = 0;
  function page(title, refs, darkPage = false) {
    const s = p.addSlide(); s.background = { color: darkPage ? dark : paper };
    text(s, title, 0.6, 0.42, 12.1, 0.65, 30, darkPage ? 'FFFFFF' : dark, true);
    text(s, `科顺股份及科顺转债｜信息截止 ${d.mandate.cutoff}｜条件性公开研究｜${++n}`, 0.6, 7.02, 12.1, 0.22, 9, darkPage ? 'BCD2CE' : '5C6C71');
    text(s, `底稿记录：${refs.join(' / ')}；原页、公式及完整限制见报告和Excel。`, 0.6, 6.52, 12.1, 0.35, 10, darkPage ? 'BCD2CE' : '5C6C71');
    s.addNotes(refs.map(id => JSON.stringify(d.findings.find(f => f.id === id) || d.evidence.find(e => e.id === id) || d.figures[id] || {id})).join('\n'));
    return s;
  }
  function card(s, x, y, w, heading, main, detail, color = green) {
    s.addShape(p.ShapeType.rect, { x, y, w, h: 1.85, fill: { color: 'E6EFEC' }, line: { color: 'E6EFEC' } });
    text(s, heading, x + 0.22, y + 0.16, w - 0.44, 0.35, 14);
    text(s, main, x + 0.22, y + 0.62, w - 0.44, 0.58, 25, color, true);
    text(s, detail, x + 0.22, y + 1.26, w - 0.44, 0.43, 12);
  }
  function table(s, rows, y, widths, size = 15) {
    s.addTable(rows, { x: 0.6, y, w: 12.1, colW: widths, fontSize: size, color: dark, margin: 0.12,
      rowH: 0.48, border: { type: 'solid', pt: 0.5, color: 'D5DEDA' }, fill: 'FFFFFF', bold: false });
  }
  const chain = q('ks_r_rating_chain');
  let s = page('科顺股份与科顺转债｜研究建议及条件', ['ks_r_recommendation','ks_r_liquidity'], true);
  text(s, `${chain[0].issuer} / ${chain[0].outlook}展望`, 0.7, 1.55, 11.7, 1.05, 49, 'FFFFFF', true);
  text(s, '主体与普通无担保直接债项的基准研究建议', 0.7, 2.85, 11.7, 0.5, 23, 'D4E8E1');
  text(s, '以付款日前可调度资金及用途安排足以覆盖、未证实到期不支付为条件。母公司未来资金与持续承诺后果尚待核实，不能作为无条件正式评级发布。', 0.7, 3.65, 11.7, 1.28, 22, 'FFFFFF');
  text(s, '采用境内相对信用尺度及联合公开方法的明示研究适配；不是联合资信评级行动。完整研究及底稿另附，本汇报只提炼影响决定的事项。', 0.7, 5.35, 11.7, 0.7, 15, 'D4E8E1');

  s = page('建议来自因素、调整、支持与债项的连续判断', ['ks_r_recommendation','ks_r_support_assessment','ks_r_adjustments']);
  card(s, 0.6, 1.45, 3.8, '经营风险', chain[0].business, `自身竞争力 ${value('ks_r_competitive_score')}`);
  card(s, 4.65, 1.45, 3.8, '财务风险', chain[0].finance, `财务研究分 ${value('ks_r_financial_score')}`);
  card(s, 8.7, 1.45, 4.0, '指示结果选择', chain[0].chosen, `公开单元格 ${chain[0].cell}`);
  text(s, '取较弱端：最新负EBITDA、母公司负经营现金、末季回款依赖与用途限制。基础因素已反映的事项不重复扣档；未计入未经证实的支持增益。', 0.6, 3.75, 12.1, 1.0, 22);
  text(s, '方法局限会影响决定：财务仅以可比两年30/70合成，是研究适配；本企业并非只存续两年。三年重述细项、定性区间与计算顺序都需敏感性核验。', 0.6, 5.1, 12.1, 0.95, 18, red);

  s = page('收入收缩与毛利修复，并未转成盈利恢复', ['ks_a_e_is','ks_b_market_position','ks_a_find_earnings']);
  card(s, 0.6, 1.5, 3.8, '2025收入', value('ks_a_revenue_2025'), `同比 ${value('ks_a_revenue_growth_2025')}`);
  card(s, 4.65, 1.5, 3.8, '2025毛利率', value('ks_a_grossmargin_2025'), `2024 ${value('ks_a_grossmargin_2024')}`);
  card(s, 8.7, 1.5, 4.0, '2025 EBITDA', value('ks_a_ebitda_2025'), '保留信用及资产减值影响', red);
  text(s, '渠道、产品及成本变化要连接销量、售价和回款。收入类别或毛利率的变化，不能在缺少数量与价格桥时直接命名为有机增长或提价。', 0.6, 3.82, 12.1, 1.0, 22);
  text(s, '反证保留：季度收入及利润初步改善、无保留审计意见；它们不能单独排除旧应收损失、资金限制或短期付款风险。', 0.6, 5.12, 12.1, 0.85, 19);

  s = page('同行比较显示差异，也保留集团业务边界', ['ks_r_peer_finding']);
  const peer = q('ks_r_peers');
  table(s, [['2025集团口径','收入同比 %','负债/资产 %','净周期 天','EBITDA/费用化利息 倍'],
    ...peer.map(r => [r.company.replace('股份有限公司',''), ...['revenue_growth','liabilities_assets','noc360','ebitda_expinterest'].map(k => Number(r[k]).toFixed(2))])], 1.6, [4.1,1.8,1.9,1.8,2.5]);
  text(s, '科顺的利润、杠杆及账面周转压力不能只用行业下行解释。北新含重要石膏板/涂料业务，两家同行并购贡献未全年化重构；样本不构成行业均值或定级标尺。', 0.6, 4.18, 12.1, 1.08, 21);
  text(s, '同行简式融资口径和费用化利息倍数仅供比较，不能替代本案评级方法的全部债务与全部利息。', 0.6, 5.62, 12.1, 0.55, 17, red);

  s = page('现金质量取决于形成过程与季节性', ['ks_a_find_cfo','ks_a_find_q1','ks_a_e_indirect']);
  card(s, 0.6, 1.5, 3.8, '全年经营净现金', value('ks_a_cfo_2025'), '正现金不等于正EBITDA');
  card(s, 4.65, 1.5, 3.8, '扣现金资本开支后', value('ks_a_fcf_2025'), '尚未扣并购、分配及其他投资');
  card(s, 8.7, 1.5, 4.0, '第四季CFO', value('ks_a_quarter4_cfo'), '不能掩盖前三季净流出');
  text(s, '非现金减值加回不会创造经营盈利。应收净额下降还可能来自准备、核销、抵债及范围变化，未完成滚动桥前不能直接视为客户多付现金。', 0.6, 3.85, 12.1, 1.0, 22);
  text(s, `未经审计的一季度CFO仍为 ${value('ks_a_q1_cfo')}。年度、季度及重述比较范围分开；不以一季乘四取代全年预测。`, 0.6, 5.18, 12.1, 0.85, 19);

  s = page('季度现金低点比年末余额更先约束支付', ['ks_r_liquidity']);
  const cash = ['base','worse','better'].map(id => ({ name: {base:'基准',worse:'恶化',better:'改善'}[id], labels: ['2026-06','2026-09','2026-12'],
    values: q('ks_r_cash_'+id).slice(0,3).map(r => Number(r.cash_end_before_additional_purpose_reserve)/1e8) }));
  s.addChart(p.ChartType.line, cash, { x: 0.6, y: 1.52, w: 7.9, h: 4.35, showLegend: false, chartColors: [green,red,'8A9970'],
    showValue: false, showDataTable: true, showDataTableKeys: true, dataTableFontSize: 11, dataTableFormatCode: '0.00', catAxisLabelFontSize: 13, valAxisLabelFontSize: 12, valAxisTitle: '亿元人民币', showValAxisTitle: true,
    showMarker: true, showBorder: false, valGridLine: { color: 'DCE4E0', width: 0.5 } });
  text(s, `基准最低\n${value('ks_r_base_cash_min')}\n\n既定客户收款再降\n${value('ks_r_base_receipt_boundary')}\n即触及季度末零现金`, 8.95, 1.75, 3.72, 3.15, 22);
  text(s, '以3月末合并实际现金为起点；之后均为无新增融资的条件路径。负数后的行只表示未融资缺口延续，后期回款不证明此前已安全支付。', 0.6, 6.01, 12.1, 0.42, 13, red);

  s = page('募集资金用途限制，须与外部还债分开', ['ks_d_n_funds','ks_r_liquidity']);
  const purposeReserve = (Number(q('ks_r_cash_base')[3].minimum_cash) - Number(q('ks_r_cash_base')[3].reserve_650m_minimum)) / 1e8;
  card(s, 0.6, 1.55, 3.8, '基准：不新增用途预留', value('ks_r_base_cash_min'), '集团季度最低余额');
  card(s, 4.65, 1.55, 3.8, `基准：另预留${purposeReserve.toFixed(1)}亿元`, value('ks_r_base_reserve650'), '条件用途敏感性；非实际占用', red);
  card(s, 8.7, 1.55, 4.0, '恶化：不新增用途预留', value('ks_r_worse_cash_min'), '尚未落实补缺融资', red);
  text(s, '恢复专户或用途约束是内部现金调度，不是新增一笔债券本金。实际补流占用和项目付款时点未知；已受限余额与未来恢复额必须先核对重合。', 0.6, 3.9, 12.1, 0.97, 22);
  text(s, '现金模型中的银行本金、非转债利息与季度分配是研究预算，尚非已核实的逐笔合同到期表。季度末为正也不能证明月内足够。', 0.6, 5.16, 12.1, 0.8, 19, red);

  s = page('偿债主体是发行人，不能直接动用全部集团余额', ['ks_r_parent_risk','ks_d_e_issue_coupon','ks_d_e_maturity_call']);
  card(s, 0.6, 1.48, 5.9, '母公司2025末：现金减短期账面代理', value('ks_r_parent_screen'), '未扣全体经营、票据、股利及用途需求');
  card(s, 6.8, 1.48, 5.9, '同日现金减固定本金未来到期价', value('ks_r_parent_maturity_gap'), '静态比较，不是本年已到期缺口', red);
  table(s, [['固定一季末面值情景','2026支付','2027支付','2028支付','2029支付'],
    ['合同现金需求（亿元）',...['2026','2027','2028','2029'].map(y => amount('ks_d_g_cash_'+y).toFixed(4))]], 3.74, [3.7,2.1,2.1,2.1,2.1], 15);
  text(s, '到期价已含末期利息，不再加末息。未来转股尚未发生，不提前免除本金。母公司上划须核对子公司自身资金、可分配金额、法律决策及到账路径。', 0.6, 5.25, 12.1, 0.9, 19);

  s = page('会计与合同疑点保留原值，不倒挤为零', ['ks_a_e_ar','ks_a_e_fixed','ks_d_n_covenant','ks_r_bond_bucket_finding']);
  const unresolved = d.results.reconciliations.filter(r => r.status === 'unexplained_difference');
  table(s, [['需解释的原表勾稽','精确残差：人民币元'], ...unresolved.map(r => [d.reconciliations.find(x => x.id === r.id).label, Number(r.residual).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})])], 1.55, [8.6,3.5]);
  text(s, '两项滚动差异均回看原页后保留；另有债券期限表与固定本金合同时间轴的差额。均需解释，不能擅改原符号或直接推断整体报表失实。', 0.6, 3.61, 12.1, 1.0, 21);
  text(s, `债券账面余额/净资产 ${value('ks_d_c_book_ratio')} 与持续承诺存在待解释关系。发行条件、持续承诺、会议触发和实际加速后果分别核验，不能直接认定已违约或已获豁免。`, 0.6, 4.94, 12.1, 1.05, 20, red);

  s = page('跟踪应改变决定，而不只是更新比率', ['ks_r_followup','ks_r_rating_chain'], true);
  table(s, [['重算后成立的条件','条件建议','行动边界'],
    ...chain.slice(2,5).map(r => [r.business+'/'+r.finance,r.issuer,'其他调整、支持及付款条件不变']),
    ['证实近期无法按约付款','退出常态矩阵','确认合同事件并立即重新定级']], 1.6, [4.2,2.2,5.7], 17);
  text(s, '先取得实际银行现金与用途对账、母公司付款日、持续承诺后果和可执行融资；再更新回款、亏损、订单及完整重述。改善必须由完整期间和后续证据支持，不能仅靠区间选高分升级。', 0.6, 4.65, 12.1, 1.22, 21, 'FFFFFF');
  await p.writeFile({ fileName: output });
  console.log(JSON.stringify({ slides: n, input, output }));
}
main();
