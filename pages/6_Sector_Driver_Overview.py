#%%
"""
Sector & Sub-Sector Earnings Driver Overview
Dynamic big-picture view of what drives growth: Revenue vs Cost vs Non-Recurring

Design goals:
- No fixed fallbacks tied to years; all period choices are data-driven
- Vectorized aggregations (groupby/agg, pivot) without row loops
- Jupyter-style #%% cell for interactive workflows
"""

import os
import sys
from typing import List
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# Page config must be first Streamlit command
st.set_page_config(page_title="Sector Driver Overview", page_icon="📈", layout="wide")

# Project root and imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

try:
    from utilities.style_utils import apply_google_font
    from utilities.sidebar_style import apply_sidebar_style
    apply_google_font()
    apply_sidebar_style()
except Exception:
    pass


@st.cache_data
def load_driver_data():
    try:
        q = pd.read_parquet(os.path.join(project_root, 'Data/earnings_quality_quarterly.parquet'))
        y = pd.read_parquet(os.path.join(project_root, 'Data/earnings_quality_yearly.parquet'))
        return q, y
    except Exception as e:
        return None, None


def _suffix_for(label: str) -> str:
    if "QoQ" in label:
        return "_QoQ"
    if "YoY" in label:
        return "_YoY"
    return "_T12M"  # default


def _available_numeric_weights(columns: List[str]) -> List[str]:
    """Suggest potential weight columns if present."""
    candidates = [
        'TOI', 'PBT', 'NPATMI', 'Total Assets', 'Total Assets_YoY', 'TOI_T12M', 'PBT_T12M'
    ]
    return [c for c in candidates if c in columns]


def _dominant_driver_row(row: pd.Series, rev_col: str, cost_col: str, nonrec_col: str) -> str:
    vals = {}
    if rev_col in row.index and pd.notna(row[rev_col]):
        vals['Revenue'] = abs(row[rev_col])
    if cost_col in row.index and pd.notna(row[cost_col]):
        vals['Cost'] = abs(row[cost_col])
    if nonrec_col in row.index and pd.notna(row[nonrec_col]):
        vals['Non-Rec'] = abs(row[nonrec_col])
    if not vals:
        return ''
    return max(vals, key=vals.get)


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    """Compute weighted median (50th percentile) for 1D arrays.
    Returns NaN if arrays are empty or total weight is zero.
    """
    try:
        mask = np.isfinite(values) & np.isfinite(weights)
        v = values[mask]
        w = weights[mask]
        if v.size == 0:
            return np.nan
        order = np.argsort(v)
        v_sorted = v[order]
        w_sorted = w[order]
        cw = np.cumsum(w_sorted)
        cutoff = 0.5 * cw[-1]
        if cw[-1] == 0:
            return np.nan
        idx = np.searchsorted(cw, cutoff, side='left')
        idx = int(min(max(idx, 0), len(v_sorted) - 1))
        return float(v_sorted[idx])
    except Exception:
        return np.nan


qdf, ydf = load_driver_data()
if qdf is None or ydf is None:
    st.error("Unable to load earnings driver Parquet files. Please run scripts/Prepare_earnings_driver.py.")
    st.stop()

st.title("Sector & Sub‑Sector Driver Overview")
st.caption("Big-picture attribution of profit growth by driver with sector and sub‑sector breakdowns")

# Cross-link back to the parent page
col_link, _ = st.columns([1, 6])
with col_link:
    try:
        st.page_link("pages/7_Earnings_Drivers.py", label="← Back to Earnings Drivers")
    except Exception:
        if st.button("← Back to Earnings Drivers"):
            try:
                st.switch_page("pages/7_Earnings_Drivers.py")
            except Exception:
                pass

with st.sidebar:
    st.header("Data Selection")
    freq = st.radio("Frequency", ["Quarterly", "Yearly"], index=0, horizontal=True)
    if freq == "Quarterly":
        comp_label = st.selectbox("Comparison", ["T12M (4Q avg)", "QoQ", "YoY"], index=0)
        suffix = _suffix_for(comp_label)
        df = qdf.copy()
        period_col = 'Date_Quarter'
    else:
        suffix = ""
        df = ydf.copy()
        period_col = 'Year'

    st.header("Aggregation Scope")
    scope = st.radio("Scope", ["Latest period", "Last N periods"], index=0, horizontal=True)
    if scope == "Last N periods":
        # derive available distinct periods
        periods_sorted = (
            pd.Series(df[period_col].dropna().unique())
            .sort_values(ascending=True)
            .tolist()
        )
        max_n = len(periods_sorted) if periods_sorted else 4
        n_periods = st.slider("Window size (periods)", min_value=2, max_value=max(2, max_n), value=min(4, max_n))
        reducer = st.selectbox("Aggregation", ["mean", "median"], index=0)
    else:
        n_periods = None
        reducer = "mean"

    st.header("Weighting (optional)")
    weight_candidates = _available_numeric_weights(df.columns)
    weight_options = ["None"] + weight_candidates + ["Total Assets (from sector data)"]
    weight_choice = st.selectbox(
        "Weight by",
        weight_options,
        index=0,
        help="Weights for Type averages; choose None for equal-weight or Total Assets from sector datasets"
    )


# Build columns
rev_col = f'Top_Line_Impact{suffix}' if suffix else 'Top_Line_Impact'
cost_col = f'Cost_Cutting_Impact{suffix}' if suffix else 'Cost_Cutting_Impact'
nonrec_col = f'Non_Recurring_Impact{suffix}' if suffix else 'Non_Recurring_Impact'
total_col = f'Total_Impact{suffix}' if suffix else 'Total_Impact'
use_cols = [c for c in [rev_col, cost_col, nonrec_col, total_col] if c in df.columns]

# Subcomponents for optional panels
nii_col = f'NII_Impact{suffix}' if suffix else 'NII_Impact'
fee_col = f'Fee_Impact{suffix}' if suffix else 'Fee_Impact'
opex_col = f'OPEX_Impact{suffix}' if suffix else 'OPEX_Impact'
prov_col = f'Provision_Impact{suffix}' if suffix else 'Provision_Impact'
loan_col = f'Loan_Impact{suffix}' if suffix else 'Loan_Impact'
nim_col = f'NIM_Impact{suffix}' if suffix else 'NIM_Impact'
sub_cols = [c for c in [nii_col, fee_col, opex_col, prov_col, loan_col, nim_col] if c in df.columns]

# Slice base
sector_agg_tickers = ['Sector', 'SOCB', 'Private_1', 'Private_2', 'Private_3']

if scope == "Latest period":
    latest_period = df[period_col].max()
    base = df[df[period_col] == latest_period][['TICKER', 'Type', period_col] + use_cols + sub_cols].copy()
    # Exclude sector aggregate rows to avoid double counting in All Banks averages
    base = base[~base['TICKER'].isin(sector_agg_tickers)]
    scope_label = f"Latest {period_col}: {latest_period}"
else:
    all_periods = (
        pd.Series(df[period_col].dropna().unique())
        .sort_values(ascending=True)
        .tolist()
    )
    window = all_periods[-n_periods:]
    base = df[df[period_col].isin(window)][['TICKER', 'Type', period_col] + use_cols + sub_cols].copy()
    base = base[~base['TICKER'].isin(sector_agg_tickers)]
    scope_label = f"Window: {window[0]} → {window[-1]} ({len(window)} periods)"

st.markdown(f"#### {scope_label}")

# Aggregation helper
def aggregate_by_type(frame: pd.DataFrame, measures: List[str], weight: str = None, reducer: str = "mean") -> pd.DataFrame:
    dfm = frame.dropna(subset=['Type'])
    if not measures:
        return pd.DataFrame()
    if weight and weight in dfm.columns:
        # Weighted average by Type: sum(value*weight)/sum(weight)
        grouped = dfm.groupby('Type', as_index=True)
        sums = grouped[measures + [weight]].apply(lambda g: pd.Series({
            m: (g[m] * g[weight]).sum() / g[weight].sum() if g[weight].sum() != 0 else np.nan for m in measures
        }))
        out = sums[measures]
    else:
        if scope == "Latest period":
            out = dfm.groupby('Type', as_index=True)[measures].mean(numeric_only=True)
        else:
            agg_func = np.median if reducer == "median" else np.mean
            out = dfm.groupby('Type', as_index=True)[measures].agg(agg_func)
    return out


# Attach weights if chosen
weight_col_name = None
if weight_choice == "Total Assets (from sector data)":
    # Load sector datasets for weights
    try:
        if freq == "Quarterly":
            wdf = pd.read_parquet(os.path.join(project_root, 'Data/dfsectorquarter.parquet'))
            w_period = 'Date_Quarter'
        else:
            wdf = pd.read_parquet(os.path.join(project_root, 'Data/dfsectoryear.parquet'))
            w_period = 'Year'
        if 'Total Assets' in wdf.columns:
            wdf2 = wdf[['TICKER', w_period, 'Total Assets']].copy()
            wdf2 = wdf2.rename(columns={w_period: period_col, 'Total Assets': 'WEIGHT_TOTAL_ASSETS'})
            base = base.merge(wdf2, on=['TICKER', period_col], how='left')
            weight_col_name = 'WEIGHT_TOTAL_ASSETS'
    except Exception:
        weight_col_name = None
elif weight_choice != "None" and weight_choice in base.columns:
    weight_col_name = weight_choice

# Compute Type aggregates (bottom-up by sub-sector); add All Banks row
grouped = aggregate_by_type(base, use_cols, weight=weight_col_name, reducer=reducer).round(1)
if not grouped.empty:
    # All Banks roll-up computed bottom-up across banks (sector tickers excluded)
    if weight_col_name and weight_col_name in base.columns:
        w = base[weight_col_name]
        overall = pd.Series({m: (base[m] * w).sum() / w.sum() if w.sum() != 0 else np.nan for m in use_cols})
    else:
        if scope == "Latest period":
            overall = base[use_cols].mean(numeric_only=True)
        else:
            agg_func = np.median if reducer == "median" else np.mean
            overall = base[use_cols].agg(agg_func)
    grouped = pd.concat([grouped, pd.DataFrame([overall.round(1)], index=["All Banks"])])

# Dominance table
if not grouped.empty:
    dom = grouped.copy()
    for c in [rev_col, cost_col, nonrec_col]:
        if c not in dom.columns:
            dom[c] = np.nan
    dominance = pd.DataFrame({
        'Dominant Driver': dom.apply(lambda r: _dominant_driver_row(r, rev_col, cost_col, nonrec_col), axis=1),
        'Value (pp)': dom[[rev_col, cost_col, nonrec_col]].abs().max(axis=1).round(1)
    })
else:
    dominance = pd.DataFrame()

# Display grouped table
st.subheader("Average Impacts by Type")
if not grouped.empty:
    rename_map = {rev_col: 'Revenue (pp)', cost_col: 'Cost (pp)', nonrec_col: 'Non-Rec (pp)', total_col: 'Total (pp)'}
    show_cols = [c for c in [rev_col, cost_col, nonrec_col, total_col] if c in grouped.columns]
    st.dataframe(grouped[show_cols].rename(columns=rename_map).style.format("{:.1f}"), use_container_width=True)
else:
    st.info("No impact columns available for this selection.")

# Dominance display
if not dominance.empty:
    st.subheader("Driver of the Period by Type")
    st.dataframe(dominance, use_container_width=True)

# Driver mix stacked bar
if not grouped.empty:
    st.subheader("Driver Mix by Type")
    plot_df = grouped.copy().reset_index().rename(columns={'index': 'Type'})
    plot_df = plot_df.rename(columns=rename_map)
    melt_cols = [rename_map.get(c, c) for c in show_cols]
    m = plot_df.melt(id_vars=['Type'], value_vars=melt_cols, var_name='Driver', value_name='Impact')
    order_types = None
    if total_col in grouped.columns:
        order_types = grouped.sort_values(total_col, ascending=False).index.tolist()
        m['Type'] = pd.Categorical(m['Type'], categories=order_types, ordered=True)
    fig = px.bar(m, x='Type', y='Impact', color='Driver', barmode='relative', color_discrete_map={
        'Revenue (pp)': '#398278',
        'Cost (pp)': '#cc7c5e',
        'Non-Rec (pp)': '#e6a085',
        'Total (pp)': '#5A8A7F'
    })
    fig.update_layout(height=420, hovermode='x unified')
    st.plotly_chart(fig, use_container_width=True)

# Subcomponent composition
with st.expander("Sub-component Composition"):
    if not grouped.empty and any(c in grouped.columns for c in sub_cols):
        comp = grouped.copy()
        # Revenue: NII vs Fees
        if nii_col in comp.columns or fee_col in comp.columns:
            cols = [c for c in [nii_col, fee_col] if c in comp.columns]
            rev_mix = comp[cols].abs()
            rev_mix_sum = rev_mix.sum(axis=1).replace(0, np.nan)
            rev_share = (rev_mix.div(rev_mix_sum, axis=0) * 100).fillna(0).round(1)
            rev_share.columns = [c.replace(nii_col, 'NII').replace(fee_col, 'Fees') for c in rev_share.columns]
            st.markdown("#### Revenue Components (% of Revenue Impact by absolute contribution)")
            st.dataframe(rev_share, use_container_width=True)
        # Cost: OPEX vs Provisions
        if opex_col in comp.columns or prov_col in comp.columns:
            cols = [c for c in [opex_col, prov_col] if c in comp.columns]
            cost_mix = comp[cols].abs()
            cost_mix_sum = cost_mix.sum(axis=1).replace(0, np.nan)
            cost_share = (cost_mix.div(cost_mix_sum, axis=0) * 100).fillna(0).round(1)
            cost_share.columns = [c.replace(opex_col, 'OPEX').replace(prov_col, 'Provisions') for c in cost_share.columns]
            st.markdown("#### Cost Components (% of Cost Impact by absolute contribution)")
            st.dataframe(cost_share, use_container_width=True)
        # NII: Loan vs NIM
        if loan_col in comp.columns or nim_col in comp.columns:
            cols = [c for c in [loan_col, nim_col] if c in comp.columns]
            nii_mix = comp[cols].abs()
            nii_mix_sum = nii_mix.sum(axis=1).replace(0, np.nan)
            nii_share = (nii_mix.div(nii_mix_sum, axis=0) * 100).fillna(0).round(1)
            nii_share.columns = [c.replace(loan_col, 'Loan').replace(nim_col, 'NIM') for c in nii_share.columns]
            st.markdown("#### NII Breakdown (% of NII Impact by absolute contribution)")
            st.dataframe(nii_share, use_container_width=True)
    else:
        st.info("Sub-component columns not available for this selection.")

# Trend heatmaps (shown when window scope is used)
if scope == "Last N periods":
    st.subheader("Trend Heatmaps")
    # Select metric for heatmap
    # Offer only metrics that exist in the current dataframe
    heatmap_options = []
    if rev_col in df.columns:
        heatmap_options.append(('Revenue (pp)', rev_col))
    if cost_col in df.columns:
        heatmap_options.append(('Cost (pp)', cost_col))
    if nonrec_col in df.columns:
        heatmap_options.append(('Non-Rec (pp)', nonrec_col))
    if total_col in df.columns:
        heatmap_options.append(('Total (pp)', total_col))
    if not heatmap_options:
        st.info("No impact columns available for heatmap in this selection.")
        heatmap_options = [('Total (pp)', total_col)]  # placeholder; will be filtered below
    hm_metric = st.selectbox("Heatmap metric", heatmap_options, format_func=lambda x: x[0])
    hm_col = hm_metric[1]

    # Build period window base
    periods_sorted = (
        pd.Series(df[period_col].dropna().unique())
        .sort_values(ascending=True)
        .tolist()
    )
    window = periods_sorted[-n_periods:]
    win_base = df[df[period_col].isin(window)][['TICKER', 'Type', period_col] + use_cols].copy()
    win_base = win_base[~win_base['TICKER'].isin(sector_agg_tickers)]

    # Aggregate per Type per period (weighted + mean/median as selected)
    if hm_col not in win_base.columns:
        st.warning("Selected heatmap metric is not available for this frequency/selection.")
        agg = pd.DataFrame(columns=['Type', period_col, 'Impact'])
    elif weight_choice == "Total Assets (from sector data)":
        try:
            if freq == "Quarterly":
                wdf = pd.read_parquet(os.path.join(project_root, 'Data/dfsectorquarter.parquet'))
                w_period = 'Date_Quarter'
            else:
                wdf = pd.read_parquet(os.path.join(project_root, 'Data/dfsectoryear.parquet'))
                w_period = 'Year'
            if 'Total Assets' in wdf.columns:
                wdf2 = wdf[[w_period, 'TICKER', 'Total Assets']].rename(columns={w_period: period_col, 'Total Assets': 'WEIGHT_TOTAL_ASSETS'})
                wdf2 = wdf2[wdf2[period_col].isin(window)]
                temp = df.merge(wdf2, on=['TICKER', period_col], how='left')
                temp = temp[~temp['TICKER'].isin(sector_agg_tickers)]
                wcol = 'WEIGHT_TOTAL_ASSETS'
                if reducer == 'median':
                    agg = (
                        temp.groupby(['Type', period_col])
                        .apply(lambda g: _weighted_median(g[hm_col].to_numpy(), g[wcol].to_numpy()))
                        .reset_index(name='Impact')
                    )
                else:
                    agg = (
                        temp.groupby(['Type', period_col])
                        .apply(lambda g: (g[hm_col] * g[wcol]).sum() / g[wcol].sum() if g[wcol].sum() != 0 else np.nan)
                        .reset_index(name='Impact')
                    )
            else:
                raise ValueError('Total Assets column not found')
        except Exception:
            if reducer == 'median':
                agg = win_base.groupby(['Type', period_col], as_index=False)[hm_col].median(numeric_only=True).rename(columns={hm_col: 'Impact'})
            else:
                agg = win_base.groupby(['Type', period_col], as_index=False)[hm_col].mean(numeric_only=True).rename(columns={hm_col: 'Impact'})
    elif weight_choice != "None" and weight_choice in df.columns:
        wcol = weight_choice
        temp = df[df[period_col].isin(window)][['TICKER', 'Type', period_col, wcol, hm_col]].copy()
        temp = temp[~temp['TICKER'].isin(sector_agg_tickers)]
        if reducer == 'median':
            agg = (
                temp.groupby(['Type', period_col])
                .apply(lambda g: _weighted_median(g[hm_col].to_numpy(), g[wcol].to_numpy()))
                .reset_index(name='Impact')
            )
        else:
            agg = (
                temp.groupby(['Type', period_col])
                .apply(lambda g: (g[hm_col] * g[wcol]).sum() / g[wcol].sum() if g[wcol].sum() != 0 else np.nan)
                .reset_index(name='Impact')
            )
    else:
        if reducer == 'median':
            agg = win_base.groupby(['Type', period_col], as_index=False)[hm_col].median(numeric_only=True).rename(columns={hm_col: 'Impact'})
        else:
            agg = win_base.groupby(['Type', period_col], as_index=False)[hm_col].mean(numeric_only=True).rename(columns={hm_col: 'Impact'})

    # Add All Banks roll-up per period for heatmap (bottom-up across banks)
    if hm_col in win_base.columns:
        if weight_choice == "Total Assets (from sector data)":
            try:
                if freq == "Quarterly":
                    wdf = pd.read_parquet(os.path.join(project_root, 'Data/dfsectorquarter.parquet'))
                    w_period = 'Date_Quarter'
                else:
                    wdf = pd.read_parquet(os.path.join(project_root, 'Data/dfsectoryear.parquet'))
                    w_period = 'Year'
                if 'Total Assets' in wdf.columns:
                    wdf2 = wdf[[w_period, 'TICKER', 'Total Assets']].rename(columns={w_period: period_col, 'Total Assets': 'WEIGHT_TOTAL_ASSETS'})
                    wdf2 = wdf2[wdf2[period_col].isin(window)]
                    temp = df.merge(wdf2, on=['TICKER', period_col], how='left')
                    temp = temp[~temp['TICKER'].isin(sector_agg_tickers)]
                    wcol = 'WEIGHT_TOTAL_ASSETS'
                    if reducer == 'median':
                        overall = (
                            temp.groupby(period_col)
                            .apply(lambda g: _weighted_median(g[hm_col].to_numpy(), g[wcol].to_numpy()))
                            .reset_index(name='Impact')
                            .assign(Type='All Banks')
                        )
                    else:
                        overall = (
                            temp.groupby(period_col)
                            .apply(lambda g: (g[hm_col] * g[wcol]).sum() / g[wcol].sum() if g[wcol].sum() != 0 else np.nan)
                            .reset_index(name='Impact')
                            .assign(Type='All Banks')
                        )
                else:
                    overall = win_base.groupby(period_col, as_index=False)[hm_col].mean(numeric_only=True).rename(columns={hm_col: 'Impact'}).assign(Type='All Banks')
            except Exception:
                overall = win_base.groupby(period_col, as_index=False)[hm_col].mean(numeric_only=True).rename(columns={hm_col: 'Impact'}).assign(Type='All Banks')
        elif weight_choice != "None" and weight_choice in df.columns:
            wcol = weight_choice
            temp = df[df[period_col].isin(window)][['TICKER', 'Type', period_col, wcol, hm_col]].copy()
            temp = temp[~temp['TICKER'].isin(sector_agg_tickers)]
            if reducer == 'median':
                overall = (
                    temp.groupby(period_col)
                    .apply(lambda g: _weighted_median(g[hm_col].to_numpy(), g[wcol].to_numpy()))
                    .reset_index(name='Impact')
                    .assign(Type='All Banks')
                )
            else:
                overall = (
                    temp.groupby(period_col)
                    .apply(lambda g: (g[hm_col] * g[wcol]).sum() / g[wcol].sum() if g[wcol].sum() != 0 else np.nan)
                    .reset_index(name='Impact')
                    .assign(Type='All Banks')
                )
        else:
            if reducer == 'median':
                overall = win_base.groupby(period_col, as_index=False)[hm_col].median(numeric_only=True).rename(columns={hm_col: 'Impact'}).assign(Type='All Banks')
            else:
                overall = win_base.groupby(period_col, as_index=False)[hm_col].mean(numeric_only=True).rename(columns={hm_col: 'Impact'}).assign(Type='All Banks')
        agg = pd.concat([agg, overall], ignore_index=True)

    # Pivot to matrix
    # Use string labels for periods to avoid float-like yearly labels (e.g., 2023.5)
    agg['_period_str'] = agg[period_col].astype(str)
    mat = agg.pivot(index='Type', columns='_period_str', values='Impact').round(1)
    # Set symmetric color bounds for green=good (positive), red=bad (negative)
    max_abs = np.nanmax(np.abs(mat.to_numpy())) if mat.size else 1
    fig_hm = px.imshow(mat, color_continuous_scale='RdYlGn', origin='lower', aspect='auto', zmin=-max_abs, zmax=max_abs)
    fig_hm.update_layout(height=420, coloraxis_colorbar_title='pp')
    st.plotly_chart(fig_hm, use_container_width=True)

    # Categorical dominance heatmap (encode dominant driver)
    st.markdown("#### Dominant Driver Map")
    # Compute per Type per period dominant among rev/cost/nonrec
    dom_cols = [c for c in [rev_col, cost_col, nonrec_col] if c in win_base.columns]
    if len(dom_cols) >= 1:
        # Mean by Type-period first
        base_dom = win_base.groupby(['Type', period_col], as_index=False)[dom_cols].mean(numeric_only=True)
        # Map to code
        code_map = {rev_col: 0, cost_col: 1, nonrec_col: 2}
        label_map = {0: 'Revenue', 1: 'Cost', 2: 'Non-Rec'}
        base_dom['dom_code'] = base_dom[dom_cols].abs().idxmax(axis=1).map(code_map)
        dom_mat = base_dom.pivot(index='Type', columns=period_col, values='dom_code')
        # Brand-aligned, distinct colors (match app palette)
        # Revenue = teal, Cost = terracotta, Non-Rec = muted green/teal
        rev_col_hex = '#398278'
        cost_col_hex = '#cc7c5e'
        nonrec_col_hex = '#5A8A7F'
        color_scale = [
            [0.0, rev_col_hex], [1/3 - 1e-6, rev_col_hex],
            [1/3, cost_col_hex], [2/3 - 1e-6, cost_col_hex],
            [2/3, nonrec_col_hex], [1.0, nonrec_col_hex]
        ]
        fig_cat = px.imshow(dom_mat, color_continuous_scale=color_scale, origin='lower', aspect='auto', zmin=-0.5, zmax=2.5)
        fig_cat.update_layout(height=420, coloraxis_showscale=False)
        st.plotly_chart(fig_cat, use_container_width=True)
        st.caption("Legend: Revenue = teal (#398278), Cost = terracotta (#cc7c5e), Non‑Rec = muted green (#5A8A7F)")
    else:
        st.info("Dominance cannot be computed: required columns missing.")
