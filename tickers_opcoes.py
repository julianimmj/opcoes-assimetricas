"""
Lista de ações brasileiras com opções líquidas na B3.
Inclui os ativos mais negociados no mercado de opções, expandido
para cobrir ativos médios além de PETR/VALE.
"""

# Tickers com opções mais líquidas na B3 (ordenados por liquidez típica)
TICKERS_COM_OPCOES = [
    "PETR4",   # Petrobras PN
    "VALE3",   # Vale ON
    "BOVA11",  # ETF Ibovespa
    "ITUB4",   # Itaú Unibanco PN
    "BBDC4",   # Bradesco PN
    "BBAS3",   # Banco do Brasil ON
    "B3SA3",   # B3 ON
    "ABEV3",   # Ambev ON
    "ITSA4",   # Itaúsa PN
    "WEGE3",   # WEG ON
    "SUZB3",   # Suzano ON
    "RENT3",   # Localiza ON
    "GGBR4",   # Gerdau PN
    "CSNA3",   # CSN ON
    "USIM5",   # Usiminas PNA
    "CMIG4",   # Cemig PN
    "CSAN3",   # Cosan ON
    "PRIO3",   # PetroRio ON
    "HAPV3",   # Hapvida ON
    "LREN3",   # Lojas Renner ON
    "MGLU3",   # Magazine Luiza ON
    "COGN3",   # Cogna ON
    "CYRE3",   # Cyrela ON
    "EQTL3",   # Equatorial ON
    "RADL3",   # Raia Drogasil ON
    "RAIL3",   # Rumo ON
    "TOTS3",   # TOTVS ON
    "KLBN11",  # Klabin UNT
    "JBSS3",   # JBS ON
    "EMBR3",   # Embraer ON
    "VIVT3",   # Telefônica Brasil ON
    "ELET3",   # Eletrobras ON
    "SBSP3",   # Sabesp ON
    "ENEV3",   # Eneva ON
    "BBSE3",   # BB Seguridade ON
    "VBBR3",   # Vibra ON
    "BPAC11",  # BTG Pactual UNT
]

# Nomes amigáveis dos ativos
NOMES_ATIVOS = {
    "PETR4": "Petrobras PN",
    "VALE3": "Vale ON",
    "BOVA11": "ETF Ibovespa",
    "ITUB4": "Itaú Unibanco PN",
    "BBDC4": "Bradesco PN",
    "BBAS3": "Banco do Brasil ON",
    "B3SA3": "B3 ON",
    "ABEV3": "Ambev ON",
    "ITSA4": "Itaúsa PN",
    "WEGE3": "WEG ON",
    "SUZB3": "Suzano ON",
    "RENT3": "Localiza ON",
    "GGBR4": "Gerdau PN",
    "CSNA3": "CSN ON",
    "USIM5": "Usiminas PNA",
    "CMIG4": "Cemig PN",
    "CSAN3": "Cosan ON",
    "PRIO3": "PetroRio ON",
    "HAPV3": "Hapvida ON",
    "LREN3": "Lojas Renner ON",
    "MGLU3": "Magazine Luiza ON",
    "COGN3": "Cogna ON",
    "CYRE3": "Cyrela ON",
    "EQTL3": "Equatorial ON",
    "RADL3": "Raia Drogasil ON",
    "RAIL3": "Rumo ON",
    "TOTS3": "TOTVS ON",
    "KLBN11": "Klabin UNT",
    "JBSS3": "JBS ON",
    "EMBR3": "Embraer ON",
    "VIVT3": "Telefônica Brasil ON",
    "ELET3": "Eletrobras ON",
    "SBSP3": "Sabesp ON",
    "ENEV3": "Eneva ON",
    "BBSE3": "BB Seguridade ON",
    "VBBR3": "Vibra ON",
    "BPAC11": "BTG Pactual UNT",
}
