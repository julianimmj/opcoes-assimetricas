"""
Motor do Screener — aplica filtros em cascata para encontrar ativos ideais.
Filtro 1: Liquidez (volume ≥ R$500k, negócios recentes)
Filtro 2: Volatilidade (IV Percentile ≤35%, IV Rank ≤30%, Diff Vol ≤3.0)
"""

import pandas as pd
import streamlit as st
from data_collector import calcular_metricas_ativo
from tickers_opcoes import TICKERS_COM_OPCOES, NOMES_ATIVOS


def executar_screener(
    tickers: list[str] | None = None,
    vol_min_opcoes: float = 500_000.0,
    iv_percentile_max: float = 35.0,
    iv_rank_max: float = 30.0,
    diff_vol_max: float = 3.0,
    progress_callback=None,
) -> pd.DataFrame:
    """
    Executa o screener completo com filtros em cascata.

    Args:
        tickers: Lista de tickers a analisar (default: TICKERS_COM_OPCOES)
        vol_min_opcoes: Volume financeiro mínimo de opções em R$
        iv_percentile_max: IV Percentile máximo (%)
        iv_rank_max: IV Rank máximo (%)
        diff_vol_max: Diferença máxima de vol entre calls e puts
        progress_callback: Função de callback para progresso (recebe i, total, ticker)

    Returns:
        DataFrame com ativos elegíveis e suas métricas
    """
    if tickers is None:
        tickers = TICKERS_COM_OPCOES

    resultados = []
    total = len(tickers)

    for i, ticker in enumerate(tickers):
        if progress_callback:
            progress_callback(i, total, ticker)

        try:
            metricas = calcular_metricas_ativo(ticker)

            if metricas is None:
                continue

            # ─── FILTRO 1: LIQUIDEZ ───────────────────────────────────────
            # Volume financeiro diário das opções ≥ R$500.000
            if metricas["vol_opcoes"] < vol_min_opcoes:
                continue

            # Verificar se há negócios (proxy: total > 0)
            if metricas["negocios_total"] <= 0:
                continue

            # ─── FILTRO 2: VOLATILIDADE ("Seguro Barato") ────────────────
            # IV Percentile ≤ 35%
            if metricas["iv_percentile"] is not None and metricas["iv_percentile"] > iv_percentile_max:
                continue

            # IV Rank ≤ 30%
            if metricas["iv_rank"] is not None and metricas["iv_rank"] > iv_rank_max:
                continue

            # Diff Vol ≤ 3.0 pontos
            if metricas["diff_vol"] > diff_vol_max:
                continue

            # ─── ATIVO APROVADO ──────────────────────────────────────────
            metricas["nome"] = NOMES_ATIVOS.get(ticker, ticker)
            resultados.append(metricas)

        except Exception:
            continue

    if not resultados:
        return pd.DataFrame()

    df = pd.DataFrame(resultados)

    # Ordenar por IV Percentile (mais barato primeiro)
    if "iv_percentile" in df.columns:
        df = df.sort_values("iv_percentile", ascending=True, na_position="last")

    return df.reset_index(drop=True)
