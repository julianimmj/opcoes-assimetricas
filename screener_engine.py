"""
Motor do Screener — aplica filtros em cascata usando dados pré-calculados
do opcoes.net.br/acoes (IV, Vol Hist EWMA, Volume Financeiro).
Filtro 1: Liquidez (volume ≥ R$500k)
Filtro 2: Volatilidade (IV Percentile ≤35%, IV Rank ≤30%, Diff Vol ≤3.0)
"""

import pandas as pd
import streamlit as st
from data_collector import obter_metricas_screener


def executar_screener(
    vol_min_opcoes: float = 500_000.0,
    iv_percentile_max: float = 35.0,
    iv_rank_max: float = 30.0,
    diff_vol_max: float = 3.0,
    progress_callback=None,
) -> pd.DataFrame:
    """
    Executa o screener completo com filtros em cascata.
    Usa dados pré-calculados do opcoes.net.br (sem recalcular IV/Vol).

    Args:
        vol_min_opcoes: Volume financeiro mínimo do ATIVO em R$
        iv_percentile_max: IV Percentile máximo (%)
        iv_rank_max: IV Rank máximo (%)
        diff_vol_max: Diferença máxima de vol entre calls e puts
        progress_callback: Função de callback para progresso

    Returns:
        DataFrame com ativos elegíveis e suas métricas
    """
    if progress_callback:
        progress_callback(0, 3, "Buscando dados do opcoes.net.br...")

    df = obter_metricas_screener()

    if df.empty:
        return pd.DataFrame()

    if progress_callback:
        progress_callback(1, 3, "Aplicando filtros de liquidez...")

    total_antes = len(df)

    # ─── FILTRO: Apenas ativos com dados de IV disponíveis ────────────
    # (durante horário de mercado, esses campos serão populados)
    df = df.dropna(subset=["iv_calls", "iv_puts", "preco"], how="any")

    # ─── FILTRO 1: LIQUIDEZ ──────────────────────────────────────────
    # Volume financeiro do ATIVO ≥ limiar
    df = df[df["vol_financeiro"] >= vol_min_opcoes]

    if progress_callback:
        progress_callback(2, 3, "Aplicando filtros de volatilidade...")

    # ─── FILTRO 2: VOLATILIDADE ("Seguro Barato") ────────────────────
    # IV Percentile ≤ limite (quanto menor, mais barata a IV está)
    if "iv_percentile" in df.columns:
        mask_ivp = df["iv_percentile"].isna() | (df["iv_percentile"] <= iv_percentile_max)
        df = df[mask_ivp]

    # IV Rank ≤ limite
    if "iv_rank" in df.columns:
        mask_ivr = df["iv_rank"].isna() | (df["iv_rank"] <= iv_rank_max)
        df = df[mask_ivr]

    # Diff Vol ≤ limite
    if "diff_vol_abs" in df.columns:
        mask_dv = df["diff_vol_abs"].isna() | (df["diff_vol_abs"] <= diff_vol_max)
        df = df[mask_dv]

    if df.empty:
        return pd.DataFrame()

    # ─── PREPARAR OUTPUT ─────────────────────────────────────────────
    # Selecionar e renomear colunas para a interface
    output_cols = {
        "ticker": "ticker",
        "preco": "preco",
        "vol_hist_ewma": "vol_hist",
        "iv_calls": "iv_calls",
        "iv_puts": "iv_puts",
        "iv_media": "iv_media",
        "iv_percentile_calls": "iv_percentile_calls",
        "iv_percentile_puts": "iv_percentile_puts",
        "iv_percentile": "iv_percentile",
        "iv_rank_calls": "iv_rank_calls",
        "iv_rank_puts": "iv_rank_puts",
        "iv_rank": "iv_rank",
        "diff_vol": "diff_vol",
        "diff_vol_abs": "diff_vol_abs",
        "vol_financeiro": "vol_opcoes",
        "hv_rank": "hv_rank",
        "hv_percentile": "hv_percentile",
    }

    available_cols = {k: v for k, v in output_cols.items() if k in df.columns}
    df_out = df[list(available_cols.keys())].rename(columns=available_cols)

    # Ordenar por IV Percentile (mais barato primeiro)
    if "iv_percentile" in df_out.columns:
        df_out = df_out.sort_values("iv_percentile", ascending=True, na_position="last")

    if progress_callback:
        progress_callback(3, 3, "Concluído!")

    return df_out.reset_index(drop=True)
