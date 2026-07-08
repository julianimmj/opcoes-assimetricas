"""
Motor do Screener — processa ativos em paralelo calculando as volatilidades.
Filtro 1: Liquidez (volume ≥ R$500k nas opções do ativo)
Filtro 2: Volatilidade (IV Percentile ≤35%, IV Rank ≤30%, Diff Vol ≤3.0)
"""

import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor, as_completed
from data_collector import obter_dados_historicos_lote, processar_ativo_screener
from tickers_opcoes import TICKERS_COM_OPCOES, NOMES_ATIVOS


def executar_screener(
    vol_min_opcoes: float = 500_000.0,
    iv_percentile_max: float = 35.0,
    iv_rank_max: float = 30.0,
    diff_vol_max: float = 3.0,
    progress_callback=None,
) -> pd.DataFrame:
    """
    Executa o screener processando todos os ativos em paralelo.
    Filtra primeiro por lote histórico e depois calcula as volatilidades de forma distribuída.

    Args:
        vol_min_opcoes: Volume financeiro mínimo de opções do ativo em R$
        iv_percentile_max: IV Percentile máximo (%)
        iv_rank_max: IV Rank máximo (%)
        diff_vol_max: Diferença máxima de vol entre calls e puts
        progress_callback: Função de callback para progresso
    """
    tickers = TICKERS_COM_OPCOES
    
    if progress_callback:
        progress_callback(0, 4, "Coletando preços históricos em lote (yfinance)...")
        
    # 1. Obter dados históricos de preços em lote (1 única chamada HTTP para todos os ativos)
    dados_historicos = obter_dados_historicos_lote(tickers)
    
    if not dados_historicos:
        return pd.DataFrame()
        
    if progress_callback:
        progress_callback(1, 4, "Varrendo opções de ativos da B3 em paralelo...")
        
    resultados = []
    ativos_para_processar = list(dados_historicos.keys())
    total_ativos = len(ativos_para_processar)
    
    # 2. Processar ativos em paralelo (Threads)
    # A velocidade é incrível porque cada thread busca a grade de opções de um ativo simultaneamente.
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(processar_ativo_screener, ticker, dados_historicos[ticker]): ticker
            for ticker in ativos_para_processar
        }
        
        concluidos = 0
        for future in as_completed(futures):
            ticker = futures[future]
            concluidos += 1
            
            if progress_callback:
                progress_callback(
                    1 + int((concluidos / total_ativos) * 2), 
                    4, 
                    f"Processando {ticker} ({concluidos}/{total_ativos})..."
                )
                
            try:
                res = future.result()
                if res is not None:
                    # ─── APLICAR FILTROS EM CASCATA ───
                    # Filtro 1: Liquidez das opções
                    if res["vol_opcoes"] < vol_min_opcoes:
                        continue
                        
                    # Filtro 2: Volatilidade
                    if res["iv_percentile"] > iv_percentile_max:
                        continue
                    if res["iv_rank"] > iv_rank_max:
                        continue
                    if res["diff_vol"] > diff_vol_max:
                        continue
                        
                    res["nome"] = NOMES_ATIVOS.get(ticker, ticker)
                    resultados.append(res)
            except Exception:
                continue

    if progress_callback:
        progress_callback(3, 4, "Ordenando e preparando resultados...")

    if not resultados:
        return pd.DataFrame()

    df = pd.DataFrame(resultados)
    
    # Ordenar por IV Percentile (mais baratas no topo)
    df = df.sort_values("iv_percentile", ascending=True)
    
    if progress_callback:
        progress_callback(4, 4, "Concluído!")
        
    return df.reset_index(drop=True)
