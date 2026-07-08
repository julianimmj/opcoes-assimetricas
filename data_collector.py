"""
Módulo de coleta de dados de opções do opcoes.net.br
Usa a API JSON interna para obter a grade completa de opções.
"""

import requests
import pandas as pd
from datetime import datetime
import streamlit as st
import numpy as np
from black_scholes import (
    calcular_vol_implicita, calcular_delta, calcular_vol_historica,
    obter_preco_atual, obter_serie_iv_historica, calcular_iv_percentile,
    calcular_iv_rank, SELIC_RATE, tempo_em_anos
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://opcoes.net.br/"
}


@st.cache_data(ttl=600, show_spinner=False)
def buscar_opcoes_ativo(ticker: str, dias_min: int = 20, dias_max: int = 90) -> pd.DataFrame:
    """
    Busca a grade completa de opções (calls + puts) para um ativo
    via API JSON interna do opcoes.net.br.

    Returns:
        DataFrame com colunas: ticker_opcao, tipo, strike, preco, volume,
        negocios, vencimento, dias_venc, delta, iv
    """
    dados = []
    hoje = datetime.now()
    url_base = (
        f"https://opcoes.net.br/listaopcoes/completa"
        f"?idAcao={ticker.upper()}&listarVencimentos=true&cotacoes=true"
    )

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        response = session.get(url_base, timeout=15)
        response.raise_for_status()
        data = response.json()

        if 'data' not in data or 'cotacoesOpcoes' not in data['data']:
            return pd.DataFrame()

        preco_ativo = None
        if 'cotacaoAtivo' in data['data']:
            preco_ativo = data['data']['cotacaoAtivo']

        if preco_ativo is None:
            preco_ativo = obter_preco_atual(ticker)

        if preco_ativo is None or preco_ativo <= 0:
            return pd.DataFrame()

        opcoes_raw = data['data']['cotacoesOpcoes']

        for opcao in opcoes_raw:
            try:
                # Cada opção vem como array com campos posicionais
                # Formato: [ticker, tipo, dir, strike, preco, ..., vencimento, ...]
                if isinstance(opcao, list) and len(opcao) >= 10:
                    ticker_opcao = str(opcao[0]) if opcao[0] else ""
                    tipo_raw = str(opcao[1]).strip().upper() if opcao[1] else ""
                    strike = float(opcao[2]) if opcao[2] else 0.0
                    preco_opcao = float(opcao[3]) if opcao[3] else 0.0
                    negocios = int(opcao[4]) if opcao[4] else 0
                    volume = float(opcao[5]) if opcao[5] else 0.0
                    vencimento_str = str(opcao[9]) if len(opcao) > 9 and opcao[9] else ""

                    # Determinar tipo
                    if "CALL" in tipo_raw or tipo_raw == "C":
                        tipo = "call"
                    elif "PUT" in tipo_raw or tipo_raw == "P":
                        tipo = "put"
                    else:
                        # Tentar determinar pelo ticker (letras A-L = call, M-X = put)
                        if ticker_opcao:
                            letra = ""
                            for c in ticker_opcao[4:]:
                                if c.isalpha():
                                    letra = c.upper()
                                    break
                            if letra and 'A' <= letra <= 'L':
                                tipo = "call"
                            elif letra and 'M' <= letra <= 'X':
                                tipo = "put"
                            else:
                                continue
                        else:
                            continue

                    # Parsear data de vencimento
                    dias_venc = 30  # fallback
                    if vencimento_str:
                        try:
                            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
                                try:
                                    venc_date = datetime.strptime(
                                        vencimento_str.split("T")[0] if "T" in vencimento_str else vencimento_str,
                                        fmt.split("T")[0]
                                    )
                                    dias_venc = max((venc_date - hoje).days, 1)
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            pass

                    # Filtrar por janela de vencimento
                    if not (dias_min <= dias_venc <= dias_max):
                        continue

                    if preco_opcao <= 0 or strike <= 0:
                        continue

                    # Calcular IV e Delta via Black-Scholes
                    T = tempo_em_anos(dias_venc)
                    iv = calcular_vol_implicita(preco_opcao, preco_ativo, strike, T, SELIC_RATE, tipo)
                    if iv is None or iv <= 0.01 or iv > 3.0:
                        continue

                    delta = calcular_delta(preco_ativo, strike, T, SELIC_RATE, iv, tipo)

                    dados.append({
                        "ticker_opcao": ticker_opcao,
                        "tipo": tipo,
                        "strike": strike,
                        "preco": preco_opcao,
                        "volume": volume,
                        "negocios": negocios,
                        "vencimento": vencimento_str,
                        "dias_venc": dias_venc,
                        "delta": round(delta, 4),
                        "iv": round(iv * 100, 2),  # em percentual
                        "preco_ativo": preco_ativo,
                    })

                elif isinstance(opcao, dict):
                    # Formato alternativo como dict
                    ticker_opcao = opcao.get("ticker", opcao.get("codNeg", ""))
                    tipo_raw = opcao.get("tipo", opcao.get("tipoOpcao", "")).upper()
                    strike = float(opcao.get("strike", opcao.get("precoExercicio", 0)))
                    preco_opcao = float(opcao.get("preco", opcao.get("cotacao", opcao.get("ultimoPreco", 0))))
                    negocios = int(opcao.get("negocios", opcao.get("qtdNegocios", 0)))
                    volume = float(opcao.get("volume", opcao.get("volumeFinanceiro", 0)))
                    vencimento_str = opcao.get("vencimento", opcao.get("dataVencimento", ""))

                    if "CALL" in tipo_raw or tipo_raw == "C":
                        tipo = "call"
                    elif "PUT" in tipo_raw or tipo_raw == "P":
                        tipo = "put"
                    else:
                        continue

                    dias_venc = 30
                    if vencimento_str:
                        try:
                            for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                                try:
                                    venc_date = datetime.strptime(vencimento_str[:10], fmt)
                                    dias_venc = max((venc_date - hoje).days, 1)
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            pass

                    if not (dias_min <= dias_venc <= dias_max):
                        continue

                    if preco_opcao <= 0 or strike <= 0:
                        continue

                    T = tempo_em_anos(dias_venc)
                    iv = calcular_vol_implicita(preco_opcao, preco_ativo, strike, T, SELIC_RATE, tipo)
                    if iv is None or iv <= 0.01 or iv > 3.0:
                        continue

                    delta = calcular_delta(preco_ativo, strike, T, SELIC_RATE, iv, tipo)

                    dados.append({
                        "ticker_opcao": ticker_opcao,
                        "tipo": tipo,
                        "strike": strike,
                        "preco": preco_opcao,
                        "volume": volume,
                        "negocios": negocios,
                        "vencimento": vencimento_str,
                        "dias_venc": dias_venc,
                        "delta": round(delta, 4),
                        "iv": round(iv * 100, 2),
                        "preco_ativo": preco_ativo,
                    })

            except (ValueError, TypeError, IndexError):
                continue

    except Exception as e:
        st.warning(f"⚠️ Erro ao buscar opções para {ticker}: {str(e)[:100]}")
        return pd.DataFrame()

    if not dados:
        return pd.DataFrame()

    return pd.DataFrame(dados)


@st.cache_data(ttl=3600, show_spinner=False)
def calcular_metricas_ativo(ticker: str) -> dict | None:
    """
    Calcula todas as métricas de volatilidade necessárias para o screener.

    Returns:
        Dict com: preco, vol_hist, iv_calls, iv_puts, iv_percentile,
        iv_rank, diff_vol, vol_opcoes_total
    """
    preco = obter_preco_atual(ticker)
    if preco is None:
        return None

    vol_hist = calcular_vol_historica(ticker, dias=60)
    if vol_hist is None:
        return None

    # Buscar opções para calcular IV média de calls e puts
    df_opcoes = buscar_opcoes_ativo(ticker)
    if df_opcoes.empty:
        return None

    # IV média ponderada por volume (ou simples se sem volume)
    calls = df_opcoes[df_opcoes["tipo"] == "call"]
    puts = df_opcoes[df_opcoes["tipo"] == "put"]

    if calls.empty and puts.empty:
        return None

    # Focar nas opções ATM (delta mais próximo de ±0.50)
    def iv_media_atm(df, tipo):
        if df.empty:
            return None
        target_delta = 0.50 if tipo == "call" else -0.50
        df = df.copy()
        df["dist_atm"] = abs(df["delta"].abs() - abs(target_delta))
        atm_opts = df.nsmallest(5, "dist_atm")
        if atm_opts["volume"].sum() > 0:
            return np.average(atm_opts["iv"], weights=atm_opts["volume"].clip(lower=1))
        return atm_opts["iv"].mean()

    iv_calls = iv_media_atm(calls, "call")
    iv_puts = iv_media_atm(puts, "put")

    if iv_calls is None and iv_puts is None:
        return None

    iv_calls = iv_calls if iv_calls is not None else (iv_puts if iv_puts is not None else 0)
    iv_puts = iv_puts if iv_puts is not None else (iv_calls if iv_calls is not None else 0)

    iv_atual = (iv_calls + iv_puts) / 2.0 / 100.0  # converter para decimal

    # Calcular IV Percentile e IV Rank
    serie_iv = obter_serie_iv_historica(ticker, janela_dias=252)
    iv_percentile = calcular_iv_percentile(iv_atual, serie_iv) if serie_iv else None
    iv_rank = calcular_iv_rank(iv_atual, serie_iv) if serie_iv else None

    # Diff Vol
    diff_vol = abs(iv_calls - iv_puts) if iv_calls and iv_puts else 0.0

    # Volume total de opções
    vol_total = df_opcoes["volume"].sum()

    return {
        "ticker": ticker,
        "preco": round(preco, 2),
        "vol_hist": round(vol_hist * 100, 2),
        "iv_calls": round(iv_calls, 2),
        "iv_puts": round(iv_puts, 2),
        "iv_media": round((iv_calls + iv_puts) / 2, 2),
        "iv_percentile": round(iv_percentile, 1) if iv_percentile is not None else None,
        "iv_rank": round(iv_rank, 1) if iv_rank is not None else None,
        "diff_vol": round(diff_vol, 2),
        "vol_opcoes": round(vol_total, 0),
        "negocios_total": int(df_opcoes["negocios"].sum()),
    }
