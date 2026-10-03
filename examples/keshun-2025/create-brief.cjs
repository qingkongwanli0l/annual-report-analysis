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
  text(s, '以付款日前资金及用途安排足以覆盖为条件。历史毛现金流的范围调整、母公司未来资金及持续承诺后果尚待核实；模型数值尚不能证明实际付款覆盖。', 0.7, 3.65, 11.7, 1.28, 22, 'FFFFFF');
  text(s, '采用境内相对信用尺度及联合公开方法的明示研究适配；不是联合资信评级行动。完整研究及底稿另附，本汇报只提炼影响决定的事项。', 0.7, 5.35, 11.7, 0.7, 15, 'D4E8E1');

  s = page('建议来自因素、调整、支持与债项的连续判断', ['ks_r_recommendation','ks_r_support_assessment','ks_r_adjustments']);
  card(s, 0.6, 1.45, 3.8, '经营风险', chain[0].business, `自身竞争力 ${value('ks_r_competitive_score')}`);
  card(s, 4.65, 1.45, 3.8, '财务风险', chain[0].finance, `财务研究分 ${value('ks_r_financial_score')}`);
  card(s, 8.7, 1.45, 4.0, '指示结果选择', chain[0].chosen, `公开单元格 ${chain[0].cell}`);
  text(s, '取较弱端：最新负EBITDA、母公司负经营现金、末季回款依赖与用途限制。基础因素已反映的事项不重复扣档；未计入未经证实的支持增益。', 0.6, 3.75, 12.1, 1.0, 22);
  text(s, `同定义年度指标先30/70加权、再分档；缺完整三年重述，仍属研究适配。固定现有定性分值的量化档内范围为[${Number(q('ks_r_finance')[10].lower).toFixed(5)}, ${Number(q('ks_r_finance')[10].upper_supremum).toFixed(5)})，跨F5/F4，不能把代表值当唯一结果。`, 0.6, 5.1, 12.1, 0.95, 18, red);

  s = page('收入收缩与毛利修复，并未转成盈利恢复', ['ks_a_e_is','ks_b_market_position','ks_a_find_earnings','ks_a_find_tax']);
  card(s, 0.6, 1.5, 3.8, '2025收入', value('ks_a_revenue_2025'), `同比 ${value('ks_a_revenue_growth_2025')}`);
  card(s, 4.65, 1.5, 3.8, '2025毛利率', value('ks_a_grossmargin_2025'), `2024 ${value('ks_a_grossmargin_2024')}`);
  card(s, 8.7, 1.5, 4.0, '2025 EBITDA', value('ks_a_ebitda_2025'), '保留信用及资产减值影响', red);
  text(s, `归母利润减少 ${amount('ks_earn_parent_decline').toFixed(2)} 亿元：扣非恶化 ${amount('ks_earn_deducted_decline').toFixed(2)} 亿元，非经常支持减少 ${amount('ks_earn_nonrec_decline').toFixed(2)} 亿元。金融资产损益及应收转回分别核对，不能把恶化全部归于一次性减值。`, 0.6, 3.82, 12.1, 1.0, 22);
  text(s, `递延税收益 ${value('ks_tax_deferred_benefit')} 缓冲当期亏损，未形成现金流入；DTA可实现性仍须按纳税主体核验。季度改善和无保留审计意见不能单独排除旧应收损失或付款风险。`, 0.6, 5.12, 12.1, 1.0, 18);

  s = page('同行比较显示差异，也保留集团业务边界', ['ks_r_peer_finding']);
  const peer = q('ks_r_peers');
  table(s, [['2025集团口径','收入同比 %','负债/资产 %','净周期 天','EBITDA/费用化利息 倍'],
    ...peer.map(r => [r.company.replace('股份有限公司',''), ...['revenue_growth','liabilities_assets','noc360','ebitda_expinterest'].map(k => Number(r[k]).toFixed(2))])], 1.6, [4.1,1.8,1.9,1.8,2.5]);
  text(s, '科顺的利润、杠杆及账面周转压力不能只用行业下行解释。北新含重要石膏板/涂料业务，两家同行并购贡献未全年化重构；样本不构成行业均值或定级标尺。', 0.6, 4.18, 12.1, 1.08, 21);
  text(s, '同行简式融资口径和费用化利息倍数仅供比较，不能替代本案评级方法的全部债务与全部利息。', 0.6, 5.62, 12.1, 0.55, 17, red);

  s = page('现金质量取决于形成过程与季节性', ['ks_a_find_cfo','ks_a_find_q1','ks_a_e_indirect','ks_a_find_contingent']);
  card(s, 0.6, 1.5, 3.8, '全年经营净现金', value('ks_a_cfo_2025'), '正现金不等于正EBITDA');
  card(s, 4.65, 1.5, 3.8, '扣现金资本开支后', value('ks_a_fcf_2025'), '尚未扣并购、分配及其他投资');
  card(s, 8.7, 1.5, 4.0, '第四季CFO', value('ks_a_quarter4_cfo'), '不能掩盖前三季净流出');
  text(s, '非现金减值加回不会创造经营盈利。应收净额下降还可能来自准备、核销、抵债及范围变化，未完成滚动桥前不能直接视为客户多付现金。', 0.6, 3.85, 12.1, 1.0, 22);
  text(s, `经销贷款用于支付公司货款，同时保留公司保证责任；不以担保存量扣CFO。三月末集团外担保 ${amount('ks_credit_guarantee_external_q1').toFixed(2)} 亿元，下降 ${value('ks_credit_guarantee_external_decline')}，未证明六月逐笔解除。一季度CFO ${value('ks_a_q1_cfo')}。`, 0.6, 5.18, 12.1, 0.95, 18);

  s = page('一年条件资金容量：范围调整仍须补证', ['ks_horizon_find_horizon','ks_horizon_find_stress']);
  const dates = ['2026-06-30','2026-09-30','2026-12-31','2027-03-31','2027-06-30'];
  const cash = ['base','collection_delay_5pct'].map(id => ({ name: id === 'base' ? '基准' : '收款另延5%至窗后', labels: dates.map(d => d.slice(0,7)),
    values: dates.map(date => Number(q('ks_horizon_q_'+id).find(r => r.date === date).group_pool_before_unknown_DX)/1e8) }));
  s.addChart(p.ChartType.line, cash, { x: 0.6, y: 1.52, w: 7.9, h: 4.35, showLegend: false, chartColors: [green,red],
    showValue: false, showDataTable: true, showDataTableKeys: true, dataTableFontSize: 11, dataTableFormatCode: '0.00', catAxisLabelFontSize: 13, valAxisLabelFontSize: 12, valAxisTitle: '亿元人民币', showValAxisTitle: true,
    showMarker: true, showBorder: false, valGridLine: { color: 'DCE4E0', width: 0.5 } });
  text(s, `2027六月末资金池\n基准 ${value('ks_horizon_base_end_group_pool_before_unknown_DX')}\n\n延期分支\n${value('ks_horizon_collection_delay_5pct_end_group_pool_before_unknown_DX')}`, 8.95, 1.75, 3.72, 3.15, 22);
  text(s, '图示固定两版历史调整ΔA=ΔH=0、持续范围调整Γ=0；实际未知。各线还须扣未核还本D、净用途X、营运缓冲及用途隔离；季度末余额不证明月内付款覆盖。', 0.6, 6.01, 12.1, 0.42, 13, red);

  s = page('用途恢复与营运缓冲改变需要落实的融资', ['ks_d_n_funds','ks_project_n_restore_event','ks_horizon_find_horizon']);
  card(s, 0.6, 1.55, 3.8, '基准：用途占用6.5亿元', value('ks_horizon_base_peak_funding_intercept_U650'), '累计融资截距；15日研究缓冲');
  card(s, 4.65, 1.55, 3.8, '基准：用途占用13亿元', value('ks_horizon_base_peak_funding_intercept_U1300'), '参数敏感性；非实际占用', red);
  card(s, 8.7, 1.55, 4.0, '另延5%：用途占用6.5亿元', value('ks_horizon_collection_delay_5pct_peak_funding_intercept_U650'), '未当作已承诺融资', red);
  text(s, '临时补流须在2027-01-09十二个月边界及更早项目需要前恢复用途。归还专户是内部调度，须与已有用途预留去重；实际占用仍未知。', 0.6, 3.9, 12.1, 0.97, 22);
  text(s, '截距固定ΔA=ΔH=Γ=D=X=P=0，实际参数未知。范围调整须同时改变经营收付与缓冲；还本、净用途及合格项目耗用须另核并去重。实际融资需求尚不能定值。', 0.6, 5.16, 12.1, 0.8, 19, red);

  s = page('偿债主体是发行人，不能直接动用全部集团余额', ['ks_r_parent_risk','ks_d_e_issue_coupon','ks_d_e_maturity_call','ks_project_n_model','ks_project_n_timing']);
  card(s, 0.6, 1.48, 5.9, '母公司2025末：现金减短期账面代理', value('ks_r_parent_screen'), '未扣全体经营、票据、股利及用途需求');
  card(s, 6.8, 1.48, 5.9, '同日现金减固定本金未来到期价', value('ks_r_parent_maturity_gap'), '静态比较，不是本年已到期缺口', red);
  table(s, [['固定一季末面值情景','2026支付','2027支付','2028支付','2029支付'],
    ['合同现金需求（亿元）',...['2026','2027','2028','2029'].map(y => amount('ks_d_g_cash_'+y).toFixed(4))]], 3.74, [3.7,2.1,2.1,2.1,2.1], 15);
  text(s, `115%已含末息。旧项目末年净现金中${value('ks_project_c_terminal_share')}依赖终期回收，不能列为已落实偿债资金。四项建设募集投入${value('ks_project_c_project_ratio')}、均延至2028年末；还须证明现金可调度至发行人。`, 0.6, 5.25, 12.1, 0.9, 19);

  s = page('会计与合同疑点保留原值，不倒挤为零', ['ks_a_e_ar','ks_a_e_fixed','ks_d_n_covenant','ks_r_bond_bucket_finding','ks_project_n_put']);
  const unresolved = d.results.reconciliations.filter(r => ['ks_a_r_arres','ks_a_r_chuzhou'].includes(r.id) && r.status === 'unexplained_difference');
  table(s, [['需解释的原表勾稽','精确残差：人民币元'], ...unresolved.map(r => [d.reconciliations.find(x => x.id === r.id).label, Number(r.residual).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})])], 1.55, [8.6,3.5]);
  text(s, '两项滚动差异均回看原页后保留；另有债券期限表与固定本金合同时间轴的差额。均需解释，不能擅改原符号或直接推断整体报表失实。', 0.6, 3.61, 12.1, 1.0, 21);
  text(s, `债券账面余额/净资产 ${value('ks_d_c_book_ratio')} 与持续承诺存在待解释关系。发行条件、持续承诺、会议触发和实际加速后果分别核验，不能直接认定已违约或已获豁免。`, 0.6, 4.94, 12.1, 1.05, 20, red);

  s = page('跟踪应改变决定，而不只是更新比率', ['ks_r_followup','ks_r_rating_chain','ks_credit_find_facilities'], true);
  table(s, [['重算后成立的条件','条件建议','行动边界'],
    ...chain.slice(2,5).map(r => [r.business+'/'+r.finance,r.issuer,'其他调整、支持及付款条件不变']),
    ['证实近期无法按约付款','退出常态矩阵','确认合同事件并立即重新定级']], 1.6, [4.2,2.2,5.7], 17);
  text(s, `同一时点未用银行借款 ${amount('ks_a_undrawn').toFixed(1)} 亿元与未用授信 ${amount('ks_credit_facility_undrawn').toFixed(1)} 亿元尚未对齐，均不当作现金。逐项核提款条件、发行人付款日、用途及担保解除，再重算融资判断、资金边界与评级条件。`, 0.6, 4.65, 12.1, 1.22, 21, 'FFFFFF');
  await p.writeFile({ fileName: output });
  console.log(JSON.stringify({ slides: n, input, output }));
}
main();
