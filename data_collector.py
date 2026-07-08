"""
Módulo de coleta de dados de opções do opcoes.net.br
Usa a página /acoes para obter IV, Vol Hist EWMA e Volume Financeiro
diretamente sem recalcular. Usa /listaopcoes/completa para a grade de opções.
"""

import re
import json
import requests
import pandas as pd
from datetime import datetime
import streamlit as st
import numpy as np
from black_scholes import (
    calcular_vol_implicita, calcular_delta, SELIC_RATE, tempo_em_anos
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/json",
    "Referer": "https://opcoes.net.br/"
}


# ═══════════════════════════════════════════════════════════════════════════════
#  COLETA DE DADOS AGREGADOS (IV, Vol Hist, Volume) — /acoes
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600, show_spinner=False)
def buscar_dados_acoes_completo() -> pd.DataFrame:
    """
    Extrai o array JavaScript `stockListDataArray` da página /acoes do opcoes.net.br.
    Retorna todos os ativos com seus dados de volatilidade pré-calculados.

    Colunas do array (posicionais):
        [0]  ticker
        [1]  variação %
        [2]  último preço
        [3]  data/hora (string)
        [4]  IV Rank CALLs
        [5]  IV Percentile CALLs
        [6]  Vol. Implícita CALLs (ATM)
        [7]  Diff Vol Calls-Puts
        [8]  IV Rank PUTs
        [9]  IV Percentile PUTs
        [10] Vol. Implícita PUTs (ATM)
        [11] HV Rank (Vol. Histórica EWMA)
        [12] HV Percentile (Vol. Histórica EWMA)
        [13] Vol. Histórica EWMA
        [14] Volume Financeiro
    """
    url = "https://opcoes.net.br/acoes"

    try:
        session = requests.Session()
        session.headers.update(HEADERS)
        response = session.get(url, timeout=20)
        response.raise_for_status()
        html = response.text

        # Extrair o array stockListDataArray do JavaScript embutido
        match = re.search(r'var\s+stockListDataArray\s*=\s*(\[.*?\])\s*;', html, re.DOTALL)
        if not match:
            st.warning("⚠️ Não foi possível encontrar stockListDataArray na página /acoes")
            return pd.DataFrame()

        raw_json = match.group(1)
        # O array pode conter 'null' que é válido em JSON
        data_array = json.loads(raw_json)

        registros = []
        for item in data_array:
            if not isinstance(item, list) or len(item) < 15:
                continue

            ticker = item[0]
            if not ticker or not isinstance(ticker, str):
                continue

            registros.append({
                "ticker": ticker,
                "variacao_pct": item[1],
                "preco": item[2],
                "data_hora": item[3],
                "iv_rank_calls": item[4],
                "iv_percentile_calls": item[5],
                "iv_calls": item[6],
                "diff_vol": item[7],
                "iv_rank_puts": item[8],
                "iv_percentile_puts": item[9],
                "iv_puts": item[10],
                "hv_rank": item[11],
                "hv_percentile": item[12],
                "vol_hist_ewma": item[13],
                "vol_financeiro": item[14],
            })

        if not registros:
            return pd.DataFrame()

        df = pd.DataFrame(registros)

        # Converter tipos numéricos
        num_cols = [
            "variacao_pct", "preco", "iv_rank_calls", "iv_percentile_calls",
            "iv_calls", "diff_vol", "iv_rank_puts", "iv_percentile_puts",
            "iv_puts", "hv_rank", "hv_percentile", "vol_hist_ewma", "vol_financeiro"
        ]
        for col in num_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Converter percentuais do opcoes.net.br para formato % (eles já vêm em %)
        # IV Rank e IV Percentile vêm como decimal (0.xx) — multiplicar por 100
        pct_cols_decimal = [
            "iv_rank_calls", "iv_percentile_calls", "iv_rank_puts",
            "iv_percentile_puts", "hv_rank", "hv_percentile",
            "variacao_pct"
        ]
        for col in pct_cols_decimal:
            if col in df.columns:
                # Verificar se valores estão em decimal (< 1.5) ou percentual (> 1.5)
                median_val = df[col].dropna().median() if not df[col].dropna().empty else 0
                if abs(median_val) < 1.5:
                    df[col] = df[col] * 100

        # IV e Vol Hist vêm como decimal (0.xx) — multiplicar por 100
        vol_cols_decimal = ["iv_calls", "iv_puts", "vol_hist_ewma"]
        for col in vol_cols_decimal:
            if col in df.columns:
                median_val = df[col].dropna().median() if not df[col].dropna().empty else 0
                if abs(median_val) < 1.5:
                    df[col] = df[col] * 100

        return df

    except Exception as e:
        st.warning(f"⚠️ Erro ao buscar dados de /acoes: {str(e)[:120]}")
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def obter_metricas_screener() -> pd.DataFrame:
    """
    Obtém as métricas filtráveis do screener diretamente do opcoes.net.br.
    Retorna DataFrame pronto para aplicar filtros.
    """
    df = buscar_dados_acoes_completo()

    if df.empty:
        return pd.DataFrame()

    # Calcular médias de IV (calls + puts)
    df["iv_media"] = df[["iv_calls", "iv_puts"]].mean(axis=1)

    # Calcular IV Percentile média (calls + puts) para o filtro
    df["iv_percentile"] = df[["iv_percentile_calls", "iv_percentile_puts"]].mean(axis=1)

    # Calcular IV Rank média (calls + puts) para o filtro
    df["iv_rank"] = df[["iv_rank_calls", "iv_rank_puts"]].mean(axis=1)

    # abs(diff_vol) — já vem calculado
    df["diff_vol_abs"] = df["diff_vol"].abs()

    return df


# ═══════════════════════════════════════════════════════════════════════════════
#  COLETA DE GRADE DE OPÇÕES INDIVIDUAIS — /listaopcoes/completa
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600, show_spinner=False)
def buscar_opcoes_ativo(ticker: str, dias_min: int = 20, dias_max: int = 90) -> pd.DataFrame:
    """
    Busca a grade completa de opções (calls + puts) para um ativo
    via API JSON interna do opcoes.net.br.
    """
    dados = []
    hoje = datetime.now()
    url = (
        f"https://opcoes.net.br/listaopcoes/completa"
        f"?idAcao={ticker.upper()}&listarVencimentos=true&cotacoes=true"
    )

    # Primeiro obter preço do ativo da tabela de ações (mais confiável)
    df_acoes = buscar_dados_acoes_completo()
    preco_ativo = None
    if not df_acoes.empty:
        row = df_acoes[df_acoes["ticker"] == ticker.upper()]
        if not row.empty and pd.notna(row.iloc[0]["preco"]):
            preco_ativo = float(row.iloc[0]["preco"])

    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        response = session.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        if 'data' not in data or 'cotacoesOpcoes' not in data['data']:
            return pd.DataFrame()

        # Usar preço do JSON se não disponível da tabela
        if preco_ativo is None:
            if 'cotacaoAtivo' in data['data'] and data['data']['cotacaoAtivo']:
                preco_ativo = float(data['data']['cotacaoAtivo'])

        if preco_ativo is None or preco_ativo <= 0:
            return pd.DataFrame()

        opcoes_raw = data['data']['cotacoesOpcoes']

        for opcao in opcoes_raw:
            try:
                if isinstance(opcao, list) and len(opcao) >= 10:
                    ticker_opcao = str(opcao[0]) if opcao[0] else ""
                    strike = float(opcao[2]) if opcao[2] else 0.0
                    preco_opcao = float(opcao[3]) if opcao[3] else 0.0
                    negocios = int(opcao[4]) if opcao[4] else 0
                    volume = float(opcao[5]) if opcao[5] else 0.0
                    vencimento_str = str(opcao[9]) if len(opcao) > 9 and opcao[9] else ""

                    # Determinar tipo pela letra do ticker
                    tipo = None
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

                    if tipo is None:
                        tipo_raw = str(opcao[1]).strip().upper() if opcao[1] else ""
                        if "CALL" in tipo_raw or tipo_raw == "C":
                            tipo = "call"
                        elif "PUT" in tipo_raw or tipo_raw == "P":
                            tipo = "put"
                        else:
                            continue

                    # Parsear data de vencimento
                    dias_venc = 30
                    if vencimento_str:
                        try:
                            for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                                try:
                                    venc_str_clean = vencimento_str.split("T")[0] if "T" in vencimento_str else vencimento_str
                                    venc_date = datetime.strptime(venc_str_clean, fmt)
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
                        "iv": round(iv * 100, 2),
                        "preco_ativo": preco_ativo,
                    })

                elif isinstance(opcao, dict):
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
