"""Crown-specific forward cash and credit bridge; reads shared workpaper IDs."""
import argparse
import hashlib
import json
import sys
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'skills/annual-report-analysis/scripts'))
from calculate import evaluate
from workpaper import Workpaper


def run(w, overrides=None, *, joint=False, facility=True):
    model = Workpaper.model_validate(w)
    computed = {c['id']: c for c in evaluate(model)['calculations']}
    facts = {f['id']: f for f in w['facts']}
    calculations = {c['id']: c for c in w['calculations']}
    snapshot = {}
    overrides = overrides or {}

    def amount(ref):
        rec = facts.get(ref) or calculations[ref]
        raw = facts[ref]['value'] if ref in facts else computed[ref]['normalized']
        if ref in facts:
            value = D(str(overrides.get(ref, raw))) * D(rec['context']['scale'])
        else:
            value = D(raw)
        snapshot[ref] = dict(record=rec, normalized=str(value), override=str(overrides[ref]) if ref in overrides else None)
        return value / D('1000000') if rec['context']['measure'] == 'money' and rec['context'].get('physical_unit') != 'per_share' else value

    def a(key): return amount('fwd_' + key)
    def mid(key): return (a(key + '_low') + a(key + '_high')) / 2

    q_cfo = amount('C_sp_q1_cfo_2026')
    e26 = mid('guide_e')
    cap = mid('guide_cap_disc') + mid('guide_cap_sustain')
    cap_remaining = cap + a('capex_q1')
    prepaid = mid('guide_prepaid')
    annual_sl = mid('guide_sl_rev')
    annual_sl_cost = mid('guide_sl_cost')
    amort_prepaid = mid('guide_prepaid_amort')
    cash_i_oper26 = mid('guide_gross_i') - mid('guide_cap_accrual') + a('cash_i_delta26')
    quarter_restruct = amount('sp_restruct26_payment') + amount('sp_restruct_old_payment')
    annual_cash_operating = e26 - annual_sl - amort_prepaid + annual_sl_cost - a('restruct_cash26') + prepaid
    quarter_cash_operating_proxy = a('company_e_q1') - a('sl_rev_q1') - a('prepaid_amort_q1') + a('sl_cost_q1') - quarter_restruct + a('prepaid_add_q1')
    quarter_cash_model = quarter_cash_operating_proxy - a('interest_paid_net_q1') - a('cash_tax_q1') + a('cash_income_q1')
    quarter_conversion_difference = q_cfo - quarter_cash_model
    cfo_remaining = (annual_cash_operating - quarter_cash_operating_proxy - (cash_i_oper26 - a('interest_paid_net_q1'))
                     - (a('cash_tax26') - a('cash_tax_q1')) + (a('guide_interest_income') - a('cash_income_q1')) - a('other_conversion26'))
    fiber_cash_proxy = (amount('sp_q1_disc_2026') + a('do_invest_q1')) / 3
    fiber_cash = D(str(overrides.get('fiber_cash', fiber_cash_proxy)))
    dividend_remaining = a('div_per_share') * a('guide_shares') * 3
    dividend_annual = a('div_per_share') * a('guide_shares') * 4
    variable26 = a('variable26')
    ground_annual26 = a('ground_q1') + a('ground_cash_2026')
    fixed_cost26 = ground_annual26 + annual_sl_cost - a('non_ground_sl') + a('corporate_lease') - variable26
    fixed_cash_remaining = a('ground_cash_2026') - variable26 * D('.75') + a('corporate_lease') * D('.75')
    recurring_cash_e26 = annual_cash_operating - prepaid + a('restruct_cash26')
    billings26 = mid('guide_site_rev') - amort_prepaid - annual_sl - a('site_other')
    non_ground_base = billings26 + a('site_other') + a('service_gp') - ground_annual26 - recurring_cash_e26
    opening_cash = amount('q_cash')
    principal = a('face_q1')
    ol = amount('C_fwd_ol_q1')
    aro = amount('sp_aro_end')
    unamort = a('unamort_q1')
    cumulative_new_draw = D(0)
    rate = a('new_draw_rate')
    floor = a('cash_floor')
    commit = amount('C_newnetLC') - a('cp_reserve')
    lease_rate = amount('sp_lease_rate')
    new_restruct_liability = amount('sp_restruct26_liability')
    old_restruct_liability = amount('sp_restruct_old_liability')
    path = {}
    for year in [2026, 2027, 2028]:
        fraction = D('.75') if year == 2026 else D(1)
        k = rate * fraction / 2
        if year == 2026:
            cash_i_oper = cash_i_oper26
            cap_cash = a('cap_cash')
            cap_accrual = mid('guide_cap_accrual')
            gross_accrual = mid('guide_gross_i')
            amort_i = mid('guide_amort_i')
            gaap_tax = mid('guide_tax')
            cash_tax = a('cash_tax26')
            income_cash = a('guide_interest_income')
            cash_cfo = cfo_remaining
            expense_restruct = mid('guide_restruct')
            ppa = mid('guide_ppa')
            fixed_cost = fixed_cost26
            credit_e = e26 - expense_restruct - ppa + fixed_cost
            company_e = e26
            dda, sbc, imp = mid('guide_dda'), mid('guide_sbc'), mid('guide_imp')
            other_expense = mid('guide_other')
            revenue = mid('guide_site_rev') + a('service_revenue')
            cap_window = cap_remaining
            dividends = dividend_remaining
            buybacks = amount('plan_buyback')
            principal_paid = amount('debtrepaid') + amount('plan_cp') + amount('plan_otherdebt') + 3 * a('principal_q1')
            refinance_paid = refinance_new = D(0)
            cash_sources = amount('C_saleproceeds') - amount('costpaid') - a('closing_extra_cost') + fiber_cash + a('april_net_finance')
            principal += a('april_net_finance')
            ol_cash, ol_add = fixed_cash_remaining, a('lease_add26')
            old_restruct_paid = a('old_restruct_cash26')-amount('sp_restruct_old_payment')
            new_restruct_paid = a('restruct_cash26')-a('old_restruct_cash26')-amount('sp_restruct26_payment')
            new_restruct_liability += expense_restruct-amount('sp_restruct26_expense')-new_restruct_paid
            old_restruct_liability -= old_restruct_paid
            writeoff = a('debt_writeoff26')
            amort_window = amort_i - a('amort_i_q1')
            aro += amount('sp_aro_accretion') - amount('sp_aro_settled') + a('aro_new26')
            operating_loss = refinance_extra = D(0)
        else:
            idx = year - 2026
            growth = (1 + a('growth')) ** idx
            recurring_bill = a(f'contract_bill_{year}') + (a('new_leasing') - a('normal_churn')) * (D(1) if year == 2027 else D(2) + a('escalator'))
            amort_prepaid_y, sl_y = a(f'contract_prepaid_{year}'), a(f'contract_sl_{year}')
            ground_y, ground_sl = a(f'ground_cash_{year}'), a(f'ground_sl_{year}')
            variable = variable26 * growth
            fixed_cost = ground_y + ground_sl + a('corporate_lease') - variable
            cash_e = recurring_bill + a('site_other') + a('service_gp') - non_ground_base * growth - ground_y
            expense_restruct = a('new_restruct_expense' + str(year))
            ppa = a('ppa' + str(year))
            company_e = cash_e + amort_prepaid_y + sl_y - ground_sl - a('non_ground_sl')
            credit_e = company_e - expense_restruct - ppa + fixed_cost
            principal_paid = 4 * a('principal_q1')
            legacy_average_principal = principal - cumulative_new_draw - principal_paid / 2
            gross_accrual = legacy_average_principal * a('legacy_rate' + str(year))
            cap_accrual = a('cap_accrual' + str(year))
            cash_i_oper = gross_accrual - cap_accrual + a('cash_i_delta' + str(year))
            cap_cash, amort_i = a('cap_cash' + str(year)), a('amort_i' + str(year))
            cash_tax, gaap_tax, income_cash = a('cash_tax' + str(year)), a('gaap_tax' + str(year)), a('income_cash' + str(year))
            dda, sbc, imp = a('dda' + str(year)), a('sbc' + str(year)), a('imp' + str(year))
            other_expense = a('other_pnl' + str(year))
            cash_cfo = cash_e + prepaid - a('cash_restruct' + str(year)) - cash_i_oper - cash_tax + income_cash - a('other_conversion' + str(year))
            revenue = recurring_bill + amort_prepaid_y + sl_y + a('site_other') + a('service_revenue')
            cap_window, dividends, buybacks = cap, dividend_annual, a('buyback' + str(year))
            refinance_paid = refinance_new = a('refi' + str(year))
            cash_sources = D(0)
            ol_cash, ol_add = ground_y - variable + a('corporate_lease'), a('lease_add_future')
            new_restruct_liability += expense_restruct
            new_restruct_paid = min(new_restruct_liability,a('cash_restruct'+str(year)))
            old_restruct_paid = a('cash_restruct'+str(year))-new_restruct_paid
            new_restruct_liability -= new_restruct_paid
            old_restruct_liability -= old_restruct_paid
            writeoff, amort_window = a('unamort_writeoff' + str(year)), amort_i
            aro += amount('sp_aro_accretion') - amount('sp_aro_settled')
            operating_loss = a('loss27') if joint and year == 2027 else (a('loss28') + a('att_2028') * a('att_loss') * a('att_fraction')) if joint else D(0)
            refinance_extra = a('refi_exposure2027') * a('spread27') if joint and year == 2027 else (a('refi2027') * a('spread27') + a('refi_exposure2028') * a('spread28')) if joint else D(0)
        opening_extra_i = cumulative_new_draw * rate * fraction
        cash_cfo -= operating_loss + refinance_extra + opening_extra_i
        raw_cash = opening_cash + cash_cfo + cash_sources - cap_window - dividends - buybacks - principal_paid - refinance_paid + refinance_new
        desired_draw = max((floor - raw_cash) / (1 - k), D(0))
        available = max(commit - cumulative_new_draw, D(0)) if facility else D(0)
        draw = min(desired_draw, available)
        new_draw_i = draw * k
        cash_cfo -= new_draw_i
        end_cash = raw_cash + draw - new_draw_i
        principal = principal - principal_paid - refinance_paid + refinance_new + draw
        cumulative_new_draw += draw
        unamort -= amort_window + writeoff
        carrying = principal - unamort
        old_restruct_lease_cash = old_restruct_paid*a('old_restruct_lease_in_ol')
        lease_end = (ol * (1 + lease_rate * fraction / 2) - ol_cash - old_restruct_lease_cash + ol_add) / (1 - lease_rate * fraction / 2)
        lease_i_window = (ol + lease_end) / 2 * lease_rate * fraction
        lease_i = lease_i_window + (amount('C_sp_lease_end') + ol) / 2 * lease_rate / 4 if year == 2026 else lease_i_window
        ol = lease_end
        extra_i = refinance_extra + opening_extra_i + new_draw_i
        annual_cfo = cash_cfo + q_cfo if year == 2026 else cash_cfo
        credit_e -= operating_loss
        gross_cash_i = cash_i_oper + cap_cash + extra_i
        credit_ffo = credit_e - gross_cash_i - lease_i - cash_tax
        credit_cfo = annual_cfo + fixed_cost - lease_i - cap_cash
        credit_capex = cap - cap_cash
        net_debt = carrying + ol + aro - a('aro_net_offset') + a('credit_debt_delta') - end_cash
        ebit = credit_e - fixed_cost - dda - sbc - imp
        adjusted_dda = dda - amount('sp_aro_accretion') + fixed_cost - lease_i
        adjusted_ebit = credit_e - adjusted_dda
        net_accrual_i = gross_accrual + amort_i - cap_accrual + extra_i
        adjusted_accrual_i = net_accrual_i + cap_accrual + lease_i + amount('sp_aro_accretion')
        ni = ebit - net_accrual_i + income_cash - gaap_tax - other_expense
        shortfall = (desired_draw - draw) * (1-k)
        path[str(year)] = dict(year=year, status='conditional_analysis' if shortfall==0 else 'unfunded_budget_not_projected' if end_cash<0 else 'cash_floor_not_met_reference', revenue=revenue, company_adjusted_ebitda_proxy=company_e-operating_loss,
            EBITDA=credit_e, GAAP_operating_income=ebit, adjusted_EBIT=adjusted_ebit, adjusted_DAA=adjusted_dda, NI_cont_proxy=ni,
            gross_cash_interest=gross_cash_i, operating_cash_interest=cash_i_oper+extra_i,adjusted_accrual_interest=adjusted_accrual_i,
            capitalized_cash_interest=cap_cash, net_accrual_interest=net_accrual_i, CFO=annual_cfo, CFO_window=cash_cfo,
            economic_CFO_after_all_cash_interest=annual_cfo-cap_cash,economic_capex_after_interest_transfer=cap-cap_cash,
            capex_gaap=cap, cash_dividends=dividends-a('div_q1') if year==2026 else dividends,
            repurchases=buybacks-a('buy_q1') if year==2026 else buybacks, cash=end_cash, cash_before_new_draw=raw_cash,
            new_draw=draw, required_draw=desired_draw, finance_shortfall=shortfall,
            cash_payment_deficit=max(-end_cash,D(0)),cash_floor_additional_reserve_gap=max(floor-max(end_cash,D(0)),D(0)),
            facility_nominal_available_before_draw=available, cumulative_new_draw=cumulative_new_draw,
            financial_principal=principal, financial_carrying_proxy=carrying, unamortized_proxy=unamort,
            operating_lease=ol, fixed_lease_cash_window=ol_cash, fixed_lease_cost_proxy=fixed_cost, lease_interest_proxy=lease_i,
            new_restruct_payment_window=new_restruct_paid,old_restruct_payment_window=old_restruct_paid,
            new_restruct_liability=new_restruct_liability,old_restruct_liability=old_restruct_liability,old_restruct_cash_mapped_to_OL=old_restruct_lease_cash,
            ARO_gross=aro, net_debt=net_debt, FFO=credit_ffo, adjusted_CFO=credit_cfo, adjusted_capex=credit_capex,
            FOCF=credit_cfo-credit_capex, DCF=credit_cfo-credit_capex-(dividends-a('div_q1') if year==2026 else dividends)-(buybacks-a('buy_q1') if year==2026 else buybacks),
            debt_EBITDA=net_debt/credit_e, FFO_debt=credit_ffo/net_debt, principal_maturities_paid=refinance_paid,
            CFO_debt=credit_cfo/net_debt,FOCF_debt=(credit_cfo-credit_capex)/net_debt,
            DCF_debt=(credit_cfo-credit_capex-(dividends-a('div_q1') if year==2026 else dividends)-(buybacks-a('buy_q1') if year==2026 else buybacks))/net_debt,
            EBITDA_interest_coverage=credit_e/adjusted_accrual_i,FFO_cash_interest_coverage=(credit_ffo+gross_cash_i+lease_i)/(gross_cash_i+lease_i),
            assumed_refinance_inflow=refinance_new, extra_financing_interest=extra_i, operating_loss=operating_loss,
            base_gross_accrual_interest=gross_accrual,refinance_incremental_interest=refinance_extra,
            simple_principal_cash_required_EBITDA_at7x=(principal-end_cash)/amount('newlimit'),
            simple_principal_cash_EBITDA_to_survive_10pct_decline=(principal-end_cash)/D('6.3'),
            simple_principal_cash_EBITDA_to_survive_15pct_decline=(principal-end_cash)/D('5.95'),
            covenant_numerator_formula='Financial principal−ordinarycash + unknown TotalIndebtedness scope delta − unknown UnrestrictedCash scope delta. Reference thresholds are not actual covenant EBITDA or certified capacity.',
            cash_identity_residual=end_cash-(opening_cash+cash_cfo+cash_sources-cap_window-dividends-buybacks-principal_paid-refinance_paid+refinance_new+draw))
        if end_cash < 0:
            path[str(year)]['unfunded_cash_arithmetic'] = end_cash
            path[str(year)]['not_projected_reason'] = 'All scheduled assumed cash uses cannot be paid with the permitted funding. Negative arithmetic is a funding deficit, not an asset. Later years are not projected.'
            for key in ['cash','financial_principal','financial_carrying_proxy','unamortized_proxy','net_debt','FFO','adjusted_CFO','FOCF','DCF','debt_EBITDA','FFO_debt','CFO_debt','FOCF_debt','DCF_debt','EBITDA_interest_coverage','FFO_cash_interest_coverage','simple_principal_cash_required_EBITDA_at7x','simple_principal_cash_EBITDA_to_survive_10pct_decline','simple_principal_cash_EBITDA_to_survive_15pct_decline']:
                path[str(year)][key] = None
            break
        if overrides.get('fwd_old_restruct_lease_in_ol') == 1:
            path[str(year)]['status'] = 'OL_balance_mapping_sensitivity_method_not_formed'
            for key in ['FFO','adjusted_CFO','adjusted_capex','FOCF','DCF','debt_EBITDA','FFO_debt','CFO_debt','FOCF_debt','DCF_debt','EBITDA_interest_coverage','FFO_cash_interest_coverage']:
                path[str(year)][key] = None
            path[str(year)]['method_not_formed_reason'] = 'Hypothetical old-office cash reduces reported OL; the corresponding current lease expense/credit CFO depreciation allocation is unverified. Only cash budget and conditional OL balance are shown.'
        opening_cash = end_cash
    reverse = {}
    for y,x in path.items():
        if x['status'] != 'conditional_analysis': continue
        k = rate * (D('.75') if y=='2026' else D(1)) / 2
        headroom = x['cash_before_new_draw']-floor
        reverse[y] = dict(cash_without_new_funding_margin=headroom,
            additional_loss_to_nominal_facility_exhaustion=max(x['facility_nominal_available_before_draw']*(1-k)+x['cash_before_new_draw']-floor,D(0)),
            scope='Year-local change in operating cash and EBITDA, unchanged opening balances and other assumptions; signed loss<0 means required improvement. No grade or PD boundary. Facility remains conditional.')
        for target in [D('.12'),D('.09')]:
            margin = x['FFO']-target*x['net_debt']
            if headroom < 0:
                funded = margin*(1-k)/(1+target)
                bound = funded if funded >= headroom else headroom+(margin-(1+target)*headroom/(1-k))/(1+target)
            else:
                unborrowed = margin/(1+target)
                bound = unborrowed if unborrowed <= headroom else headroom+(margin-(1+target)*headroom)*(1-k)/(1+target)
            reverse[y][f'signed_operating_cash_loss_to_FFO_debt_{target}'] = bound
            reverse[y][f'already_below_FFO_debt_{target}'] = margin<0
        for target in [D('5.0'),D('5.5')]:
            reduction = x['net_debt']-target*x['EBITDA']
            funded = reduction/(target+1/(1-k))
            improvement = funded if headroom<0 and funded<=-headroom else (reduction-k*x['new_draw'])/(1+target)
            reverse[y][f'net_debt_reduction_at_fixed_EBITDA_to_{target}x'] = reduction
            reverse[y][f'operating_cash_EBITDA_improvement_to_{target}x'] = improvement
    shared_sga_proxy = (a('sga_q1')-a('sbc_q1'))*4
    attribution = {}
    for y,x in path.items():
        shared = shared_sga_proxy*(1+a('growth'))**(int(y)-2026)
        tax = a('cash_tax26') if y=='2026' else a('cash_tax'+y)
        conversion = a('other_conversion26') if y=='2026' else a('other_conversion'+y)
        if y=='2026': conversion -= quarter_conversion_difference
        restructuring = a('restruct_cash26') if y=='2026' else a('cash_restruct'+y)
        inc = a('guide_interest_income') if y=='2026' else a('income_cash'+y)
        economic_cfo=x['economic_CFO_after_all_cash_interest']
        burden = shared + tax + x['gross_cash_interest'] + conversion + restructuring - inc
        service_weight = a('service_revenue') / x['revenue']
        services = a('service_gp') - service_weight * burden
        attribution[y] = dict(total_economic_operating_CFO_after_all_lease_cash=economic_cfo,GAAP_classification_CFO_reference=x['CFO'],capitalized_cash_interest_transfer=x['capitalized_cash_interest'],
            shared_cash_SGA_proxy=shared,cash_tax=tax,operating_cash_interest=x['operating_cash_interest'],
            total_financial_cash_interest=x['gross_cash_interest'],other_cash_conversion_including_WC_proxy=conversion,services_cash_gross_profit_proxy=a('service_gp'),
            pro_rata_service_weight=service_weight,services_attributable_CFO_reference=services,
            rental_attributable_CFO_reference=economic_cfo-services,rental_share_reference=(economic_cfo-services)/economic_cfo,
            rental_share_if_all_shared_burden_allocated_rental=(economic_cfo-a('service_gp'))/economic_cfo,
            unallocated_services_cash_delta_to_90pct_boundary=D('.1')*economic_cfo-a('service_gp'),
            unallocated_services_cash_delta_to_two_thirds_boundary=economic_cfo/3-a('service_gp'),
            formula='Services CFO = service cash GP105 + unknown services cash delta −lambda(shared cashSGA+cash tax+total financial cash interest+other cash conversion+restructcash−interest received); rental CFO=economic total−services. Economic total deducts capitalized cash interest but never adds lease principal; CAP is reduced by the same interest classification transfer. Reference lambda=services revenue/total revenue; lambda and unknown cash attribution are unverified.',
            limitation='No disclosed segment CFO split. All Q1 SBC is assumed to reduce shared SG&A cash; the expense location is unverified. Neither revenue ratio nor GP ratio is used as predictable CFO. Positive contractual CFO/predictability, counterparty and renewal enforceability remain separate conditions. Cash conversion allocation and any future payment gap remain conditions.')
    known_cash = amount('q_cash')+amount('C_saleproceeds')-amount('costpaid')-amount('debtrepaid')
    known_principal = a('face_q1')-amount('debtrepaid')
    quarter_oper_accrual = a('gross_accrual_q1')-a('cap_accrual_q1')
    quarter_accrued_decrease = a('accrued_interest_begin')-a('accrued_interest_end')
    bridge = dict(Q1_actual_CFO=q_cfo, Q1_cash_conversion_proxy=quarter_cash_model,Q1_actual_minus_proxy=quarter_conversion_difference,
        Q1_operating_interest_accrual=quarter_oper_accrual,Q1_accrued_interest_liability_decrease=quarter_accrued_decrease,
        Q1_operating_cash_interest_from_simple_accrual_bridge=quarter_oper_accrual+quarter_accrued_decrease,
        Q1_interest_conversion_unexplained_residual=a('interest_paid_net_q1')-quarter_oper_accrual-quarter_accrued_decrease,
        remaining_2026_CFO_before_additional_draw_interest=cfo_remaining, remaining_2026_capex=cap_remaining,
        remaining_2026_dividend_proxy=dividend_remaining, April_Fiber_cash_proxy=fiber_cash,
        annual_operating_cash_interest26=cash_i_oper26,remaining_operating_cash_interest26=cash_i_oper26-a('interest_paid_net_q1'),
        capitalized_cash_q1_proxy=a('cap_cash_q1'),remaining_capitalized_cash_proxy=a('cap_cash')-a('cap_cash_q1'),
        disclosed_face_difference_10q_vs_supplement=a('cash_obligations_10q')-a('face_q1'),
        disclosed_10q_unamortized=a('unamort_10q'),supplement_unamortized=a('unamort_q1'),
        company_FFO_guidance_midpoint=mid('guide_ffo'),company_AFFO_guidance_midpoint=mid('guide_affo'),
        company_net_interest_guidance_midpoint=mid('guide_net_i'),sum_separately_selected_interest_components=mid('guide_gross_i')+mid('guide_amort_i')-mid('guide_cap_accrual'),
        company_net_income_midpoint=mid('guide_ni'),company_discontinued_net_income_midpoint=mid('guide_do'),company_continuing_NI_by_separate_midpoints=mid('guide_ni')-mid('guide_do'),
        company_services_margin_guidance_midpoint=mid('guide_service_margin'),
        disclosed_fixed_maturity2027=a('fixed_maturity2027'),disclosed_fixed_maturity2028=a('fixed_maturity2028'),disclosed_anticipated_repayment2028=a('anticipated2028'),
        remaining_contract_billings26=a('contract_bill_2026'),remaining_contract_prepaid_amort26=a('contract_prepaid_2026'),remaining_contract_SL26=a('contract_sl_2026'),remaining_ground_SL26=a('ground_sl_2026'),total_renewal_exposure2028=a('renew_2028'),
        may1_cash_known_actions=known_cash,
        may1_cash_actual=None,may1_cash_algebra=f'{known_cash} + April Towers net cash + April Fiber parent-attributable net cash + April financing/other; these April inputs are not disclosed',
        may1_principal_known_actions=known_principal,may1_debt_actual=None,
        may1_principal_algebra=f'{known_principal} + April net borrowing/repayment;3300 is approximately reported repayment',
        june_cash_actual=None,June_cash_algebra='last actual55 + Apr-Jun retained CFO + Fiber attributable cash +8376−74−other costs−capex−dividends−buyback−executed principal+new financing; no unique June cash inferred',
        non_ground_cash_cost_calibration=non_ground_base,
        cash_interest_conversion='Annual operating cash = gross debt accrual expense − accrual capitalized interest + explicit operating-payment timing delta; gross cash = operating cash + separately assumed capitalized cash. Net P&L expense adds amortization; it is not cash.')
    rolling=dict(start='2026-07-01',end='2027-06-30',status='not_projected' if '2027' not in path else 'conditional_timing_reference',opening_ordinary_cash=None,
        formula='CFO_window=(CFO26−actualQ1CFO296)×h26+CFO27×h27. h26/h27 are unverified timing shares; reference2/3,1/2. June ordinary cash J is unknown.',
        sources_formula='J + window_CFO + qualified committed facility availability + independent committed refinancing; market refinancing assumptions are not automatically liquidity sources. Do not count the same RCF once as availability and again as refinance inflow.',
        uses_formula='window_capex + window_dividends + JuneCPprincipal + unrepaidJuly2026bond + unrepaidMarch2027bonds + routineprincipal + optionalrepayments + postJunebuybacks + unpaidcosts. 2100 plan portion must reconcile mandatory bonds and optional debt, not be added twice.',
        debt_execution_parameters='Mandatory fixed calendar1000+1250 only if not already redeemed. Additional2100 plan afterJune is2100−DpaidJune, with any July1000 included there rather than twice; March1250 paid/inflow-refinanced cancels in annual budget but still needs a genuine committed liquidity source. CPJune,JuneRCFdraw,buybacksJune andcostsJune remain unknown.',
        facility_limit='Total pool=4460.6−June existingdraw−LCchanges, conditionally. Cash-budget free pool subtracts CP reserve100; if CP cash payment is in liquidity uses, admit the matching qualified reserved backup source or admit the full pool once. Do not both subtract reserved CP and claim complete sources after again charging all CP. A draw kept as unrestricted cash or used to repay existing financial principal does not by itself increase net debt. Spending cash and draw-interest do. NoDefault and quarter-end net/secured covenants remain independent conditions.',
        covenant_10pct_decline_boundary='Actual (TotalIndebtedness−UnrestrictedCash)/6.3',covenant_15pct_decline_headroom_boundary='Actual (TotalIndebtedness−UnrestrictedCash)/5.95')
    if '2027' in path:
        rolling.update(window_CFO=(path['2026']['CFO']-q_cfo)*a('window_weight26')+path['2027']['CFO']*a('window_weight27'),
            window_capex=cap_remaining*a('window_weight26')+cap*a('window_weight27'),window_dividends=dividend_annual,
            fixed_maturities_if_not_prepaid=a('maturity_H226')+a('maturity_H127'),routine_principal_proxy=4*a('principal_q1'),
            weighted_method_EBITDA_reference=(path['2026']['EBITDA']+path['2027']['EBITDA'])/2,
            cash_loss_if_weighted_method_EBITDA_declines_15pct=(path['2026']['EBITDA']+path['2027']['EBITDA'])/2*D('.15'),
            cash_loss_conversion='One dollar EBITDA decline becomes one dollar CFO loss before additional financing interest, with no tax or cost mitigation; transparent stress assumption, not a fixed methodology algorithm.')
        capitalized_transfer=(a('cap_cash')-a('cap_cash_q1'))*a('window_weight26')+a('cap_cash2027')*a('window_weight27')
        rolling.update(window_capitalized_cash_interest_transfer=capitalized_transfer,window_economic_CFO=rolling['window_CFO']-capitalized_transfer,window_economic_capex=rolling['window_capex']-capitalized_transfer,
            classification_pairing='Use GAAP-reference CFO and gross CAP, or economic CFO and CAP excluding the same capitalized interest transfer. Do not pair economic CFO with gross CAP or lease-adjusted method CFO with actual cash uses.')
    if '2028' in path and path['2028']['cash'] is not None:
        rolling.update(nominal_pool_left_after_base_funding_and_2027_bond_refi=commit-path['2027']['cumulative_new_draw']-a('refi2027'),
            nominal_pool_shortfall_if_all_2027_2028_bond_refi_uses_same_RCF=max(a('refi2027')+a('refi2028')+path['2028']['cumulative_new_draw']-commit,D(0)),
            pool_stress_scope='Necessary principal-only capacity condition under the displayed cash budget and no RCF retirement; higher bank replacement interest and changed cash timing are not modeled here. This is not a complete no-market cash forecast or Default conclusion.')
    for ref,record in facts.items():
        if ref.startswith('fwd_') and record['state']=='missing': snapshot[ref]=dict(record=record,normalized=None,override=None)
    return dict(input_snapshot=snapshot,path=path,reverse=reverse,bridge=bridge,operating_CFO_attribution=attribution,rolling_liquidity_interface=rolling,scenario_controls=dict(overrides=overrides,joint_stress=joint,new_facility_assumed_available=facility))


def rebuild(w):
    scenarios = dict(base=run(w),joint_stress=run(w,joint=True),
        cash_unknowns_adverse=run(w,{'fwd_closing_extra_cost':150,'fiber_cash':-150,'fwd_other_conversion26':250,'fwd_cash_i_delta26':100}),
        capitalized_cash15=run(w,{'fwd_cap_cash':15}),no_new_facility=run(w,facility=False),old_restruct_lease_mapping1=run(w,{'fwd_old_restruct_lease_in_ol':1}))
    rows, figures = [], []
    entity=w['mandate']['entity']
    for scenario,r in scenarios.items():
        for year,metrics in r['path'].items():
            for key in ['CFO','economic_CFO_after_all_cash_interest','cash','financial_principal','financial_carrying_proxy','operating_lease','EBITDA','NI_cont_proxy','FFO','FOCF','DCF','new_draw','finance_shortfall','cash_payment_deficit','FFO_debt','debt_EBITDA','simple_principal_cash_required_EBITDA_at7x','simple_principal_cash_EBITDA_to_survive_10pct_decline','simple_principal_cash_EBITDA_to_survive_15pct_decline']:
                i=len(rows)
                rows.append(dict(scenario=scenario,year=year,metric=key,result=None if metrics[key] is None else str(metrics[key]),status=metrics['status'],formula='See executable crown_forward.run and artifact full path; same-ID input snapshot retained'))
                selected=(scenario in ['base','joint_stress'] and key in ['CFO','economic_CFO_after_all_cash_interest','cash','financial_principal','financial_carrying_proxy','operating_lease','EBITDA','FFO','FFO_debt','debt_EBITDA','new_draw']) or (scenario=='cash_unknowns_adverse' and year=='2026' and key in ['CFO','FFO_debt','new_draw']) or (scenario=='capitalized_cash15' and year=='2026' and key in ['FFO','FOCF']) or (scenario=='no_new_facility' and key in ['CFO','finance_shortfall','cash_payment_deficit'])
                selected=selected or (scenario=='base' and key.startswith('simple_principal_cash_'))
                if not selected or metrics[key] is None: continue
                ratio=key in ['FFO_debt','debt_EBITDA']
                instant=key in ['cash','financial_principal','financial_carrying_proxy','operating_lease','finance_shortfall','cash_payment_deficit']
                figures.append(dict(id=f'fwd_{scenario}_{key}_{year}',label=f'{scenario} {year} {key}',row=i,field='result',context=dict(entity=entity,scope='post_sale_towers_analysis',start=None if instant else year+'-01-01',end=year+'-12-31',aggregation='ratio' if ratio else 'instant' if instant else 'flow',basis='Explicit Crown forward US GAAP / S&P-method analytical bridge',measure='ratio' if ratio else 'money',currency=None if ratio else 'USD',scale='1' if ratio else '1000000',physical_unit='times' if key=='debt_EBITDA' else None)))
        if scenario in ['base','joint_stress']:
            for key in ['window_CFO','window_capex','window_economic_CFO','window_economic_capex','window_dividends','fixed_maturities_if_not_prepaid','routine_principal_proxy','cash_loss_if_weighted_method_EBITDA_declines_15pct']:
                i=len(rows)
                rows.append(dict(scenario=scenario,year='rolling12m',metric=key,result=str(r['rolling_liquidity_interface'][key]),status='conditional_timing_reference',formula=r['rolling_liquidity_interface']['formula']))
                figures.append(dict(id=f'fwd_{scenario}_{key}_rolling12m',label=f'{scenario} Jul2026-Jun2027 {key}',row=i,field='result',context=dict(entity=entity,scope='post_sale_towers_analysis',start='2026-07-01',end='2027-06-30',aggregation='flow',basis='Explicit unknown-June-cash and uniform-cash-timing reference',measure='money',currency='USD',scale='1000000',physical_unit=None)))
        if scenario=='base':
            for year in ['2026','2027']:
                for key in ['services_attributable_CFO_reference','rental_attributable_CFO_reference','rental_share_reference']:
                    i=len(rows)
                    a=r['operating_CFO_attribution'][year]
                    rows.append(dict(scenario=scenario,year=year,metric=key,result=str(a[key]),status='conditional_cash_attribution_reference',formula=a['formula']))
                    ratio=key=='rental_share_reference'
                    figures.append(dict(id=f'fwd_base_{key}_{year}',label=f'{year} {key}',row=i,field='result',context=dict(entity=entity,scope='post_sale_towers_analysis',start=year+'-01-01',end=year+'-12-31',aggregation='ratio' if ratio else 'flow',basis='Economic operating CFO; unknown cash attribution and explicit shared cost allocation',measure='ratio' if ratio else 'money',currency=None if ratio else 'USD',scale='1' if ratio else '1000000',physical_unit=None)))
    refs=sorted(set().union(*(r['input_snapshot'] for r in scenarios.values())))
    q=dict(id='Q_crown_forward',label='Crown公开信息约束的售后前瞻现金及信用指标',method='crown_post_sale_forward_cash_credit_v1',as_of='2026-06-30',input_refs=refs,evidence=[e['id'] for e in w['evidence'] if e['id'].startswith('E_FWD_')]+['EQ126SALE','EQ126FAC','E_SP_RATIOS','E_SP_SCOPE','E_SP_ARO'],
       assumptions=['公司区间取中点只是研究输入；gross应计到operating现金及capitalized现金分别转换。',
        'Q1现金税采用公司LQA净付退税横线所对应披露精度0的季度参照，不证明毛额或未舍入值为零；全年现金税15仍为独立假设，剩余期税款及季度转换残差分别重算。',
        '2026其他现金转换净流出100、未来100、53追加交易费、退出Fiber季度净流量月均代理是明确情景，不是已知付款或真实June余额。',
        '计划1800/2100/1000在2026执行；2027/28到期分别等额融资。新额度可用、CP占用100及50现金数学阈值都是条件；未独立核合规证书。',
        '留存本金利息由期初金融本金扣累计新增额度及年度例行本金平均还款，乘2027/28组合利率4%/4.2%；组合和逐券计划未知。再融资压力为额外200bp：按到期月末至年末暴露1187.5/2212.5及前期2250全年续息，不是公司利息指引。',
        '未来普通股支付按1.0625每季、429百万股代理；未来新融资利息按5.5%，平均新增余额计；cash资本化改变时保持operating现金独立以免分类创造现金。',
        '公司新重组expense30与总cash30分别处理：FY26新付26/旧付4，FY27新4/旧6，FY28旧2，旧余额4留至2029–2033。新计划2027结清仅为建模假设，原文只明确员工减员付款；旧12全留存也是假设。旧闭店付款排除普通corporate租金2。旧付款是否减少OL采用报表分类一致的覆盖份额0参照及1余额端点；端点租赁费用/方法CFO未配套，不发布其方法FFO/比率，现金不再扣一次。',
        '未来其他P&L费用和新增回购参照为0，不断言实际为0；现金转换残差与ARO结算在CFO中不重复。'],
       limitations=['公开信息及明确假设形成的研究情景，不是公司预算或S&P已发表指标。',
        'May1、June实际余额未知，以null和代数式保留；年度现金不覆盖月中缺口。',
        '租赁固定/可变拆分、新增和现金时差均有假设；ARO仍采用未抵减主情景，不证明税益或专款为0。',
        '未摊销退出调整、会计/本金及契约范围需继续核数；7x所需EBITDA仅参数界限，不是遵约比率。',
        '12%与5.0x作为standard条件主界限；9%/5.5x仅为medial条件辅助。low表分界不同，未形成其完整路径。同定义指标界限不是PD、等级或完整FRP；核心指标冲突及转型权重另形成。'],
       artifact=dict(input_snapshot=scenarios['base']['input_snapshot'],scenarios=scenarios,rows=rows,execution='Actual Decimal execution reading shared facts/calculations IDs; no stored result substituted for computation',units='USD millions; ratio decimal; leverage times',script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),benchmark_conditions=dict(source_id='S_DEV_CORP',sha256='641c89f41dac7f914dbda629b4c81da95986574ce51f51538524fcd53d0276ce',actually_read_physical_pages=[33,34],standard_table17=dict(FFO_debt_boundary='.12',debt_EBITDA_boundary='5.0'),medial_table18=dict(FFO_debt_boundary='.09',debt_EBITDA_boundary='5.5'),applicability='Conditional benchmark choices only; issuer table/CICRA/sector selection belongs to the separately formed rating chain.')),figures=figures)
    return q


def main():
    parser=argparse.ArgumentParser(description='Crown-specific public-information forward cash/credit scenario')
    parser.add_argument('--workpaper',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    w=json.loads(args.workpaper.read_text(encoding='utf-8-sig'))
    q=rebuild(w)
    index=next((i for i,old in enumerate(w['quantitative']) if old['id']==q['id']),len(w['quantitative']))
    w['quantitative'][index:index+1]=[q]
    Workpaper.model_validate(w)
    args.output.write_text(json.dumps(w,ensure_ascii=False,indent=2,default=str),encoding='utf-8')


if __name__=='__main__':main()
