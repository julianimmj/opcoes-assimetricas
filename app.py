"""
🛡️ Screener de Opções Assimétricas — B3
Filtra opções com volatilidade implícita historicamente barata e monta
estruturas Strap/Strip assimétricas com proteção clássica ou total.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
import numpy as np

from tickers_opcoes import TICKERS_COM_OPCOES, NOMES_ATIVOS
from screener_engine import executar_screener
from strategy_engine import montar_estrategia
from black_scholes import SELIC_RATE

# ─── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Screener de Opções Assimétricas — B3",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* Global */
    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* ─── Header Premium ─── */
    .main-header {
        background: linear-gradient(135deg, #0a192f 0%, #172a45 50%, #1a1a3e 100%);
        border-radius: 16px;
        padding: 2rem 2.5rem;
        margin-bottom: 1.5rem;
        border: 1px solid rgba(0, 210, 255, 0.15);
        box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 60px rgba(0,210,255,0.05);
        position: relative;
        overflow: hidden;
    }
    .main-header::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -50%;
        width: 100%;
        height: 100%;
        background: radial-gradient(circle, rgba(0,210,255,0.08) 0%, transparent 60%);
        pointer-events: none;
    }
    .main-header h1 {
        color: #fff;
        font-size: 2.2rem;
        font-weight: 800;
        margin: 0;
        background: linear-gradient(90deg, #00d2ff 0%, #00ffa3 50%, #7b2ff7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        position: relative;
    }
    .main-header p {
        color: rgba(255,255,255,0.65);
        font-size: 0.95rem;
        margin: 0.5rem 0 0 0;
        font-weight: 300;
        position: relative;
    }
    .main-header .badge-selic {
        display: inline-block;
        background: rgba(0,210,255,0.15);
        color: #00d2ff;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        border: 1px solid rgba(0,210,255,0.25);
        margin-top: 0.5rem;
    }

    /* ─── Metric Cards ─── */
    .metric-card {
        background: linear-gradient(135deg, rgba(15,25,47,0.95) 0%, rgba(23,42,69,0.9) 100%);
        border: 1px solid rgba(0,210,255,0.12);
        border-radius: 14px;
        padding: 1.3rem 1.5rem;
        text-align: center;
        backdrop-filter: blur(12px);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 16px rgba(0,0,0,0.2);
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 30px rgba(0,210,255,0.12);
        border-color: rgba(0,210,255,0.3);
    }
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #00d2ff, #00ffa3);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .metric-label {
        font-size: 0.8rem;
        color: rgba(255,255,255,0.5);
        margin-top: 0.3rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }

    /* ─── Section Headers ─── */
    .section-header {
        background: linear-gradient(90deg, rgba(0,210,255,0.1) 0%, transparent 100%);
        border-left: 3px solid #00d2ff;
        padding: 0.6rem 1.2rem;
        border-radius: 0 8px 8px 0;
        margin: 1.5rem 0 1rem 0;
    }
    .section-header h2 {
        color: #fff;
        font-size: 1.2rem;
        font-weight: 700;
        margin: 0;
    }
    .section-header p {
        color: rgba(255,255,255,0.5);
        font-size: 0.8rem;
        margin: 0.2rem 0 0 0;
    }

    /* ─── Recommendation Card ─── */
    .reco-card {
        background: linear-gradient(135deg, rgba(0,26,51,0.95) 0%, rgba(0,40,60,0.9) 100%);
        border: 1px solid rgba(0,255,163,0.2);
        border-radius: 16px;
        padding: 1.8rem 2rem;
        margin: 1rem 0;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3), 0 0 40px rgba(0,255,163,0.05);
        position: relative;
        overflow: hidden;
    }
    .reco-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #00d2ff, #00ffa3, #7b2ff7);
    }
    .reco-card .reco-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #00ffa3;
        margin-bottom: 1rem;
    }
    .reco-card .reco-line {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        padding: 0.8rem 1rem;
        background: rgba(255,255,255,0.03);
        border-radius: 10px;
        margin-bottom: 0.6rem;
        border: 1px solid rgba(255,255,255,0.05);
        transition: all 0.2s ease;
    }
    .reco-card .reco-line:hover {
        background: rgba(0,210,255,0.05);
        border-color: rgba(0,210,255,0.15);
    }
    .reco-card .reco-action {
        font-size: 0.85rem;
        font-weight: 700;
        color: #00ffa3;
        text-transform: uppercase;
        min-width: 70px;
    }
    .reco-card .reco-qty {
        font-size: 1.4rem;
        font-weight: 800;
        color: #fff;
        min-width: 60px;
    }
    .reco-card .reco-ticker {
        font-size: 1rem;
        font-weight: 600;
        color: #00d2ff;
        background: rgba(0,210,255,0.1);
        padding: 2px 10px;
        border-radius: 6px;
    }
    .reco-card .reco-detail {
        font-size: 0.85rem;
        color: rgba(255,255,255,0.6);
    }
    .reco-card .reco-cost {
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid rgba(255,255,255,0.08);
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.5rem;
    }
    .reco-card .reco-cost-item {
        text-align: center;
    }
    .reco-card .reco-cost-value {
        font-size: 1.3rem;
        font-weight: 700;
        color: #fff;
    }
    .reco-card .reco-cost-label {
        font-size: 0.7rem;
        color: rgba(255,255,255,0.4);
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .reco-card .badge-protecao {
        display: inline-block;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-classica {
        background: rgba(0,210,255,0.15);
        color: #00d2ff;
        border: 1px solid rgba(0,210,255,0.3);
    }
    .badge-total {
        background: rgba(0,255,163,0.15);
        color: #00ffa3;
        border: 1px solid rgba(0,255,163,0.3);
    }

    /* ─── Recommendation top boxes ─── */
    .reco-top-badges {
        display: flex;
        gap: 1rem;
        margin-bottom: 1.2rem;
        justify-content: flex-start;
    }
    .badge-box {
        flex: 1;
        max-width: 220px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 0.5rem 1rem;
        text-align: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
    }
    .badge-box-label {
        font-size: 0.72rem;
        color: rgba(255, 255, 255, 0.4);
        text-transform: uppercase;
        font-weight: 500;
        letter-spacing: 0.5px;
        margin-bottom: 0.2rem;
    }
    .badge-box-value {
        font-size: 0.95rem;
        font-weight: 700;
        color: #fff;
    }
    .badge-box-vies-alta {
        border-color: rgba(0, 255, 163, 0.25);
        background: rgba(0, 255, 163, 0.04);
    }
    .badge-box-vies-alta .badge-box-value {
        color: #00ffa3;
    }
    .badge-box-vies-queda {
        border-color: rgba(255, 80, 80, 0.25);
        background: rgba(255, 80, 80, 0.04);
    }
    .badge-box-vies-queda .badge-box-value {
        color: #ff5050;
    }
    .badge-box-protecao {
        border-color: rgba(0, 210, 255, 0.25);
        background: rgba(0, 210, 255, 0.04);
    }
    .badge-box-protecao .badge-box-value {
        color: #00d2ff;
    }

    /* ─── Custom Segmented Radio Buttons ─── */
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        display: flex !important;
        flex-direction: row !important;
        gap: 0.5rem !important;
        width: 100% !important;
        margin-top: 0.5rem !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label {
        flex: 1 !important;
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 10px !important;
        padding: 0.6rem 1rem !important;
        text-align: center !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        transition: all 0.25s ease !important;
        margin: 0 !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:hover {
        background: rgba(0, 210, 255, 0.05) !important;
        border-color: rgba(0, 210, 255, 0.25) !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) {
        background: rgba(0, 210, 255, 0.12) !important;
        border-color: #00d2ff !important;
        box-shadow: 0 0 10px rgba(0, 210, 255, 0.15) !important;
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] > label:has(input:checked) p {
        color: #fff !important;
        font-weight: 600 !important;
    }
    /* Hide default radio elements */
    div[data-testid="stRadio"] div[data-testid="stRadioCircle"] {
        display: none !important;
    }
    div[data-testid="stRadio"] div[class*="stRadioCircle"] {
        display: none !important;
    }
    div[data-testid="stRadio"] div[class*="RadioCircle"] {
        display: none !important;
    }
    div[data-testid="stRadio"] span[class*="Radio"] {
        display: none !important;
    }

    /* ─── Viés Buttons ─── */
    .vies-alta {
        background: linear-gradient(135deg, rgba(0,180,80,0.15) 0%, rgba(0,255,163,0.08) 100%);
        border: 1px solid rgba(0,255,163,0.25);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        transition: all 0.3s ease;
    }
    .vies-alta:hover { border-color: rgba(0,255,163,0.5); }
    .vies-queda {
        background: linear-gradient(135deg, rgba(180,0,0,0.15) 0%, rgba(255,80,80,0.08) 100%);
        border: 1px solid rgba(255,80,80,0.25);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        transition: all 0.3s ease;
    }
    .vies-queda:hover { border-color: rgba(255,80,80,0.5); }

    /* ─── Info Badge ─── */
    .info-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.72rem;
        font-weight: 600;
    }
    .badge-green {
        background: rgba(0,200,100,0.15);
        color: #00c864;
        border: 1px solid rgba(0,200,100,0.25);
    }
    .badge-yellow {
        background: rgba(255,200,0,0.15);
        color: #ffc800;
        border: 1px solid rgba(255,200,0,0.25);
    }
    .badge-red {
        background: rgba(255,80,80,0.15);
        color: #ff5050;
        border: 1px solid rgba(255,80,80,0.25);
    }

    /* ─── DataFrames ─── */
    .stDataFrame { border-radius: 12px; overflow: hidden; }

    /* ─── Sidebar ─── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a192f 0%, #172a45 100%);
    }
    section[data-testid="stSidebar"] .stMarkdown h2 { color: #00d2ff; }
    section[data-testid="stSidebar"] .stMarkdown h3 { color: rgba(255,255,255,0.7); }

    /* ─── Buttons ─── */
    .stButton > button {
        background: linear-gradient(135deg, #00d2ff 0%, #00ffa3 100%);
        color: #0a192f;
        border: none;
        border-radius: 10px;
        font-weight: 700;
        padding: 0.6rem 2rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        font-size: 0.9rem;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,210,255,0.3);
    }

    /* ─── Progress ─── */
    .stProgress > div > div {
        background: linear-gradient(90deg, #00d2ff, #00ffa3);
    }

    /* ─── Footer ─── */
    .footer {
        text-align: center;
        color: rgba(255,255,255,0.25);
        font-size: 0.72rem;
        margin-top: 3rem;
        padding: 1.5rem;
        border-top: 1px solid rgba(255,255,255,0.05);
    }

    /* ─── Disclaimer ─── */
    .disclaimer {
        background: rgba(255,165,0,0.08);
        border: 1px solid rgba(255,165,0,0.15);
        border-radius: 10px;
        padding: 0.8rem 1.2rem;
        font-size: 0.78rem;
        color: rgba(255,255,255,0.5);
        margin-top: 1rem;
    }

    /* ─── Empty state ─── */
    .empty-state {
        text-align: center;
        padding: 3rem 2rem;
        color: rgba(255,255,255,0.4);
    }
    .empty-state .empty-icon { font-size: 3rem; margin-bottom: 1rem; }
    .empty-state .empty-title { font-size: 1.2rem; font-weight: 600; color: rgba(255,255,255,0.6); }
    .empty-state .empty-desc { font-size: 0.9rem; margin-top: 0.5rem; }

    /* ─── Sizing & Equal Heights for Selector Containers ─── */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        min-height: 145px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: space-between !important;
    }
    div[data-testid="stRadio"] > label {
        margin-bottom: 0.5rem !important;
    }

    /* ─── Mobile Responsiveness & Adaptations ─── */
    @media (max-width: 768px) {
        /* Let selection containers stack and size dynamically on mobile */
        div[data-testid="stVerticalBlockBorderWrapper"] {
            min-height: auto !important;
            margin-bottom: 0.8rem !important;
            padding: 0.8rem !important;
        }
        /* Convert radio group options to vertical stack to prevent squishing */
        div[data-testid="stRadio"] > div[role="radiogroup"] {
            flex-direction: column !important;
            gap: 0.4rem !important;
        }
        div[data-testid="stRadio"] > div[role="radiogroup"] > label {
            width: 100% !important;
            padding: 0.5rem 0.8rem !important;
        }
        /* Adjust header, widgets and spacing for mobile */
        .main-header {
            padding: 1.2rem 1.5rem !important;
            margin-bottom: 1rem !important;
        }
        .main-header h1 {
            font-size: 1.6rem !important;
        }
        .main-header p {
            font-size: 0.85rem !important;
        }
        .metric-card {
            padding: 1rem !important;
            margin-bottom: 0.6rem !important;
        }
        .metric-value {
            font-size: 1.8rem !important;
        }
        /* Recommendation card responsive stack */
        .reco-card {
            padding: 1.2rem 1.2rem !important;
        }
        .reco-card .reco-line {
            flex-direction: column !important;
            align-items: flex-start !important;
            gap: 0.4rem !important;
            padding: 0.6rem 0.8rem !important;
        }
        .reco-card .reco-qty {
            font-size: 1.2rem !important;
            min-width: auto !important;
        }
        .reco-card .reco-action {
            min-width: auto !important;
        }
        .reco-card .reco-cost {
            flex-direction: column !important;
            align-items: flex-start !important;
            gap: 0.8rem !important;
        }
        .reco-card .reco-cost-item {
            text-align: left !important;
            width: 100% !important;
        }
        .reco-top-badges {
            flex-direction: column !important;
            gap: 0.6rem !important;
        }
        .badge-box {
            max-width: 100% !important;
            width: 100% !important;
        }
    }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  RENDER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def render_header():
    """Renderiza o cabeçalho premium."""
    st.markdown(f"""
    <div class="main-header">
        <h1>🛡️ Screener de Opções Assimétricas — B3</h1>
        <p>
            Identifica opções historicamente baratas (IV baixo) e monta estruturas
            Strap/Strip assimétricas com proteção inteligente contra movimentos adversos.
        </p>
        <span class="badge-selic">Taxa SELIC: {SELIC_RATE*100:.2f}% a.a. (BCB)</span>
    </div>
    """, unsafe_allow_html=True)


def render_metrics(df):
    """Renderiza os cards de métricas do screener."""
    total = len(df)
    melhor_ivp = df["iv_percentile"].min() if "iv_percentile" in df.columns and not df["iv_percentile"].isna().all() else 0
    melhor_ivr = df["iv_rank"].min() if "iv_rank" in df.columns and not df["iv_rank"].isna().all() else 0
    vol_total = df["vol_opcoes"].sum() if "vol_opcoes" in df.columns else 0

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{total}</div>
            <div class="metric-label">Ativos Elegíveis</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{melhor_ivp:.1f}%</div>
            <div class="metric-label">Menor IV Percentile</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{melhor_ivr:.1f}%</div>
            <div class="metric-label">Menor IV Rank</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">R${vol_total/1e6:.1f}M</div>
            <div class="metric-label">Volume Total Opções</div>
        </div>
        """, unsafe_allow_html=True)


def render_recommendation(resultado):
    """Renderiza o card de recomendação final."""
    if resultado is None:
        return

    vies_emoji = "🟢" if resultado["vies"] == "ALTA" else "🔴"
    vies_label = "ALTA" if resultado["vies"] == "ALTA" else "QUEDA"
    protecao_badge = "badge-classica" if resultado["tipo_protecao"] == "CLASSICA" else "badge-total"
    protecao_label = "Proteção Clássica" if resultado["tipo_protecao"] == "CLASSICA" else "Proteção Total"

    aposta = resultado["aposta"]
    protecao = resultado["protecao"]

    from datetime import timedelta
    
    # Fallback robusto caso haja atraso no reload de cache/modulo no servidor
    if not aposta.get('vencimento'):
        venc_aposta_dt = (datetime.now() + timedelta(days=aposta.get('dias_venc', 8))).strftime("%d/%m/%Y")
    else:
        venc_aposta_dt = datetime.strptime(aposta['vencimento'], "%Y-%m-%d").strftime("%d/%m/%Y")

    if not protecao.get('vencimento'):
        venc_prot_dt = (datetime.now() + timedelta(days=protecao.get('dias_venc', 8))).strftime("%d/%m/%Y")
    else:
        venc_prot_dt = datetime.strptime(protecao['vencimento'], "%Y-%m-%d").strftime("%d/%m/%Y")

    dias_uteis_aposta = aposta.get('dias_uteis', int(aposta.get('dias_venc', 8) * 5 / 7))
    dias_uteis_prot = protecao.get('dias_uteis', int(protecao.get('dias_venc', 8) * 5 / 7))

    html_content = f"""<div class="reco-card">
<div class="reco-title">
🛡️ Estrutura Recomendada para {resultado['ticker']} — {resultado['estrategia']}
</div>
<div class="reco-top-badges">
<div class="badge-box badge-box-vies-{resultado['vies'].lower()}">
<div class="badge-box-label">Viés Direcional</div>
<div class="badge-box-value">{vies_emoji} {vies_label}</div>
</div>
<div class="badge-box badge-box-protecao">
<div class="badge-box-label">Nível de Proteção</div>
<div class="badge-box-value">{protecao_label}</div>
</div>
</div>
<div class="reco-line">
<span class="reco-action">COMPRE</span>
<span class="reco-qty">{aposta['qtd']}</span>
<span>opções</span>
<span class="reco-ticker">{aposta['ticker_opcao']}</span>
<span class="reco-detail">
{aposta['label']} · Δ {aposta['delta']:.2f} · R$ {aposta['preco']:.2f} · Strike {aposta['strike']:.2f} · Vencimento: {venc_aposta_dt} ({dias_uteis_aposta} d.ú.)
</span>
</div>
<div class="reco-line">
<span class="reco-action">COMPRE</span>
<span class="reco-qty">{protecao['qtd']}</span>
<span>opções</span>
<span class="reco-ticker">{protecao['ticker_opcao']}</span>
<span class="reco-detail">
{protecao['label']} · Δ {protecao['delta']:.2f} · R$ {protecao['preco']:.2f} · Strike {protecao['strike']:.2f} · Vencimento: {venc_prot_dt} ({dias_uteis_prot} d.ú.)
</span>
</div>
<div class="reco-cost">
<div class="reco-cost-item">
<div class="reco-cost-value">R$ {resultado['custo_total']:,.2f}</div>
<div class="reco-cost-label">Custo Total</div>
</div>
<div class="reco-cost-item">
<div class="reco-cost-value">R$ {aposta['custo']:,.2f}</div>
<div class="reco-cost-label">Custo Aposta</div>
</div>
<div class="reco-cost-item">
<div class="reco-cost-value">R$ {protecao['custo']:,.2f}</div>
<div class="reco-cost-label">Custo Proteção</div>
</div>
<div class="reco-cost-item">
<div class="reco-cost-value">{resultado['cobertura_pct']:.0f}%</div>
<div class="reco-cost-label">Cobertura Estimada</div>
</div>
<div class="reco-cost-item">
<span class="badge-protecao {protecao_badge}">Proporção: {resultado['proporcao']}</span>
</div>
</div>
</div>"""

    st.markdown(html_content, unsafe_allow_html=True)


def render_payoff_chart(resultado):
    """Renderiza o gráfico de payoff da estratégia."""
    if resultado is None:
        return

    preco_ativo = resultado["preco_ativo"]
    aposta = resultado["aposta"]
    protecao_op = resultado["protecao"]

    # Range de preços para simulação
    precos = np.linspace(preco_ativo * 0.7, preco_ativo * 1.3, 200)

    custo_total = resultado["custo_total"]

    payoff_total = np.zeros_like(precos)

    for p in range(len(precos)):
        spot = precos[p]
        pnl = 0

        # Aposta
        if aposta["tipo"] == "call":
            pnl += aposta["qtd"] * (max(spot - aposta["strike"], 0) - aposta["preco"])
        else:
            pnl += aposta["qtd"] * (max(aposta["strike"] - spot, 0) - aposta["preco"])

        # Proteção
        if protecao_op["tipo"] == "call":
            pnl += protecao_op["qtd"] * (max(spot - protecao_op["strike"], 0) - protecao_op["preco"])
        else:
            pnl += protecao_op["qtd"] * (max(protecao_op["strike"] - spot, 0) - protecao_op["preco"])

        payoff_total[p] = pnl

    fig = go.Figure()

    # Área de lucro/prejuízo
    fig.add_trace(go.Scatter(
        x=precos, y=payoff_total,
        fill='tozeroy',
        fillcolor='rgba(0,210,255,0.08)',
        line=dict(color='#00d2ff', width=2.5),
        name='P&L Total',
        hovertemplate='Preço: R$%{x:.2f}<br>P&L: R$%{y:,.2f}<extra></extra>'
    ))

    # Linha zero
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.2)")

    # Linha do preço atual
    fig.add_vline(x=preco_ativo, line_dash="dot", line_color="#00ffa3",
                  annotation_text=f"Spot: R${preco_ativo:.2f}", annotation_font_color="#00ffa3")

    # Strikes
    fig.add_vline(x=aposta["strike"], line_dash="dot", line_color="rgba(0,210,255,0.4)",
                  annotation_text=f"Strike Aposta: {aposta['strike']:.2f}",
                  annotation_font_color="rgba(0,210,255,0.6)")
    fig.add_vline(x=protecao_op["strike"], line_dash="dot", line_color="rgba(255,165,0,0.4)",
                  annotation_text=f"Strike Proteção: {protecao_op['strike']:.2f}",
                  annotation_font_color="rgba(255,165,0,0.6)")

    fig.update_layout(
        title=dict(
            text=f"Payoff no Vencimento — {resultado['estrategia']}",
            font=dict(color='white', size=16)
        ),
        paper_bgcolor='rgba(10,25,47,0.8)',
        plot_bgcolor='rgba(10,25,47,0.5)',
        font=dict(color='rgba(255,255,255,0.7)', family='Inter'),
        xaxis=dict(title="Preço do Ativo (R$)", gridcolor='rgba(255,255,255,0.05)'),
        yaxis=dict(title="Lucro / Prejuízo (R$)", gridcolor='rgba(255,255,255,0.05)',
                   zerolinecolor='rgba(255,255,255,0.15)'),
        hovermode='x unified',
        showlegend=False,
        margin=dict(t=50, b=50, l=60, r=30),
        height=400,
    )

    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

def render_sidebar():
    """Renderiza a sidebar com filtros configuráveis."""
    with st.sidebar:
        st.markdown("## ⚙️ Parâmetros do Screener")

        st.markdown("### 📊 Filtro de Liquidez")
        vol_min = st.number_input(
            "Volume mínimo de opções (R$)",
            min_value=0,
            max_value=10_000_000,
            value=500_000,
            step=100_000,
            format="%d",
            help="Volume financeiro diário mínimo das opções do ativo"
        )

        st.markdown("### 📉 Filtro de Volatilidade")
        iv_percentile_max = st.slider(
            "IV Percentile máximo (%)",
            min_value=5.0, max_value=100.0, value=50.0, step=1.0,
            help="Percentil máximo da volatilidade implícita (quanto menor, mais barata)"
        )

        iv_rank_max = st.slider(
            "IV Rank máximo (%)",
            min_value=5.0, max_value=100.0, value=50.0, step=1.0,
            help="IV Rank máximo (quanto menor, mais barata)"
        )

        diff_vol_max = st.slider(
            "Diff Vol máximo (pontos)",
            min_value=0.5, max_value=30.0, value=15.0, step=0.5,
            help="Diferença máxima de vol entre calls e puts"
        )

        st.markdown("### 🎯 Estratégia")
        qtd_base = st.number_input(
            "Quantidade base (opções de aposta)",
            min_value=100, max_value=10000, value=200, step=100,
            help="Quantidade base de opções para a perna de aposta"
        )

        st.markdown("---")
        st.markdown("""
        <div class="disclaimer">
            ⚠️ <strong>Aviso:</strong> Esta ferramenta é apenas para fins educacionais
            e de simulação. Não constitui recomendação de investimento.
            Opere com responsabilidade.
        </div>
        """, unsafe_allow_html=True)

    return {
        "vol_min": vol_min,
        "iv_percentile_max": iv_percentile_max,
        "iv_rank_max": iv_rank_max,
        "diff_vol_max": diff_vol_max,
        "qtd_base": qtd_base,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    render_header()
    params = render_sidebar()

    # ─── Botão de execução ────────────────────────────────────────────────
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        executar = st.button("🔍 Executar Screener", type="primary", use_container_width=True)

    with col_info:
        st.markdown(
            f"<p style='color: rgba(255,255,255,0.4); font-size: 0.82rem; padding-top: 0.5rem;'>"
            f"Dados: opcoes.net.br · "
            f"Vol ≥ R${params['vol_min']:,.0f} · "
            f"IVP ≤ {params['iv_percentile_max']:.0f}% · "
            f"IVR ≤ {params['iv_rank_max']:.0f}% · "
            f"Diff ≤ {params['diff_vol_max']:.1f}</p>",
            unsafe_allow_html=True
        )

    # ─── Resultados do Screener ───────────────────────────────────────────
    if executar or "screener_results" in st.session_state:
        if executar:
            st.markdown("""
            <div class="section-header">
                <h2>🔬 Varredura em Andamento</h2>
                <p>Aplicando filtros de liquidez e volatilidade nos ativos da B3...</p>
            </div>
            """, unsafe_allow_html=True)

            progress_bar = st.progress(0)
            status_text = st.empty()

            def on_progress(i, total, msg):
                progress_bar.progress(min((i + 1) / max(total, 1), 1.0))
                status_text.markdown(
                    f"<p style='color: rgba(255,255,255,0.5); font-size: 0.8rem;'>"
                    f"{msg}</p>",
                    unsafe_allow_html=True
                )

            df_resultados = executar_screener(
                vol_min_opcoes=params["vol_min"],
                iv_percentile_max=params["iv_percentile_max"],
                iv_rank_max=params["iv_rank_max"],
                diff_vol_max=params["diff_vol_max"],
                progress_callback=on_progress,
            )

            progress_bar.empty()
            status_text.empty()

            st.session_state["screener_results"] = df_resultados

        df_resultados = st.session_state.get("screener_results", pd.DataFrame())

        if df_resultados.empty:
            st.markdown("""
            <div class="empty-state">
                <div class="empty-icon">🔍</div>
                <div class="empty-title">Nenhum ativo passou nos filtros</div>
                <div class="empty-desc">
                    Tente relaxar os parâmetros na sidebar (ex: aumentar IV Percentile max
                    ou reduzir volume mínimo).
                </div>
            </div>
            """, unsafe_allow_html=True)
            return

        # ─── Cards de Métricas ────────────────────────────────────────
        render_metrics(df_resultados)

        # ─── Tabela de Ativos Elegíveis ───────────────────────────────
        st.markdown("""
        <div class="section-header">
            <h2>📋 Ativos Elegíveis para Estruturas Assimétricas</h2>
            <p>Ativos que passaram em todos os filtros de liquidez e volatilidade</p>
        </div>
        """, unsafe_allow_html=True)

        # Preparar tabela de exibição
        display_cols = ["ticker", "preco"]
        rename_map = {"ticker": "Ticker", "preco": "Preço (R$)"}

        optional_cols = {
            "vol_hist": "Vol. Hist. EWMA (%)",
            "iv_calls": "IV Calls (%)",
            "iv_puts": "IV Puts (%)",
            "iv_percentile": "IV Percentile (%)",
            "iv_rank": "IV Rank (%)",
            "diff_vol": "Diff Vol",
            "vol_opcoes": "Vol. Financeiro (R$)",
        }
        for col, label in optional_cols.items():
            if col in df_resultados.columns:
                display_cols.append(col)
                rename_map[col] = label

        df_display = df_resultados[display_cols].copy()
        df_display = df_display.rename(columns=rename_map)

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Preço (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Vol. Hist. (%)": st.column_config.NumberColumn(format="%.1f%%"),
                "IV Calls (%)": st.column_config.NumberColumn(format="%.1f%%"),
                "IV Puts (%)": st.column_config.NumberColumn(format="%.1f%%"),
                "IV Percentile (%)": st.column_config.ProgressColumn(
                    min_value=0, max_value=100, format="%.1f%%"
                ),
                "IV Rank (%)": st.column_config.ProgressColumn(
                    min_value=0, max_value=100, format="%.1f%%"
                ),
                "Diff Vol": st.column_config.NumberColumn(format="%.2f"),
                "Vol. Opções (R$)": st.column_config.NumberColumn(format="R$ %,.0f"),
            }
        )

        # ─── Seleção do Ativo ─────────────────────────────────────────
        st.markdown("""
        <div class="section-header">
            <h2>🎯 Montagem da Estrutura Assimétrica</h2>
            <p>Selecione um ativo, seu viés direcional e o nível de proteção desejado</p>
        </div>
        """, unsafe_allow_html=True)

        tickers_disponiveis = df_resultados["ticker"].tolist()
        ticker_labels = [
            f"{t} (R${df_resultados[df_resultados['ticker']==t]['preco'].values[0]:.2f})"
            for t in tickers_disponiveis
        ]

        col_sel, col_vies, col_prot = st.columns([2, 1, 1])

        with col_sel:
            selected_label = st.selectbox(
                "Selecione o Ativo",
                options=ticker_labels,
                index=0 if ticker_labels else None,
                help="Escolha o ativo para montar a estrutura de proteção"
            )

        selected_ticker = tickers_disponiveis[ticker_labels.index(selected_label)] if selected_label else None

        with col_vies:
            with st.container(border=True):
                vies = st.radio(
                    "Viés Direcional",
                    options=["🟢 Acredito na ALTA", "🔴 Acredito na QUEDA"],
                    index=0,
                    help="Sua expectativa de direção para o ativo",
                    horizontal=True
                )
                vies_code = "ALTA" if "ALTA" in vies else "QUEDA"

        with col_prot:
            with st.container(border=True):
                protecao = st.radio(
                    "Nível de Proteção",
                    options=["🛡️ Clássica (Mais Barata)", "🏰 Total (Garante o Capital)"],
                    index=0,
                    help="Clássica: proporção fixa 2:1 | Total: cobertura dinâmica de 100%",
                    horizontal=True
                )
                protecao_code = "CLASSICA" if "Clássica" in protecao else "TOTAL"

        # ─── Montar Estratégia ────────────────────────────────────────
        if selected_ticker:
            with st.spinner("Calculando estrutura de proteção..."):
                resultado = montar_estrategia(
                    ticker=selected_ticker,
                    vies=vies_code,
                    protecao=protecao_code,
                    qtd_base=params["qtd_base"],
                )

            if resultado:
                st.markdown("""
                <div class="section-header">
                    <h2>✅ Recomendação Final</h2>
                    <p>Estrutura calculada com base nos filtros e parâmetros selecionados</p>
                </div>
                """, unsafe_allow_html=True)

                render_recommendation(resultado)

                # ─── Gráfico de Payoff ────────────────────────────────
                render_payoff_chart(resultado)

                # ─── Detalhes Adicionais ──────────────────────────────
                with st.expander("📊 Detalhes da Estrutura"):
                    det1, det2 = st.columns(2)

                    with det1:
                        st.markdown("**Perna de Aposta**")
                        st.json({
                            "Ticker": resultado["aposta"]["ticker_opcao"],
                            "Tipo": resultado["aposta"]["label"],
                            "Strike": resultado["aposta"]["strike"],
                            "Preço": resultado["aposta"]["preco"],
                            "Delta": resultado["aposta"]["delta"],
                            "IV (%)": resultado["aposta"]["iv"],
                            "Quantidade": resultado["aposta"]["qtd"],
                            "Custo Total": resultado["aposta"]["custo"],
                            "Dias Venc.": resultado["aposta"]["dias_venc"],
                        })

                    with det2:
                        st.markdown("**Perna de Proteção**")
                        st.json({
                            "Ticker": resultado["protecao"]["ticker_opcao"],
                            "Tipo": resultado["protecao"]["label"],
                            "Strike": resultado["protecao"]["strike"],
                            "Preço": resultado["protecao"]["preco"],
                            "Delta": resultado["protecao"]["delta"],
                            "IV (%)": resultado["protecao"]["iv"],
                            "Quantidade": resultado["protecao"]["qtd"],
                            "Custo Total": resultado["protecao"]["custo"],
                            "Dias Venc.": resultado["protecao"]["dias_venc"],
                        })

                    st.markdown(f"""
                    **Parâmetros do Cálculo:**
                    - Taxa SELIC: {SELIC_RATE*100:.2f}% a.a.
                    - Delta Médio (constante para proteção total): 0.32
                    - Movimento adverso considerado: 10% do ativo
                    - Proporção: {resultado['proporcao']}
                    - Cobertura estimada em cenário adverso: {resultado['cobertura_pct']:.0f}%
                    """)

            else:
                st.warning(
                    f"⚠️ Não foi possível montar a estrutura para {selected_ticker}. "
                    "Opções com Delta adequado podem não estar disponíveis no momento."
                )

    # ─── Footer ───────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="footer">
        Screener de Opções Assimétricas — B3 · Dados: opcoes.net.br + yfinance · Modelo: Black-Scholes<br>
        Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')} ·
        Desenvolvido com Streamlit
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
