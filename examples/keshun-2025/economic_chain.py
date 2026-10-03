"""科顺专用条件研究；读取共同底稿与参数，输出经营、现金、融资、财务与评级因子。"""
import argparse
import hashlib
import json
import sys
from datetime import date
from decimal import Decimal as D, getcontext
from pathlib import Path

getcontext().prec = 32
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'skills/annual-report-analysis/scripts'))
from calculate import evaluate
from workpaper import Workpaper


def load_inputs(workpaper_path, parameter_path):
    w = Workpaper.model_validate_json(workpaper_path.read_text(encoding='utf-8-sig'))
    p = json.loads(parameter_path.read_text(encoding='utf-8'))
    values = {f.id: str(f.value*f.context.scale) if f.value is not None else None for f in w.facts}
    values.update({c['id']: c['normalized'] for c in evaluate(w)['calculations']})
    used = set()
    def val(k):
        used.add(k)
        return values[k]
    needed = ['revenue','cost','selling','admin','surtax','creditimp','assetimp','equity','assets','debt','stdebt','currentliab','cashlike','customerscash','ebit','ebitda','interest_total','interest_exp','pbt','average_assets']
    historical = {str(y): {k:val(f'ks_a_{k}_{y}') for k in needed} for y in [2024,2025]}
    q1 = {k:val('ks_a_q1_'+k) for k in ['assets','liab','equity','cashbook','cash','ar','stborrow','notes_ap','currentlongliab','ltborrow','bonds','lease','revenue','cost','netincome','creditimp','assetimp','cfo','capex']}
    q1.update({k:val('ks_econ_q1_'+k) for k in ['currentliab','pbt','interest_exp','tax_expense','trading','notes_ar','arfin','inventory','ap','other_ar','taxpay']})
    q1['customerscash']=val('ks_d_l_f_q1_2026_customerscash')
    cash_base = next(q for q in w.quantitative if q.id=='ks_r_cash_base')
    used.update(cash_base.input_refs)
    fields = ['period_start','period_end','revenue','customer_receipts','other_operating_receipts','tax_refund_receipts','ordinary_supplier_payments','incremental_trade_settlement','employee_payments','tax_payments','other_operating_payments','capex','dividend','bond_coupon']
    anchors = [{k:a[k] for k in fields} for a in cash_base.artifact['rows'][:3]]
    for q, rev in [(1,q1['revenue']),(2,anchors[0]['revenue'])]:
        def cv(kind):
            if q==1: return D(val('ks_d_l_f_q1_2026_'+kind))
            return D(val('ks_horizon_f_h125_'+kind))-D(val('ks_d_l_f_q1_2025_'+kind))
        anchors.append(dict(period_start='2027-01-01' if q==1 else '2027-04-01',period_end='2027-03-31' if q==1 else '2027-06-30',revenue=rev,
            customer_receipts=str(cv('customerscash')*D('.97')),other_operating_receipts=str(cv('otheropcashin')*D('.90')),tax_refund_receipts='0',
            ordinary_supplier_payments=str(cv('suppliercash')),incremental_trade_settlement='0',employee_payments=str(cv('employeecash')),
            tax_payments=str(cv('taxcash')),other_operating_payments=str(cv('otheropcashout')),capex=q1['capex'] if q==1 else str(D(val('ks_horizon_f_h125_capex'))-D(val('ks_d_l_f_q1_2025_capex'))),dividend='0',bond_coupon='0'))
    material = {f'revenue_{y}':val(f'ks_econ_material_revenue_{y}') for y in [2024,2025]}
    material.update({f'costs_{y}':[val(f'ks_econ_material_{k}_{y}') for k in ['direct_material','fuel','labor','manufacturing','freight']] for y in [2024,2025]})
    result = dict(as_of=p['as_of'],historical=historical,q1=q1,anchors=anchors,rd_2025=val('ks_a_rd_2025'),
                  da_2025=str(sum(D(val(f'ks_a_{k}_2025')) for k in ['dep','dep_rou','amort','amort_long'])),
                  material=material,research_parameters=p['parameters'],
                  other_receipt_components={k:val('ks_econ_cash_'+k+'_2025') for k in ['interest','grants','guarantee','restricted','staff','other_unknown']},
                  current_tax_2025=val('ks_a_taxcurrent'),tax_cash_2025=val('ks_a_taxcash_2025'),
                  opening_income_tax_payable_proxy=val('ks_econ_income_tax_payable_2025'),
                  q1_capitalized_interest_proxy=str(D(val('ks_a_interest_cap_2025'))/4),
                  cashlike_non_CCE_proxy=str(D(q1['trading'])+D(q1['notes_ar'])+D(val('ks_a_arfin_notes_2025'))-D(val('ks_a_restricted_note_2025'))),
                  input_refs=sorted(used),
                  source_scope_propagation=cash_base.artifact['scope_propagation'])
    result['source_input_sha256']=hashlib.sha256(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
    return result


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('workpaper', type=Path)
parser.add_argument('parameters', type=Path)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
I = load_inputs(args.workpaper, args.parameters)
H = {y: {k: D(v) for k, v in x.items()} for y, x in I['historical'].items()}
Q = {k: D(v) for k, v in I['q1'].items()}
P = {k: D(v) for k, v in I['research_parameters'].items() if k != 'redemption_book_budgets'}
P.update({k:D(I[k]) for k in ['q1_capitalized_interest_proxy','cashlike_non_CCE_proxy']})
R = H['2025']['revenue']
DA = D(I['da_2025'])
MAT = D(I['material']['costs_2025'][0])
OPEX = H['2025']['selling'] + H['2025']['admin'] + D(I['rd_2025']) + H['2025']['surtax']
WEIGHTS = dict(asset_quality=D('.1'), ebitda_margin=D('.07'), roa=D('.03'), equity=D('.15'),
               debt_cap=D('.15'), interest_cover=D('.1'), leverage=D('.125'),
               receipts_current=D('.075'), cash_short=D('.075'), refinance=D('.125'))


def score(k, v):
    if v is None:
        return None
    # 本案例实际采用的联合PDF30–31原表分区；区间内取中点为研究约定。
    ascending = {
        'ebitda_margin': [(-30, '1'), (-10, '1.5'), (0, '2.5'), (2.5, '3.5'), (5, '4.5'), (10, '5.5'), (20, '6.5')],
        'roa': [(-8, '1'), (-4, '1.5'), (0, '2.5'), (1, '3.5'), (2, '4.5'), (4, '5.5'), (8, '6.5')],
        'equity': [(5, '1'), (10, '1.5'), (15, '2.5'), (25, '3.5'), (50, '4.5'), (100, '5.5'), (300, '6.5')],
        'interest_cover': [(0, '1'), (.25, '1.5'), (.5, '2.5'), (1, '3.5'), (2, '4.5'), (4, '5.5'), (6, '6.5')],
        'receipts_current': [(.1, '1'), (.2, '1.5'), (.4, '2.5'), (.7, '3.5'), (1.1, '4.5'), (1.5, '5.5'), (3, '6.5')],
        'cash_short': [(.02, '1'), (.05, '1.5'), (.1, '2.5'), (.2, '3.5'), (.4, '4.5'), (.6, '5.5'), (1.2, '6.5')],
    }
    if k in ascending:
        return next((D(s) for limit, s in ascending[k] if v < D(str(limit))), D(7))
    if k == 'debt_cap':
        return next((D(s) for limit, s in [(45, '7'), (50, '6.5'), (60, '5.5'), (70, '4.5'), (75, '3.5'), (80, '2.5'), (85, '1.5')] if v <= limit), D(1)) if v >= 0 else D(1)
    if k == 'leverage':
        return next((D(s) for limit, s in [(4, '7'), (8, '6.5'), (15, '5.5'), (20, '4.5'), (25, '3.5'), (30, '2.5'), (40, '1.5')] if v <= limit), D(1)) if v >= 0 else D(1)
    return v


def category(s):
    return next(('F' + str(n) for n, lower in enumerate(['6.5', '5.5', '4.5', '3.5', '2.5', '1.5', '1'], 1) if s >= D(lower)))


def factors(years, weights, quality, refinance):
    amounts = {k: sum(w * years[y][k] for y, w in weights.items()) for k in
               ['revenue', 'ebitda', 'ebit', 'average_assets', 'equity', 'debt', 'interest_total', 'customerscash', 'currentliab', 'cashlike', 'stdebt']}
    v = dict(asset_quality=quality, refinance=refinance, ebitda_margin=100*amounts['ebitda']/amounts['revenue'],
             roa=100*amounts['ebit']/amounts['average_assets'], equity=amounts['equity']/D('1e8'),
             debt_cap=100*amounts['debt']/(amounts['debt']+amounts['equity']),
             interest_cover=amounts['ebitda']/amounts['interest_total'] if amounts['interest_total'] else None,
             leverage=amounts['debt']/amounts['ebitda'] if amounts['ebitda'] else None,
             receipts_current=amounts['customerscash']/amounts['currentliab'], cash_short=amounts['cashlike']/amounts['stdebt'])
    rows = [dict(factor=k, input=v[k], weight=WEIGHTS[k], score=score(k,v[k]),
                 contribution=WEIGHTS[k]*score(k,v[k]) if v[k] is not None else None,
                 undefined_reason='加权分母为零，指标无定义；未伪造零杠杆或最高分。' if v[k] is None else None) for k in WEIGHTS]
    subtotal = sum(x['contribution'] for x in rows if x['contribution'] is not None)
    unresolved_weight = sum(x['weight'] for x in rows if x['score'] is None)
    total = subtotal if not unresolved_weight else None
    # 全部债务/EBITDA在混合正负年度不作带符号比率均值；金额先加权后求比率。
    grade = category(total) if total is not None else None
    cells = {'F3': ('a+/a', 'A'), 'F4': ('a-/bbb+', 'BBB+'), 'F5': ('bbb/bbb-', 'BBB-'), 'F6': ('bb+/bb', 'BB')}
    cell, chosen = cells.get(grade,(None,None))
    annual_ratios = {}
    for y in weights:
        a=years[y]
        annual_ratios[y]=dict(ebitda_margin=100*a['ebitda']/a['revenue'],roa=100*a['ebit']/a['average_assets'],
            equity=a['equity']/D('1e8'),debt_cap=100*a['debt']/(a['debt']+a['equity']),
            interest_cover=a['ebitda']/a['interest_total'] if a['interest_total'] else None,
            leverage=a['debt']/a['ebitda'] if a['ebitda'] else None,
            receipts_current=a['customerscash']/a['currentliab'],cash_short=a['cashlike']/a['stdebt'])
    ratio_inputs={k:sum(w*annual_ratios[y][k] for y,w in weights.items()) if all(annual_ratios[y][k] is not None for y in weights) else None for k in annual_ratios[next(iter(weights))]}
    ratio_inputs.update(asset_quality=quality,refinance=refinance)
    ratio_scores={k:score(k,v) for k,v in ratio_inputs.items()}
    mixed_sign=any(years[y]['ebitda']<0 for y in weights) and any(years[y]['ebitda']>0 for y in weights)
    if mixed_sign and ratio_inputs['leverage'] is not None:
        ratio_inputs['leverage_signed_mean_display_only']=ratio_inputs['leverage']
        ratio_inputs['leverage']=None
        ratio_scores['leverage']=D(1) if amounts['ebitda']<0 else None
    ratio_subtotal=sum(WEIGHTS[k]*v for k,v in ratio_scores.items() if v is not None)
    ratio_unresolved=sum(WEIGHTS[k] for k,v in ratio_scores.items() if v is None)
    ratio_result=dict(inputs=ratio_inputs,scores=ratio_scores,
        score=ratio_subtotal if not ratio_unresolved else None,
        financial_category=category(ratio_subtotal) if not ratio_unresolved else None,
        mixed_sign_leverage_rule='年度分母为零先保留无定义；非零但混合正负时，加权金额EBITDA负则最低档，否则杠杆未决，不用带符号均值抵销。',
        undefined_reasons={k:'至少一个年度分母为零或正负分母混合，无法唯一赋分；原年度值另列。' for k,s in ratio_scores.items() if s is None},
        score_range_if_unresolved=[ratio_subtotal+ratio_unresolved,ratio_subtotal+7*ratio_unresolved] if ratio_unresolved else None)
    interval_half_width=sum(x['weight']/2 for x in rows if x['score'] is not None and x['score']%1 and x['factor'] not in ['asset_quality','refinance'])
    return dict(rows=rows, weighted_amounts=amounts, input_year_weights=weights, financial_score=total, category=grade,
                selected_research_route='本函数先加权会计金额再求比率；预测2026进入20/30/50以及金额先加权均为明示研究适配，并非替换现有历史年度比率主路径。历史30/70比较另列。',
                annual_ratios=annual_ratios,annual_ratio_first_comparison=ratio_result,
                score_range_if_unresolved=[subtotal+unresolved_weight,subtotal+7*unresolved_weight] if unresolved_weight else None,
                lower=subtotal+unresolved_weight-interval_half_width,
                upper_supremum=subtotal+7*unresolved_weight+interval_half_width,
                business='C', matrix_cell=cell, matrix_weak_end=chosen,
                individual_adjustment=0, support_notches=0, issue_notches=0,
                conditional_issuer=chosen, conditional_keshun_convertible=chosen)


def project(material_shock, impairment_anchor, finance_limit=None, cashlike_addon=None, vat_recovery=D(1), current_tax_multiplier=None, tax_paid_same_quarter=None, other_income_occurs=True):
    cash, equity, assets = Q['cash'], Q['equity'], Q['assets']
    old_loans = Q['stborrow']+Q['currentlongliab']+Q['ltborrow']+Q['lease']
    initial_current = Q['stborrow']+Q['currentlongliab']
    notes, bonds, new_loans = Q['notes_ap'], Q['bonds'], D(0)
    debt0 = old_loans+notes+bonds
    other_liab = Q['liab']-debt0
    residual_assets = Q['assets']-Q['cash']
    cumulative_redemptions = previous_material_payable = vat_receivable = D(0)
    opening_income_tax_payable = D(I['opening_income_tax_payable_proxy'])
    income_tax_payable = opening_income_tax_payable
    recovery_pool = Q['cashbook']-Q['cash']+Q['other_ar']
    receipt_components = {k:D(v) for k,v in I['other_receipt_components'].items()}
    receipts_total = sum(receipt_components.values())
    tax_multiplier = P['current_tax_multiplier'] if current_tax_multiplier is None else current_tax_multiplier
    tax_payment_fraction = P['current_tax_paid_same_quarter'] if tax_paid_same_quarter is None else tax_paid_same_quarter
    rows = []
    for n, a in enumerate(I['anchors']):
        d = {k:D(v) for k,v in a.items() if k not in ['period_start','period_end']}
        days = D((date.fromisoformat(a['period_end'])-date.fromisoformat(a['period_start'])).days+1)
        period_fraction = days/365
        revenue = d['revenue']*P['revenue_factor']
        material_base = revenue*MAT/R
        material_extra = material_base*material_shock
        material_paid = material_extra*P['paid_same_quarter']+previous_material_payable
        material_payable = material_extra*(1-P['paid_same_quarter'])
        delta_material_ap = material_payable-previous_material_payable
        cost = revenue*H['2025']['cost']/R+material_extra
        op_expense = revenue*OPEX/R
        if impairment_anchor == 'q1':
            impairment = revenue*(-Q['creditimp']-Q['assetimp'])/Q['revenue']
        else:
            impairment = revenue*(-H['2025']['creditimp']-H['2025']['assetimp'])/R
        depreciation = DA*period_fraction
        # 按年报性质拆开现金预算：新增收益同季确认；存量资产回收另列余额池，未拆其他不预测。
        interest_income = d['other_operating_receipts']*receipt_components['interest']/receipts_total if other_income_occurs else D(0)
        grants_income = d['other_operating_receipts']*receipt_components['grants']/receipts_total if other_income_occurs else D(0)
        recovery_requested = d['other_operating_receipts']*sum(receipt_components[k] for k in ['guarantee','restricted','staff'])/receipts_total
        recovery_pool_begin = recovery_pool
        asset_recovery = min(recovery_requested,recovery_pool)
        recovery_pool -= asset_recovery
        other_receipts = interest_income+grants_income+asset_recovery
        ebit = revenue-cost-op_expense-impairment+interest_income+grants_income
        ebitda = ebit+depreciation
        receipts = d['customer_receipts']*P['revenue_factor']
        supplier_cash = d['ordinary_supplier_payments']*P['revenue_factor']+material_paid*D('1.13')
        vat_recovered = material_paid*D('.13')*vat_recovery
        vat_increase = material_paid*D('.13')-vat_recovered
        vat_receivable += vat_increase
        # 公开当期税/毛现金税比例仅用于预算拆分；先剔除旧代理份额，再加独立税支付，避免重复。
        embedded_income_tax_cash = d['tax_payments']*D(I['current_tax_2025'])/D(I['tax_cash_2025'])
        income_tax_begin = income_tax_payable
        taxes = D(I['current_tax_2025'])*period_fraction*tax_multiplier
        income_tax_cash = income_tax_begin+taxes*tax_payment_fraction
        income_tax_payable += taxes-income_tax_cash
        other_tax_cash = d['tax_payments']-embedded_income_tax_cash
        tax_cash = other_tax_cash+income_tax_cash-vat_recovered
        op_payments = supplier_cash+d['incremental_trade_settlement']+d['employee_payments']+tax_cash+d['other_operating_payments']
        cfo = receipts+other_receipts+d['tax_refund_receipts']-op_payments
        redemption = D(I['research_parameters']['redemption_book_budgets'][n])
        accrued_remaining = max(0,P['opening_accrued_interest_proxy']-cumulative_redemptions)
        cash_interest_before_draw = (old_loans-accrued_remaining)*P['legacy_loan_rate']*period_fraction+new_loans*P['new_loan_rate']*period_fraction
        bond_interest = bonds*P['bond_effective_rate']*period_fraction
        if d['bond_coupon']:
            bond_interest -= d['bond_coupon']*P['bond_effective_rate']*D(57)/365
        floor = op_payments*P['buffer_days']/days
        reserve = P['U'] if n >= 2 else D(0)  # 在12月末提前备足1月9日用途恢复，仍留在集团资产中。
        cash_without_draw = cash+cfo-d['capex']-d['dividend']-redemption-d['bond_coupon']-cash_interest_before_draw
        required_draw = max(0,(floor+reserve-cash_without_draw)/(1-P['new_loan_rate']*period_fraction))
        draw = required_draw if finance_limit is None else min(required_draw,max(0,finance_limit-new_loans))
        new_interest = draw*P['new_loan_rate']*period_fraction
        cash_interest = cash_interest_before_draw+new_interest
        interest = cash_interest+bond_interest
        pbt = ebit-interest
        profit = pbt-taxes
        debt_start = old_loans+notes+bonds+new_loans
        old_loans -= redemption
        cumulative_redemptions += redemption
        notes -= d['incremental_trade_settlement']
        bonds += bond_interest-d['bond_coupon']
        new_loans += draw
        debt = old_loans+notes+bonds+new_loans
        cash_end = cash_without_draw+draw-new_interest
        equity += profit-d['dividend']
        other_liab += delta_material_ap+taxes-income_tax_cash
        # 从间接法推出净营运资产变化，单列已计入CFO但归广义债务的票据清偿。
        delta_nwc = profit+depreciation+impairment+interest-cfo-d['incremental_trade_settlement']
        delta_operating_assets = delta_nwc+delta_material_ap+taxes-income_tax_cash-impairment
        residual_assets += delta_operating_assets+d['capex']-depreciation
        assets = cash_end+residual_assets
        shortdebt = initial_current-cumulative_redemptions+notes
        currentliab = Q['currentliab']-cumulative_redemptions-(Q['notes_ap']-notes)+material_payable+income_tax_payable-opening_income_tax_payable
        addon = P['cashlike_non_CCE_proxy'] if cashlike_addon is None else cashlike_addon
        cashlike = cash_end-reserve+addon
        row = dict(period_start=a['period_start'],period_end=a['period_end'],revenue=revenue,cost=cost,gross_profit=revenue-cost,
                   operating_expenses=op_expense,impairment=impairment,ebit=ebit,ebitda=ebitda,depreciation=depreciation,
                   material_base=material_base,material_cost_increase=material_extra,material_accrued_purchase_increase=material_extra,
                   material_inventory_increase=D(0),material_cash_payment_increase=material_paid,material_payable_end=material_payable,
                   material_gross_supplier_payment=material_paid*D('1.13'),same_period_vat_credit_cash=vat_recovered,
                   incremental_vat_receivable=vat_receivable,income_tax_expense=taxes,income_tax_cash=income_tax_cash,
                   income_tax_payable_begin=income_tax_begin,income_tax_payable_end=income_tax_payable,
                   income_tax_payable_change=taxes-income_tax_cash,embedded_income_tax_cash_removed=embedded_income_tax_cash,
                   original_gross_tax_cash_budget=d['tax_payments'],other_tax_cash_budget=other_tax_cash,
                   tax_cash_after_vat=tax_cash,interest_income_and_cash=interest_income,grants_income_and_cash=grants_income,
                   income_receipts_excluded=d['other_operating_receipts']*(receipt_components['interest']+receipt_components['grants'])/receipts_total-interest_income-grants_income,
                   unclassified_other_receipts_excluded=d['other_operating_receipts']*receipt_components['other_unknown']/receipts_total,
                   other_operating_receipts=other_receipts,asset_recovery_requested=recovery_requested,asset_recovery_cash=asset_recovery,
                   recovery_pool_begin=recovery_pool_begin,recovery_pool_end=recovery_pool,
                   customer_receipts=receipts,cfo=cfo,cash_begin=cash,capex=d['capex'],dividend=d['dividend'],
                   redemption_book_budget=redemption,trade_note_settlement=d['incremental_trade_settlement'],
                   bond_cash_coupon=d['bond_coupon'],bond_book_interest=bond_interest,cash_interest=cash_interest,
                   interest_total=interest,new_draw_interest=new_interest,pbt=pbt,taxes=taxes,net_income=profit,
                   required_new_draw=required_draw,new_draw=draw,cumulative_new_draw=new_loans,cash_end=cash_end,
                   minimum_cash=floor,purpose_reserve=reserve,headroom=cash_end-floor-reserve,debt_begin=debt_start,
                   debt_end=debt,shortdebt=shortdebt,currentliab=currentliab,cashlike=cashlike,equity=equity,assets=assets,
                   other_liabilities=other_liab,delta_nwc=delta_nwc,delta_operating_assets=delta_operating_assets,
                   delta_unallocated_operating_assets=delta_operating_assets-vat_increase+asset_recovery,
                   cash_residual=cash_end-(cash+cfo-d['capex']-d['dividend']-redemption-d['bond_coupon']-cash_interest+draw),
                   debt_residual=debt-(debt_start+draw-redemption-d['incremental_trade_settlement']+bond_interest-d['bond_coupon']),
                   balance_residual=assets-debt-other_liab-equity,
                   equation_residual=required_draw*(1-P['new_loan_rate']*period_fraction)-max(0,floor+reserve-cash_without_draw))
        rows.append(row)
        cash, previous_material_payable = cash_end, material_payable
        if cash_end < floor+reserve-D('.01'):
            return dict(material_shock=material_shock,impairment_anchor=impairment_anchor,rows=rows,status='financing_condition_failed',
                        forecast_rating=None,first_unfunded_date=a['period_end'],gap_to_floor_and_reserve=floor+reserve-cash_end,
                        missing_issuer_actual_resources=None)
    first = rows[:3]
    yend = first[-1]
    annual = dict(revenue=Q['revenue']+sum(x['revenue'] for x in first),
                  ebit=Q['pbt']+Q['interest_exp']+sum(x['ebit'] for x in first),
                  ebitda=Q['pbt']+Q['interest_exp']+DA*D(90)/365+sum(x['ebitda'] for x in first),
                  pbt=Q['pbt']+sum(x['pbt'] for x in first),net_income=Q['netincome']+sum(x['net_income'] for x in first),
                  interest_total=Q['interest_exp']+P['q1_capitalized_interest_proxy']+sum(x['interest_total'] for x in first),
                  customerscash=Q['customerscash']+sum(x['customer_receipts'] for x in first),
                  cfo=Q['cfo']+sum(x['cfo'] for x in first),average_assets=(H['2025']['assets']+yend['assets'])/2,
                  **{k:yend[v] for k,v in [('equity','equity'),('debt','debt_end'),('stdebt','shortdebt'),('currentliab','currentliab'),('cashlike','cashlike'),('assets','assets')]})
    years = {**H,'2026':annual}
    f = factors(years,{'2024':D('.2'),'2025':D('.3'),'2026':D('.5')},D('2.7'),D('4.35'))
    adjacent = []
    for aq_shift in [D('-.5'),D(0),D('.5')]:
        for ref_shift in [D('-.5'),D(0),D('.5')]:
            ff=factors(years,{'2024':D('.2'),'2025':D('.3'),'2026':D('.5')},D('2.7')+aq_shift,D('4.35')+ref_shift)
            adjacent.append(dict(asset_quality_shift=aq_shift,refinance_shift=ref_shift,score=ff['financial_score'],category=ff['category'],conditional_issuer=ff['conditional_issuer']))
    events=[]
    for index,event,elapsed in [(1,'2026-08-04',D(35)),(3,'2027-01-09',D(9))]:
        r=rows[index]
        days=D((date.fromisoformat(r['period_end'])-date.fromisoformat(r['period_start'])).days+1)
        event_cash=r['cash_begin']+r['new_draw']+(r['cfo']-r['capex'])*elapsed/days-r['bond_cash_coupon']
        events.append(dict(date=event,group_cash=event_cash,headroom=event_cash-r['minimum_cash']-r['purpose_reserve'],
            issuer_dispatchable_cash=None,assumption='提款期初到位；其他经营/capex均匀、本金及银行利息季末支付；全额票息在8月4日支付，1月9日用途资金已于12月末预留。'))
    return dict(material_shock=material_shock,impairment_anchor=impairment_anchor,vat_recovery=vat_recovery,
                current_tax_multiplier=tax_multiplier,tax_paid_same_quarter=tax_payment_fraction,other_income_occurs=other_income_occurs,rows=rows,annual_2026=annual,
                dated_group_cash_tests=events,
                forecast_rating=f,joint_qualitative_adjacent=adjacent,status='conditional_research_not_actual_payment_verification')


def serialize(x):
    if isinstance(x,D): return str(x)
    if isinstance(x,dict): return {k:serialize(v) for k,v in x.items()}
    if isinstance(x,list): return [serialize(v) for v in x]
    return x


def main():
    c24=list(map(D,I['material']['costs_2024'])); c25=list(map(D,I['material']['costs_2025']))
    bridge=dict(gross_profit_2024=D(I['material']['revenue_2024'])-sum(c24),gross_profit_2025=D(I['material']['revenue_2025'])-sum(c25),
                revenue_contribution=D(I['material']['revenue_2025'])-D(I['material']['revenue_2024']),
                cost_contributions=[x-y for x,y in zip(c24,c25)],historical_flat_volume_5pct_sensitivity=MAT*D('.05'))
    cases={f'{imp}_{shock}':project(D(shock),imp) for imp in ['q1','annual2025'] for shock in ['0','.05']}
    cases['q1_.05_finance_cap_500m']=project(D('.05'),'q1',P['finance_capacity_case'])
    cases['q1_.05_cashlike_CCE_only']=project(D('.05'),'q1',cashlike_addon=D(0))
    cases['q1_.05_vat_deferred']=project(D('.05'),'q1',vat_recovery=D(0))
    cases['q1_.05_zero_new_current_tax']=project(D('.05'),'q1',current_tax_multiplier=D(0))
    cases['q1_.05_tax_paid_same_quarter']=project(D('.05'),'q1',tax_paid_same_quarter=D(1))
    cases['q1_.05_no_other_income']=project(D('.05'),'q1',other_income_occurs=False)
    historical_joint=[]
    for aq in [D('-.5'),D(0),D('.5')]:
        for rf in [D('-.5'),D(0),D('.5')]:
            f=factors(H,{'2024':D('.3'),'2025':D('.7')},D('2.8')+aq,D('4.65')+rf)
            historical_joint.append(dict(asset_quality_shift=aq,refinance_shift=rf,score=f['financial_score'],category=f['category'],issuer=f['conditional_issuer'],lower=f['lower'],upper_supremum=f['upper_supremum']))
    result=dict(input_snapshot=I,historical_material_bridge=bridge,historical_qualitative_joint=historical_joint,cases=cases,
                actual_unknowns={k:None for k in ['delta_A','delta_H','Gamma_by_quarter','U','P','D_actual_contract_schedule','X','issuer_dispatchable_A','additional_Q1_debt','accrued_interest_split','Q1_lease_split','Q1_eligible_cashlike','Q1_DA','Q1_capitalized_interest','Q1_income_tax_payable_split','future_tax_by_entity','historical_income_tax_cash_split','future_other_receipt_mix','asset_recovery_eligibility']})
    for c in cases.values():
        for r in c['rows']:
            assert max(abs(r[k]) for k in ['cash_residual','debt_residual','balance_residual','equation_residual'])<D('.000001')
            assert abs(r['material_accrued_purchase_increase']-r['material_cost_increase'])<D('.000001')
            assert abs(r['income_tax_payable_begin']+r['income_tax_expense']-r['income_tax_cash']-r['income_tax_payable_end'])<D('.000001')
            assert abs(r['original_gross_tax_cash_budget']-r['embedded_income_tax_cash_removed']+r['income_tax_cash']-r['same_period_vat_credit_cash']-r['tax_cash_after_vat'])<D('.000001')
            assert r['recovery_pool_end'] >= 0
    for imp in ['q1','annual2025']:
        for base,stress in zip(cases[imp+'_0']['rows'],cases[imp+'_.05']['rows']):
            assert abs(stress['delta_unallocated_operating_assets']-base['delta_unallocated_operating_assets'])<D('.000001')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(serialize(result),ensure_ascii=False,indent=2),encoding='utf-8')
    for k,c in cases.items():
        a=c.get('annual_2026',{})
        print(k,c['status'],'EBITDA',a.get('ebitda'),'NI',a.get('net_income'),'CFO',a.get('cfo'),'debt',a.get('debt'),'new debt',c['rows'][-1]['cumulative_new_draw'],'F',c.get('forecast_rating',{}).get('financial_score') if c.get('forecast_rating') else None)


if __name__=='__main__':
    main()
