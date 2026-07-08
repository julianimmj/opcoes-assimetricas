"""
Módulo de cálculos financeiros: Black-Scholes, gregas (Delta),
volatilidade histórica e implícita, taxa SELIC dinâmica.
"""

import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
import yfinance as yf
import requests
from datetime import datetime, timedelta


# ─── Taxa SELIC ────────────────────────────────────────────────────────────────

def obter_taxa_selic_atual() -> float:
    """Busca a meta da taxa Selic atualizada via API do Banco Central do Brasil."""
    try:
        r = requests.get(
            'https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json',
            timeout=5
        )
        return float(r.json()[0]['valor']) / 100.0
    except Exception:
        return 0.1175  # fallback conservador


SELIC_RATE = obter_taxa_selic_atual()


# ─── Utilidades ────────────────────────────────────────────────────────────────

def tempo_em_anos(dias_uteis: int) -> float:
    """Converte dias úteis em fração de ano (252 dias úteis)."""
    return max(dias_uteis / 252.0, 1 / 252.0)


# ─── Black-Scholes Pricing ────────────────────────────────────────────────────

def black_scholes_price(S: float, K: float, T: float, r: float,
                        sigma: float, tipo: str = "call") -> float:
    """
    Calcula o preço teórico de uma opção europeia via Black-Scholes.

    Args:
        S: Preço spot do ativo
        K: Preço de exercício (strike)
        T: Tempo até o vencimento em anos
        r: Taxa livre de risco (anualizada)
        sigma: Volatilidade (anualizada)
        tipo: "call" ou "put"

    Returns:
        Preço teórico da opção
    """
    if sigma <= 0 or T <= 0 or S <= 0 or K <= 0:
        return 0.0

    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    if tipo.lower() == "call":
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


# ─── Gregas ────────────────────────────────────────────────────────────────────

def calcular_delta(S: float, K: float, T: float, r: float,
                   sigma: float, tipo: str = "call") -> float:
    """
    Calcula o Delta da opção via Black-Scholes.

    Returns:
        Delta (0 a 1 para calls, -1 a 0 para puts)
    """
    if sigma <= 0 or T <= 0 or S <= 0 or K <= 0:
        return 0.0

    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))

    if tipo.lower() == "call":
        return norm.cdf(d1)
    else:
        return norm.cdf(d1) - 1.0


def calcular_gamma(S: float, K: float, T: float, r: float,
                   sigma: float) -> float:
    """Calcula o Gamma da opção."""
    if sigma <= 0 or T <= 0 or S <= 0 or K <= 0:
        return 0.0

    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return norm.pdf(d1) / (S * sigma * np.sqrt(T))


def calcular_vega(S: float, K: float, T: float, r: float,
                  sigma: float) -> float:
    """Calcula o Vega da opção (sensibilidade à vol)."""
    if sigma <= 0 or T <= 0 or S <= 0 or K <= 0:
        return 0.0

    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    return S * norm.pdf(d1) * np.sqrt(T) / 100.0


# ─── Volatilidade Implícita ───────────────────────────────────────────────────

def calcular_vol_implicita(preco_mercado: float, S: float, K: float,
                           T: float, r: float, tipo: str = "call") -> float | None:
    """
    Calcula a volatilidade implícita via solver Brent.

    Args:
        preco_mercado: Preço observado da opção no mercado
        S: Preço spot
        K: Strike
        T: Tempo em anos
        r: Taxa livre de risco
        tipo: "call" ou "put"

    Returns:
        Volatilidade implícita anualizada ou None se não convergir
    """
    if preco_mercado <= 0 or S <= 0 or K <= 0 or T <= 0:
        return None

    def objetivo(sigma):
        return black_scholes_price(S, K, T, r, sigma, tipo) - preco_mercado

    try:
        iv = brentq(objetivo, 0.001, 5.0, xtol=1e-6, maxiter=200)
        return iv
    except (ValueError, RuntimeError):
        return None


# ─── Volatilidade Histórica ───────────────────────────────────────────────────

def calcular_vol_historica(ticker: str, dias: int = 60) -> float | None:
    """
    Calcula a volatilidade histórica anualizada usando retornos log-normais.

    Args:
        ticker: Ticker da ação (sem .SA)
        dias: Número de dias úteis para o cálculo

    Returns:
        Volatilidade anualizada em decimal (ex: 0.35 = 35%)
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(dias * 1.8))

        stock = yf.Ticker(f"{ticker}.SA")
        hist = stock.history(start=start_date, end=end_date)

        if hist.empty or len(hist) < dias:
            return None

        closes = hist["Close"].tail(dias)

        if len(closes) < 2:
            return None

        log_returns = np.log(closes / closes.shift(1)).dropna()

        if len(log_returns) < 10:
            return None

        vol = log_returns.std() * np.sqrt(252)
        return float(vol)

    except Exception:
        return None


# ─── Preço Atual ──────────────────────────────────────────────────────────────

def obter_preco_atual(ticker: str) -> float | None:
    """Obtém o preço de fechamento mais recente do ativo via yfinance."""
    try:
        stock = yf.Ticker(f"{ticker}.SA")
        hist = stock.history(period="5d")
        if hist.empty:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None


# ─── Série Histórica de IV (para IV Percentile e IV Rank) ─────────────────────

def obter_serie_iv_historica(ticker: str, janela_dias: int = 252) -> list[float]:
    """
    Reconstrói uma série aproximada de volatilidade implícita histórica
    usando a relação entre vol histórica em janelas móveis como proxy.

    Para um cálculo mais preciso, precisaríamos de dados históricos de
    opções. Usamos vol. histórica em janelas de 21 dias (1 mês) como proxy.

    Returns:
        Lista de valores de IV proxy para os últimos `janela_dias` dias
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=int(janela_dias * 2.0))

        stock = yf.Ticker(f"{ticker}.SA")
        hist = stock.history(start=start_date, end=end_date)

        if hist.empty or len(hist) < 60:
            return []

        closes = hist["Close"]
        log_returns = np.log(closes / closes.shift(1)).dropna()

        # Calcula vol em janelas móveis de 21 dias (proxy para IV)
        vol_series = []
        window = 21
        for i in range(window, len(log_returns)):
            window_returns = log_returns.iloc[i - window:i]
            vol = float(window_returns.std() * np.sqrt(252))
            vol_series.append(vol)

        return vol_series[-janela_dias:] if len(vol_series) > janela_dias else vol_series

    except Exception:
        return []


def calcular_iv_percentile(iv_atual: float, serie_iv: list[float]) -> float | None:
    """
    IV Percentile = % de dias em que IV esteve ABAIXO do nível atual.
    Quanto menor, mais barata está a opção historicamente.
    """
    if not serie_iv or iv_atual is None:
        return None

    dias_abaixo = sum(1 for iv in serie_iv if iv < iv_atual)
    return (dias_abaixo / len(serie_iv)) * 100.0


def calcular_iv_rank(iv_atual: float, serie_iv: list[float]) -> float | None:
    """
    IV Rank = (IV_atual - IV_min) / (IV_max - IV_min) * 100.
    Quanto menor, mais barata está a opção historicamente.
    """
    if not serie_iv or iv_atual is None:
        return None

    iv_min = min(serie_iv)
    iv_max = max(serie_iv)

    if iv_max == iv_min:
        return 50.0  # neutro se não há variação

    return ((iv_atual - iv_min) / (iv_max - iv_min)) * 100.0
