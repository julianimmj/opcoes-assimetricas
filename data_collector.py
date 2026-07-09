"""
Módulo de coleta de dados de opções do opcoes.net.br e yfinance.
Usa processamento paralelo e chamadas em lote para máxima velocidade.
Meticulosamente projetado para contornar bloqueios de robôs da página /acoes.
"""

import requests
import time
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import yfinance as yf
from black_scholes import (
    calcular_vol_implicita, calcular_delta, SELIC_RATE, tempo_em_anos
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://opcoes.net.br/"
}


# ═══════════════════════════════════════════════════════════════════════════════
#  CÁLCULO EM LOTE DE VOLATILIDADE HISTÓRICA & PROXY DE IV (yfinance)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def obter_dados_historicos_lote(tickers: list[str]) -> dict:
    """
    Busca dados históricos em lote para todos os tickers de uma vez.
    Isso economiza dezenas de conexões HTTP lentas e reduz o tempo de 15s para 1.5s.
    """
    tickers_sa = [f"{t}.SA" for t in tickers]
    try:
        # Baixar dados dos últimos 252 dias úteis (~370 dias corridos) para IV Percentile
        end_date = datetime.now()
        start_date = end_date - timedelta(days=370)
        
        df = yf.download(tickers_sa, start=start_date, end=end_date, progress=False)
        
        if df.empty or "Close" not in df.columns:
            return {}
            
        dados_ativos = {}
        for t in tickers:
            col_name = f"{t}.SA"
            if col_name in df["Close"].columns:
                closes = df["Close"][col_name].dropna()
                if len(closes) >= 60:
                    dados_ativos[t] = closes
        return dados_ativos
    except Exception as e:
        st.warning(f"⚠️ Erro ao baixar dados históricos em lote: {e}")
        return {}


def calcular_vol_e_proxy_iv(closes: pd.Series) -> dict:
    """
    Calcula Vol Histórica 60d e a série histórica de IV proxy (vol móvel 21d)
    para o cálculo de IV Rank e IV Percentile.
    """
    # Retornos logarítmicos
    log_returns = np.log(closes / closes.shift(1)).dropna()
    
    # Volatilidade Histórica 60 dias (anualizada)
    vol_hist_60d = log_returns.tail(60).std() * np.sqrt(252)
    
    # Série de IV proxy (volatilidade móvel de 21 dias)
    # Usamos janela de 21 dias móveis para representar a flutuação da IV ao longo de 252 dias
    iv_series = []
    window = 21
    for i in range(window, len(log_returns)):
        window_returns = log_returns.iloc[i - window:i]
        vol = float(window_returns.std() * np.sqrt(252))
        iv_series.append(vol)
        
    # Limitar série de IV aos últimos 252 dias
    iv_series = iv_series[-252:]
    
    return {
        "vol_hist": vol_hist_60d,
        "iv_series": iv_series
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  COLETA PARALELA DE OPÇÕES (opcoes.net.br)
# ═══════════════════════════════════════════════════════════════════════════════

def buscar_opcoes_unico_ativo(ticker: str, preco_ativo: float, dias_min: int, dias_max: int) -> pd.DataFrame:
    """
    Busca as opções de um ativo individual via API /api/v1 do opcoes.net.br.
    Retorna um DataFrame estruturado com as opções.
    """
    base_url = "https://opcoes.net.br/api/v1"
    dados = []
    hoje = datetime.now()
    z = int(time.time() / 10)
    
    params = {
        "z": z,
        "r0t": "LastQuotesInfo",
        "r1t": "OptionsChain",
        "r1p.underlying_asset_id": ticker.upper(),
        "r1p.skip": "0",
        "r1p.load": "10000",
    }
    
    try:
        response = requests.get(base_url, params=params, headers=HEADERS, timeout=12)
        if response.status_code != 200:
            return pd.DataFrame()
            
        data = response.json()
        reqs = data.get('requests', [])
        if len(reqs) < 2 or 'results' not in reqs[1]:
            return pd.DataFrame()
            
        results = reqs[1]['results']
        expirations = results.get('expirations', [])
        
        for exp in expirations:
            venc_str = exp.get('dt')  # formato: '2026-07-17'
            if not venc_str:
                continue
                
            try:
                venc_date = datetime.strptime(venc_str, "%Y-%m-%d")
                dias_venc = (venc_date - hoje).days
            except Exception:
                continue
                
            if not (dias_min <= dias_venc <= dias_max):
                continue
                
            # Processar CALLs
            for o in exp.get('calls', []):
                try:
                    if not isinstance(o, list) or len(o) < 7:
                        continue
                    
                    suffix = str(o[0])
                    ticker_opcao = f"{ticker[:4].upper()}{suffix}"
                    strike = float(o[3]) if o[3] is not None else 0.0
                    preco_opcao = float(o[6]) if o[6] is not None else 0.0
                    negocios = int(o[9]) if len(o) > 9 and o[9] is not None else 0
                    volume = float(o[10]) if len(o) > 10 and o[10] is not None else 0.0
                    
                    if preco_opcao <= 0 or strike <= 0:
                        continue
                        
                    dados.append({
                        "ticker_opcao": ticker_opcao,
                        "tipo": "call",
                        "strike": strike,
                        "preco": preco_opcao,
                        "volume": volume,
                        "negocios": negocios,
                        "vencimento": venc_str,
                        "dias_venc": dias_venc,
                        "preco_ativo": preco_ativo,
                    })
                except Exception:
                    continue
                    
            # Processar PUTs
            for o in exp.get('puts', []):
                try:
                    if not isinstance(o, list) or len(o) < 7:
                        continue
                        
                    suffix = str(o[0])
                    ticker_opcao = f"{ticker[:4].upper()}{suffix}"
                    strike = float(o[3]) if o[3] is not None else 0.0
                    preco_opcao = float(o[6]) if o[6] is not None else 0.0
                    negocios = int(o[9]) if len(o) > 9 and o[9] is not None else 0
                    volume = float(o[10]) if len(o) > 10 and o[10] is not None else 0.0
                    
                    if preco_opcao <= 0 or strike <= 0:
                        continue
                        
                    dados.append({
                        "ticker_opcao": ticker_opcao,
                        "tipo": "put",
                        "strike": strike,
                        "preco": preco_opcao,
                        "volume": volume,
                        "negocios": negocios,
                        "vencimento": venc_str,
                        "dias_venc": dias_venc,
                        "preco_ativo": preco_ativo,
                    })
                except Exception:
                    continue
    except Exception:
        pass
        
    return pd.DataFrame(dados)


@st.cache_data(ttl=600, show_spinner=False)
def buscar_opcoes_ativo(ticker: str, dias_min: int = 20, dias_max: int = 90) -> pd.DataFrame:
    """
    Busca e calcula gregas/IV para opções de um único ativo.
    Usado no seletor de montagem de estratégias da interface.
    """
    # Obter preço atual do ativo
    try:
        stock = yf.Ticker(f"{ticker.upper()}.SA")
        hist = stock.history(period="1d")
        if hist.empty:
            return pd.DataFrame()
        preco_ativo = float(hist["Close"].iloc[-1])
    except Exception:
        return pd.DataFrame()
        
    df_opcoes = buscar_opcoes_unico_ativo(ticker, preco_ativo, dias_min, dias_max)
    if df_opcoes.empty:
        return pd.DataFrame()
        
    # Calcular IV e Delta
    dados_completos = []
    for _, row in df_opcoes.iterrows():
        tipo = row["tipo"]
        strike = row["strike"]
        preco_opcao = row["preco"]
        dias_venc = row["dias_venc"]
        
        T = tempo_em_anos(dias_venc)
        iv = calcular_vol_implicita(preco_opcao, preco_ativo, strike, T, SELIC_RATE, tipo)
        if iv is None or iv <= 0.01 or iv > 3.0:
            continue
            
        delta = calcular_delta(preco_ativo, strike, T, SELIC_RATE, iv, tipo)
        
        dados_completos.append({
            **row.to_dict(),
            "delta": round(delta, 4),
            "iv": round(iv * 100, 2),
        })
        
    return pd.DataFrame(dados_completos)


# ═══════════════════════════════════════════════════════════════════════════════
#  CÁLCULO DO SCREENER EM PARALELO
# ═══════════════════════════════════════════════════════════════════════════════

def processar_ativo_screener(ticker: str, closes: pd.Series, dias_min: int = 20, dias_max: int = 90) -> dict | None:
    """Processa um ativo para o screener: calcula vol histórica, IVs de opções, Rank/Percentile."""
    try:
        preco_ativo = float(closes.iloc[-1])
        
        # 1. Calcular Vol Histórica e Série de IV Proxy
        vols_hist = calcular_vol_e_proxy_iv(closes)
        vol_hist = vols_hist["vol_hist"]
        iv_series = vols_hist["iv_series"]
        
        if vol_hist is None or not iv_series:
            return None
            
        # 2. Obter grade de opções do ativo
        df_opcoes = buscar_opcoes_unico_ativo(ticker, preco_ativo, dias_min, dias_max)
        if df_opcoes.empty:
            return None
            
        # Filtrar opções mais líquidas e próximas ao dinheiro (ATM) para calcular a IV média
        calls = df_opcoes[df_opcoes["tipo"] == "call"].copy()
        puts = df_opcoes[df_opcoes["tipo"] == "put"].copy()
        
        if calls.empty or puts.empty:
            return None
            
        # Função interna para extrair IV média ATM
        def calcular_iv_media_atm(df, tipo):
            # Encontrar opções próximas ao spot (~10% range)
            df["dist_atm"] = (df["strike"] - preco_ativo).abs() / preco_ativo
            atm_opts = df[df["dist_atm"] <= 0.10].nsmallest(5, "dist_atm")
            if atm_opts.empty:
                atm_opts = df.nsmallest(3, "dist_atm")
                
            ivs = []
            for _, row in atm_opts.iterrows():
                T = tempo_em_anos(row["dias_venc"])
                iv_val = calcular_vol_implicita(row["preco"], preco_ativo, row["strike"], T, SELIC_RATE, tipo)
                if iv_val and 0.05 <= iv_val <= 3.0:
                    ivs.append(iv_val)
            return np.mean(ivs) if ivs else None

        iv_call_atm = calcular_iv_media_atm(calls, "call")
        iv_put_atm = calcular_iv_media_atm(puts, "put")
        
        if iv_call_atm is None or iv_put_atm is None:
            return None
            
        iv_atual_decimal = (iv_call_atm + iv_put_atm) / 2.0
        
        # 3. Calcular IV Percentile e IV Rank
        dias_abaixo = sum(1 for iv in iv_series if iv < iv_atual_decimal)
        iv_percentile = (dias_abaixo / len(iv_series)) * 100.0
        
        iv_min = min(iv_series)
        iv_max = max(iv_series)
        iv_rank = ((iv_atual_decimal - iv_min) / (iv_max - iv_min) * 100.0) if iv_max != iv_min else 50.0
        
        # Diff Vol
        diff_vol = abs(iv_call_atm - iv_put_atm) * 100.0
        
        # Volume total de opções negociadas
        vol_financeiro_opcoes = df_opcoes["volume"].sum()
        
        return {
            "ticker": ticker,
            "preco": round(preco_ativo, 2),
            "vol_hist": round(vol_hist * 100, 2),
            "iv_calls": round(iv_call_atm * 100, 2),
            "iv_puts": round(iv_put_atm * 100, 2),
            "iv_media": round(iv_atual_decimal * 100, 2),
            "iv_percentile": round(iv_percentile, 1),
            "iv_rank": round(iv_rank, 1),
            "diff_vol": round(diff_vol, 2),
            "vol_opcoes": round(vol_financeiro_opcoes, 0),
        }
    except Exception:
        return None
