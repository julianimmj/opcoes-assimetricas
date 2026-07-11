"""
Motor de Estratégias — calcula as opções exatas e proporções para
estruturas de proteção assimétrica (Strap/Strip).
"""

import math
import pandas as pd
from data_collector import buscar_opcoes_ativo
from black_scholes import SELIC_RATE


# ─── Constantes ───────────────────────────────────────────────────────────────

DELTA_MEDIO_PADRAO = 0.32  # constante para estimativa de lucro na proteção total
LOTE_PADRAO = 100          # lote padrão de opções na B3


def arredondar_lote(qtd: float) -> int:
    """Arredonda para o lote padrão mais próximo (múltiplo de 100)."""
    return max(LOTE_PADRAO, int(math.ceil(qtd / LOTE_PADRAO) * LOTE_PADRAO))


# ─── Seleção de Opções por Delta ─────────────────────────────────────────────

def selecionar_opcao_por_delta(
    df_opcoes: pd.DataFrame,
    tipo: str,
    delta_min: float,
    delta_max: float,
) -> dict | None:
    """
    Seleciona a melhor opção dentro de uma faixa de Delta.

    Args:
        df_opcoes: DataFrame com opções do ativo
        tipo: "call" ou "put"
        delta_min: Delta mínimo (em valor absoluto para puts, usar negativo)
        delta_max: Delta máximo

    Returns:
        Dict com dados da opção selecionada ou None
    """
    df = df_opcoes[df_opcoes["tipo"] == tipo].copy()

    if df.empty:
        return None

    # Filtrar por faixa de delta
    if tipo == "call":
        mask = (df["delta"] >= delta_min) & (df["delta"] <= delta_max)
    else:  # put
        mask = (df["delta"] >= delta_min) & (df["delta"] <= delta_max)

    df_filtrado = df[mask]

    if df_filtrado.empty:
        # Relaxar filtro: buscar a mais próxima do centro da faixa
        centro = (delta_min + delta_max) / 2
        df["dist_centro"] = abs(df["delta"] - centro)
        melhor = df.nsmallest(1, "dist_centro").iloc[0]
    else:
        # Priorizar por volume/liquidez dentro da faixa
        if df_filtrado["volume"].sum() > 0:
            melhor = df_filtrado.sort_values("volume", ascending=False).iloc[0]
        else:
            # Priorizar pelo delta mais próximo do centro
            centro = (delta_min + delta_max) / 2
            df_filtrado = df_filtrado.copy()
            df_filtrado["dist_centro"] = abs(df_filtrado["delta"] - centro)
            melhor = df_filtrado.nsmallest(1, "dist_centro").iloc[0]

    return {
        "ticker_opcao": melhor["ticker_opcao"],
        "tipo": melhor["tipo"],
        "strike": melhor["strike"],
        "preco": melhor["preco"],
        "delta": melhor["delta"],
        "iv": melhor["iv"],
        "dias_venc": melhor["dias_venc"],
        "dias_uteis": melhor["dias_uteis"] if "dias_uteis" in melhor else int(melhor["dias_venc"] * 5 / 7),
        "vencimento": melhor["vencimento"] if "vencimento" in melhor else "",
        "volume": melhor["volume"],
    }


# ─── Montagem de Estratégia ──────────────────────────────────────────────────

def montar_estrategia(
    ticker: str,
    vies: str,           # "ALTA" ou "QUEDA"
    protecao: str,       # "CLASSICA" ou "TOTAL"
    qtd_base: int = 200, # quantidade base de opções de especulação
) -> dict | None:
    """
    Monta a estrutura de proteção assimétrica completa.

    Args:
        ticker: Ticker do ativo (ex: "PETR4")
        vies: "ALTA" (Strap) ou "QUEDA" (Strip)
        protecao: "CLASSICA" (2:1 fixo) ou "TOTAL" (cobertura dinâmica)
        qtd_base: Quantidade base de opções de especulação

    Returns:
        Dict com:
        - especulacao: {ticker_opcao, tipo, strike, preco, delta, qtd, custo}
        - protecao: {ticker_opcao, tipo, strike, preco, delta, qtd, custo}
        - custo_total, preco_ativo, vies, tipo_protecao
    """
    df_opcoes = buscar_opcoes_ativo(ticker)

    if df_opcoes.empty:
        return None

    preco_ativo = df_opcoes["preco_ativo"].iloc[0] if "preco_ativo" in df_opcoes.columns else None
    if preco_ativo is None:
        return None

    if vies.upper() == "ALTA":
        # ─── STRAP ASSIMÉTRICO ───────────────────────────────────────
        # Call ATM/levemente OTM (Delta 0.45 a 0.52)
        especulacao = selecionar_opcao_por_delta(df_opcoes, "call", 0.45, 0.52)

        # Put bem OTM, ~10% abaixo (Delta -0.18 a -0.10)
        protecao_op = selecionar_opcao_por_delta(df_opcoes, "put", -0.18, -0.10)

        if especulacao is None or protecao_op is None:
            return None

        qtd_especulacao = arredondar_lote(qtd_base)

        if protecao.upper() == "CLASSICA":
            # Strap: 2 CALLs para cada 1 PUT
            qtd_protecao = arredondar_lote(qtd_especulacao / 2)
        else:
            # PROTEÇÃO TOTAL
            custo_total_especulacao = qtd_especulacao * especulacao["preco"]
            lucro_unit_put = preco_ativo * 0.10 * DELTA_MEDIO_PADRAO
            if lucro_unit_put > 0:
                qtd_protecao = arredondar_lote(custo_total_especulacao / lucro_unit_put)
            else:
                qtd_protecao = arredondar_lote(qtd_especulacao / 2)

    elif vies.upper() == "QUEDA":
        # ─── STRIP ASSIMÉTRICO ───────────────────────────────────────
        # Put ATM/levemente OTM (Delta -0.52 a -0.45)
        especulacao = selecionar_opcao_por_delta(df_opcoes, "put", -0.52, -0.45)

        # Call bem OTM, ~10% acima (Delta 0.10 a 0.18)
        protecao_op = selecionar_opcao_por_delta(df_opcoes, "call", 0.10, 0.18)

        if especulacao is None or protecao_op is None:
            return None

        qtd_especulacao = arredondar_lote(qtd_base)

        if protecao.upper() == "CLASSICA":
            # Strip: 2 PUTs para cada 1 CALL
            qtd_protecao = arredondar_lote(qtd_especulacao / 2)
        else:
            # PROTEÇÃO TOTAL
            custo_total_especulacao = qtd_especulacao * especulacao["preco"]
            lucro_unit_call = preco_ativo * 0.10 * DELTA_MEDIO_PADRAO
            if lucro_unit_call > 0:
                qtd_protecao = arredondar_lote(custo_total_especulacao / lucro_unit_call)
            else:
                qtd_protecao = arredondar_lote(qtd_especulacao / 2)
    else:
        return None

    custo_especulacao = qtd_especulacao * especulacao["preco"]
    custo_protecao = qtd_protecao * protecao_op["preco"]
    custo_total = custo_especulacao + custo_protecao

    # Calcular cobertura estimada (% do custo coberto em movimento adverso de 10%)
    if protecao.upper() == "TOTAL":
        lucro_estimado_protecao = qtd_protecao * preco_ativo * 0.10 * DELTA_MEDIO_PADRAO
        cobertura_pct = min(100.0, (lucro_estimado_protecao / custo_especulacao) * 100) if custo_especulacao > 0 else 0
    else:
        lucro_estimado_protecao = qtd_protecao * preco_ativo * 0.10 * DELTA_MEDIO_PADRAO
        cobertura_pct = min(100.0, (lucro_estimado_protecao / custo_especulacao) * 100) if custo_especulacao > 0 else 0

    return {
        "ticker": ticker,
        "preco_ativo": preco_ativo,
        "vies": vies.upper(),
        "tipo_protecao": protecao.upper(),
        "estrategia": "Strap Assimétrico" if vies.upper() == "ALTA" else "Strip Assimétrico",
        "especulacao": {
            **especulacao,
            "qtd": qtd_especulacao,
            "custo": round(custo_especulacao, 2),
            "label": "CALL ATM" if vies.upper() == "ALTA" else "PUT ATM",
        },
        "protecao": {
            **protecao_op,
            "qtd": qtd_protecao,
            "custo": round(custo_protecao, 2),
            "label": "PUT OTM (Proteção)" if vies.upper() == "ALTA" else "CALL OTM (Proteção)",
        },
        "custo_total": round(custo_total, 2),
        "proporcao": f"{qtd_especulacao}:{qtd_protecao}",
        "cobertura_pct": round(cobertura_pct, 1),
    }
