"""Ссылка «Trade»: шаблоны по сети из env, общие для сайта (/api/config) и бота.

  TRADE_URL_BNB        по умолчанию https://four.meme/token/{address}
  TRADE_URL_ROBINHOOD  по умолчанию https://axiom.trade/t/{address}/@foxscan?chain=robinhood
  TRADE_URL_SOLANA     по умолчанию https://axiom.trade/t/{address}/@foxscan

{address} заменяется адресом токена. Шаблон не https:// или без {address} — берётся дефолт.
"""
import os
from urllib.parse import quote

DEFAULTS = {"bnb": "https://four.meme/token/{address}",
            "robinhood": "https://axiom.trade/t/{address}/@foxscan?chain=robinhood",
            "solana": "https://axiom.trade/t/{address}/@foxscan"}
ENV = {"bnb": "TRADE_URL_BNB", "robinhood": "TRADE_URL_ROBINHOOD", "solana": "TRADE_URL_SOLANA"}


def templates():
    """{сеть: шаблон} из env с проверкой."""
    out = {}
    for chain, default in DEFAULTS.items():
        v = (os.environ.get(ENV[chain]) or "").strip()
        out[chain] = v if v.startswith("https://") and "{address}" in v else default
    return out


def url(chain, address, tpls=None, launchpad=None):
    """Ссылка на торговлю токеном или None, если сеть неизвестна.
    Flap на BNB — страница flap.sh, Genius.fun — страница токена, а не шаблон four.meme этой сети."""
    if chain == "bnb" and launchpad == "flap" and address:
        return "https://flap.sh/bnb/" + quote(address, safe="")
    if chain == "bnb" and launchpad == "genius" and address:
        return "https://genius.fun/token/" + quote(address, safe="")
    tpl = (tpls or templates()).get(chain)
    return tpl.replace("{address}", quote(address, safe="")) if tpl and address else None
