"""Gera o site estático do Bom Dia Petrópolis a partir das matérias e da agenda.

Uso:  python -m robo.site   (gera a pasta _site/)
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from pathlib import Path

import markdown

RAIZ = Path(__file__).resolve().parent.parent
PASTA_MATERIAS = RAIZ / "conteudo" / "materias"
ARQ_AGENDA = RAIZ / "dados" / "agenda.json"
SAIDA = RAIZ / "_site"
NOME = "Bom Dia Petrópolis"
SECOES = {"cotidiano": "Cotidiano", "agenda": "Agenda", "cidade": "Cidade"}
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo"]
POR_PAGINA = 30

SOL = """<svg width="44" height="44" viewBox="0 0 44 44" aria-hidden="true">
<path d="M2 36 L14 22 L21 29 L30 16 L42 36 Z" fill="#2f6b5a"/>
<circle cx="22" cy="22" r="8" fill="#e8833a"/>
<g stroke="#e8833a" stroke-width="2.4" stroke-linecap="round">
<line x1="22" y1="6" x2="22" y2="10"/><line x1="9" y1="11" x2="12" y2="14"/>
<line x1="35" y1="11" x2="32" y2="14"/><line x1="5" y1="22" x2="9" y2="22"/>
<line x1="39" y1="22" x2="35" y2="22"/></g>
<rect x="0" y="35" width="44" height="3" fill="#2f6b5a"/></svg>"""


@dataclass
class Materia:
    slug: str
    titulo: str
    resumo: str
    secao: str
    tags: list[str]
    data: datetime
    corpo_html: str

    @property
    def url(self) -> str:
        return f"materias/{self.slug}.html"


def ler_materias() -> list[Materia]:
    materias = []
    for arq in PASTA_MATERIAS.glob("*.md"):
        bruto = arq.read_text("utf-8")
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", bruto, re.S)
        if not m:
            continue
        meta = {}
        for linha in m.group(1).splitlines():
            chave, _, valor = linha.partition(":")
            try:
                meta[chave.strip()] = json.loads(valor.strip())
            except json.JSONDecodeError:
                meta[chave.strip()] = valor.strip()
        materias.append(Materia(
            slug=arq.stem,
            titulo=meta.get("titulo", arq.stem),
            resumo=meta.get("resumo", ""),
            secao=meta.get("secao", "Cotidiano"),
            tags=meta.get("tags", []),
            data=datetime.fromisoformat(meta["data"]),
            corpo_html=markdown.markdown(m.group(2).strip()),
        ))
    return sorted(materias, key=lambda x: x.data, reverse=True)


def data_extenso(d: date) -> str:
    return f"{DIAS[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"


def quando(m: Materia) -> str:
    return f"{m.data.day} de {MESES[m.data.month - 1]}, {m.data:%Hh%M}"


def selo(secao: str) -> str:
    return f'<span class="selo {secao.lower()}">{escape(secao)}</span>'


def pagina(titulo: str, conteudo: str, ativo: str = "", base: str = "", descricao: str = "") -> str:
    itens = [("index.html", "Início", "inicio")] + [
        (f"{k}.html", v, k) for k, v in SECOES.items()
    ]
    menu = "".join(
        f'<a href="{base}{href}"{" aria-current=\"page\"" if chave == ativo else ""}>{rotulo}</a>'
        for href, rotulo, chave in itens
    )
    titulo_completo = NOME if titulo == NOME else f"{titulo} · {NOME}"
    descricao = descricao or "As boas notícias de Petrópolis: o que acontece, o que fazer e o que muda na cidade."
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titulo_completo)}</title>
<meta name="description" content="{escape(descricao)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{base}estilo.css">
</head>
<body>
<header class="topo"><div class="envoltorio">
<a class="marca" href="{base}index.html">{SOL}<strong>Bom Dia <span>Petrópolis</span></strong></a>
<p class="data-hoje">{data_extenso(date.today()).capitalize()}</p>
<nav class="menu" aria-label="Seções">{menu}</nav>
</div></header>
<main><div class="envoltorio">
{conteudo}
</div></main>
<footer class="rodape"><div class="envoltorio">
{NOME} · As boas notícias da Cidade Imperial. Matérias escritas com ajuda de inteligência artificial.
</div></footer>
</body>
</html>
"""


def cartao(m: Materia, base: str = "", destaque: bool = False) -> str:
    h = "h2" if destaque else "h3"
    classe = "cartao destaque" if destaque else "cartao"
    return f"""<article class="{classe}">
{selo(m.secao)}
<{h}><a href="{base}{m.url}">{escape(m.titulo)}</a></{h}>
<p>{escape(m.resumo)}</p>
<span class="quando">{quando(m)}</span>
</article>"""


def lista_agenda(eventos: list[dict], limite: int | None = None) -> str:
    if not eventos:
        return '<p class="vazio">Nenhum evento na agenda por enquanto.</p>'
    partes, mes_atual = [], None
    for e in eventos[:limite]:
        try:
            d = date.fromisoformat(e["data_inicio"])
        except ValueError:
            continue
        if limite is None and (d.year, d.month) != mes_atual:
            if mes_atual:
                partes.append("</ul>")
            mes_atual = (d.year, d.month)
            partes.append(f'<h2 class="mes">{MESES[d.month - 1]} de {d.year}</h2><ul class="agenda-lista">')
        detalhes = " · ".join(x for x in [e.get("horario", ""), e.get("local", "")] if x)
        if e.get("gratuito") == "sim":
            detalhes += " · Grátis"
        nome = escape(e["nome"])
        if e.get("materia"):
            nome = f'<a href="materias/{escape(e["materia"])}.html">{nome}</a>'
        partes.append(
            f'<li class="evento"><div class="dia">{d.day}<small>{MESES[d.month - 1][:3]}</small></div>'
            f"<div><strong>{nome}</strong><span>{escape(detalhes)}</span></div></li>"
        )
    if limite is not None:
        return '<ul class="agenda-lista">' + "".join(partes) + "</ul>"
    return "".join(partes) + ("</ul>" if mes_atual else "")


def gerar() -> None:
    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    (SAIDA / "materias").mkdir(parents=True)
    shutil.copy(RAIZ / "site" / "estilo.css", SAIDA / "estilo.css")

    materias = ler_materias()
    hoje = date.today().isoformat()
    eventos = json.loads(ARQ_AGENDA.read_text("utf-8")) if ARQ_AGENDA.exists() else []
    eventos = sorted(
        (e for e in eventos if (e.get("data_fim") or e.get("data_inicio", "")) >= hoje),
        key=lambda e: e["data_inicio"],
    )

    # Capa
    if materias:
        cartoes = cartao(materias[0], destaque=True) + "".join(cartao(m) for m in materias[1:POR_PAGINA])
        principal = f'<div class="grade">{cartoes}</div>'
    else:
        principal = '<p class="vazio">As primeiras notícias chegam em breve.</p>'
    capa = f"""<div class="colunas">
<section aria-label="Últimas notícias">{principal}</section>
<aside class="lateral"><h2>Próximos eventos</h2>{lista_agenda(eventos, limite=8)}
<p><a href="agenda.html">Ver a agenda completa</a></p></aside>
</div>"""
    (SAIDA / "index.html").write_text(pagina(NOME, capa, "inicio"), "utf-8")

    # Seções
    for chave, nome in SECOES.items():
        da_secao = [m for m in materias if m.secao == nome]
        corpo = f'<h1 class="titulo-pagina">{nome}</h1>'
        if chave == "agenda":
            corpo += lista_agenda(eventos) + '<h2 class="titulo-pagina" style="margin-top:34px">Roteiros e programação</h2>'
        if da_secao:
            corpo += '<div class="grade">' + "".join(cartao(m) for m in da_secao[:POR_PAGINA]) + "</div>"
        else:
            corpo += '<p class="vazio">Ainda não há matérias nesta seção.</p>'
        (SAIDA / f"{chave}.html").write_text(pagina(nome, corpo, chave), "utf-8")

    # Matérias
    for m in materias:
        tags = "".join(f"<span>{escape(t)}</span>" for t in m.tags)
        corpo = f"""<article class="materia">
{selo(m.secao)}
<h1>{escape(m.titulo)}</h1>
<p class="linha-fina">{escape(m.resumo)}</p>
<p class="quando">Publicado em {quando(m)}</p>
<div class="corpo">{m.corpo_html}</div>
<div class="tags">{tags}</div>
</article>"""
        (SAIDA / m.url).write_text(
            pagina(m.titulo, corpo, m.secao.lower(), base="../", descricao=m.resumo), "utf-8"
        )
    print(f"Site gerado: {len(materias)} matérias, {len(eventos)} eventos em {SAIDA}")


if __name__ == "__main__":
    gerar()
