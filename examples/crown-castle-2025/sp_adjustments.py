"""从 Crown Castle 共同底稿复算 US GAAP 至 S&P 财务指标的分析桥。"""
import argparse
import json
import sys
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'skills/annual-report-analysis/scripts'))
from calculate import evaluate
from workpaper import Workpaper


def rebuild(w):
    model = Workpaper.model_validate(w)
    calculated = {c['id']: c for c in evaluate(model)['calculations']}
    facts = {f['id']: f for f in w['facts']}
    calculations = {c['id']: c for c in w['calculations']}
    snapshot = {}

    def amount(ref):
        if ref in facts:
            record = facts[ref]
            value = D(record['value']) * D(record['context']['scale'])
        else:
            record = calculations[ref]
            value = D(calculated[ref]['normalized'])
        snapshot[ref] = dict(record=record, normalized=str(value))
        return value / D('1000000') if record['context']['measure'] == 'money' else value

    rows = []
    figures = []

    def result(key, label, value, formula, *, measure='money', period='annual', status='analysis_estimate'):
        context = dict(entity=model.mandate.entity, scope='continuing_operations_method_bridge',
                       start='2025-01-01', end='2025-12-31', aggregation='flow',
                       basis='US GAAP to S&P Ratios and Adjustments (2025-12-17)',
                       measure=measure, currency='USD' if measure == 'money' else None,
                       scale='1000000' if measure == 'money' else '1', physical_unit=None)
        if period == 'balance':
            context.update(start=None, aggregation='instant')
        if measure == 'ratio':
            context['aggregation'] = 'ratio'
            context['physical_unit'] = 'times' if key == 'leverage' else None
        rows.append(dict(metric=label, result=str(value), formula=formula, status=status))
        figures.append(dict(id='sp_' + key, label=label, row=len(rows)-1, field='result', context=context))
        return value

    lease_interest = result('lease_interest', '经营租赁利息代理',
        amount('C_sp_lease_average') * amount('sp_lease_rate'),
        'C_sp_lease_average × sp_lease_rate', status='method_proxy')
    lease_principal = result('lease_principal_proxy', '经营租赁折旧及CFO加回代理',
        amount('sp_rou_cost') - lease_interest, 'sp_rou_cost − sp_lease_interest', status='method_proxy')
    ebitda = result('ebitda', 'S&P口径EBITDA分析估计',
        amount('opincome2025') + amount('daa2025') + amount('sp_rou_cost')
        + amount('sbc2025') + amount('writedown2025'),
        'opincome2025 + daa2025 + sp_rou_cost + sbc2025 + writedown2025')
    result('accrual_interest', '应计利息已识别调整小计',
        -amount('interest2025') + amount('sp_capitalized_interest') + lease_interest + amount('sp_aro_accretion'),
        '−interest2025 + sp_capitalized_interest + sp_lease_interest + sp_aro_accretion')
    capitalized_cash = amount('sp_capitalized_cash_estimate')
    cash_interest = result('cash_interest', '现金利息分析估计（含租赁代理）',
        amount('sp_interest_paid_net') + capitalized_cash + lease_interest,
        'sp_interest_paid_net + sp_capitalized_cash_estimate + sp_lease_interest')
    ffo = result('ffo', 'FFO分析估计', ebitda - cash_interest - amount('sp_cash_tax'),
        'sp_ebitda − sp_cash_interest − sp_cash_tax')
    cfo = result('cfo', 'CFO分析估计', amount('C_contcfo_2025') + lease_principal - capitalized_cash,
        'C_contcfo_2025 + sp_lease_principal_proxy − sp_capitalized_cash_estimate')
    capex = result('capex', '资本支出分析估计（移出资本化现金利息）',
        -amount('capex2025') - capitalized_cash, '−capex2025 − sp_capitalized_cash_estimate')
    result('focf', 'FOCF分析估计（尚非付完全部租赁本金的现金）', cfo - capex, 'sp_cfo − sp_capex')
    sbc_residual = amount('C_sp_sbc_residual')
    result('ebitda_rsu', '仅加回已直接证实RSU的EBITDA敏感性', ebitda - sbc_residual,
        'sp_ebitda − C_sp_sbc_residual', status='classification_sensitivity')
    result('ffo_rsu', '仅加回已直接证实RSU的FFO敏感性', ffo - sbc_residual,
        'sp_ffo − C_sp_sbc_residual', status='classification_sensitivity')
    result('ebitda_writeoff', '采用PP&E核销总额的EBITDA敏感性', ebitda + amount('C_sp_writeoff_difference'),
        'sp_ebitda + C_sp_writeoff_difference', status='classification_sensitivity')
    gross_debt = result('gross_debt', '债务分析估计（ARO尚未抵减）',
        amount('debt2025') + amount('C_sp_lease_end') + amount('sp_aro_end'),
        'debt2025 + C_sp_lease_end + sp_aro_end', period='balance')
    net_debt = result('net_debt', '仅扣99合格现金的条件债务', gross_debt - amount('cash2025'),
        'sp_gross_debt − cash2025', period='balance', status='conditional_cash_accessibility')
    result('leverage', '2025历史条件债务/EBITDA', net_debt / ebitda,
        'sp_net_debt / sp_ebitda', measure='ratio', status='historical_not_post_sale')
    result('ffo_debt', '2025历史条件FFO/债务', ffo / net_debt,
        'sp_ffo / sp_net_debt', measure='ratio', status='historical_not_post_sale')
    result('sbc_effect', '股份支付差额对EBITDA的影响', sbc_residual / ebitda,
        'C_sp_sbc_residual / sp_ebitda', measure='ratio', status='classification_sensitivity')

    q = dict(id='Q_sp_crown', label='Crown Castle持续经营财务方法桥',
        method='S&P Ratios and Adjustments 2025-12-17；案例专用Decimal复算',
        as_of='2026-06-30', input_refs=list(snapshot),
        evidence=['E_SP_RATIOS', 'E_SP_SCOPE', 'E_SP_LEASE', 'E_SP_CASH', 'E_SP_SBC', 'E_SP_ARO', 'E_SP_XBRL'],
        assumptions=[
            '资本化现金付息以同年已披露应计资本化利息估计，原报值与估计分列；改变该估计时FFO和CFO同额反向变动，资本支出同额反向变动，FOCF不变。',
            '股份支付全部作为权益结算、资产净减记全部作为非流动项是有披露支持的分析估计；RSU已直接证实，余项另给敏感性。内部使用软件按适用方法不反转。',
            'ARO先采用未抵减负债的分析估计；税益、专款和残值尚未量化。条件净债仅扣普通现金，并以其符合方法可动用条件为前提。'],
        limitations=[
            '指标是按已识别事项形成的分析估计，不是S&P发表的发行人指标或会计报表重述；不构成主体或债项等级。',
            '历史2025持续经营利润与当年末保留债务配套；未把2026实际出售收款直接从历史债务扣除。',
            '租赁CFO加回是方法分类代理，不等于实际付款，也不增加可支用现金。受限现金用途及最终售后债务现金仍需独立取证。'],
        artifact=dict(input_snapshot=snapshot, rows=rows,
            units='金额为百万美元；ratio为小数，leverage为倍数。输入快照另保留基础单位和原始context。',
            execution='由examples/crown-castle-2025/sp_adjustments.py读取同一底稿原值和基础运算结果，实际执行Decimal算术。'),
        figures=figures)
    w['quantitative'] = [old for old in w['quantitative'] if old['id'] != q['id']] + [q]
    Workpaper.model_validate(w)
    return w


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workpaper', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    updated = rebuild(json.loads(args.workpaper.read_text(encoding='utf-8-sig')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
