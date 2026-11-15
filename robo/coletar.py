"""Coleta notícias candidatas das fontes listadas em fontes.yaml."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BomDiaPetropolisBot/1.0)"}
TIMEOUT = 25
MAX_LINKS_POR_FONTE = 15
MAX_CARACTERES_TEXTO = 12000


@dataclass
class Candidata:
    fonte: str
    url: str
    titulo: str
    texto: str
    secao_sugerida: str
    imagem: str = ""


def _baixar(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.text


IGNORAR_IMAGEM = re.compile(r"logo|icon|avatar|sprite|banner-?ads|placeholder|gravatar|pixel|\.svg", re.I)


def extrair_imagem(html: str, url: str) -> str:
    """Pega a foto principal da notícia (og:image, twitter:image ou a 1ª foto do texto)."""
    soup = BeautifulSoup(html, "html.parser")
    for atributo, nome in (("property", "og:image"), ("name", "twitter:image"),
                           ("property", "og:image:url"), ("name", "twitter:image:src")):
        tag = soup.find("meta", attrs={atributo: nome})
        if tag and tag.get("content") and not IGNORAR_IMAGEM.search(tag["content"]):
            return urljoin(url, tag["content"].strip())
    corpo = soup.find("article") or soup.find("main") or soup
    for img in corpo.find_all("img"):
        src = img.get("data-src") or img.get("data-lazy-src") or img.get("src") or ""
        largura = img.get("width", "")
        if (src and not src.startswith("data:") and not IGNORAR_IMAGEM.search(src)
                and not (largura.isdigit() and int(largura) < 300)):
            return urljoin(url, src.strip())
    return ""


def extrair_texto(html: str) -> str:
    """Pega o texto principal de uma página de notícia."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    corpo = soup.find("article") or soup.find("main") or soup.body or soup
    paragrafos = [p.get_text(" ", strip=True) for p in corpo.find_all(["p", "h2", "h3", "li"])]
    texto = "\n".join(p for p in paragrafos if len(p) > 30)
    return texto[:MAX_CARACTERES_TEXTO]


def _links_rss(fonte: dict) -> list[tuple[str, str]]:
    feed = feedparser.parse(_baixar(fonte["url"]))
    return [(e.get("link", ""), e.get("title", "")) for e in feed.entries if e.get("link")]


def _links_html(fonte: dict) -> list[tuple[str, str]]:
    soup = BeautifulSoup(_baixar(fonte["url"]), "html.parser")
    padrao = re.compile(fonte["padrao_link"])
    vistos: set[str] = set()
    links = []
    for a in soup.find_all("a", href=True):
        url = urljoin(fonte["url"], a["href"]).split("#")[0]
        titulo = a.get_text(" ", strip=True)
        if padrao.search(url) and url not in vistos and len(titulo) > 15:
            vistos.add(url)
            links.append((url, titulo))
    return links


def coletar(fontes: list[dict], ja_vistas: set[str]) -> list[Candidata]:
    candidatas: list[Candidata] = []
    for fonte in fontes:
        if fonte["tipo"] == "email":
            from .email_releases import coletar_emails

            try:
                candidatas.extend(coletar_emails(fonte, ja_vistas))
            except Exception as erro:
                log.warning("Fonte %s falhou: %s", fonte["nome"], erro)
            continue
        try:
            links = _links_rss(fonte) if fonte["tipo"] == "rss" else _links_html(fonte)
        except Exception as erro:  # uma fonte fora do ar não pode parar o robô
            log.warning("Fonte %s falhou: %s", fonte["nome"], erro)
            continue
        novos = [(u, t) for u, t in links if u not in ja_vistas][:MAX_LINKS_POR_FONTE]
        log.info("%s: %d links, %d novos", fonte["nome"], len(links), len(novos))
        for url, titulo in novos:
            try:
                html = _baixar(url)
                texto = extrair_texto(html)
                foto = extrair_imagem(html, url)
            except Exception as erro:
                log.warning("Não consegui abrir %s: %s", url, erro)
                continue
            if len(texto) < 200:
                continue
            candidatas.append(
                Candidata(fonte["nome"], url, titulo, texto, fonte.get("secao_sugerida", ""), foto)
            )
    return candidatas
