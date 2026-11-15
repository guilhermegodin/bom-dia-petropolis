"""Gera o site estático do Bom Dia Petrópolis a partir das matérias e da agenda.

Uso:  python -m robo.site   (gera a pasta _site/)

O layout segue o de um portal de notícias: barra do dia, marca, menu de editorias,
manchete em carrossel, destaques, blocos por editoria, coluna lateral
com "Últimas" e "Agenda da semana", e rodapé. Como as matérias não têm foto, cada uma
ganha uma arte própria (serra + sol) gerada a partir do título, nas cores da editoria.
Se uma matéria um dia trouxer o campo `imagem` no cabeçalho, ela é usada no lugar da arte.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

import markdown

RAIZ = Path(__file__).resolve().parent.parent
PASTA_MATERIAS = RAIZ / "conteudo" / "materias"
ARQ_AGENDA = RAIZ / "dados" / "agenda.json"
SAIDA = RAIZ / "_site"
NOME = "Bom Dia Petrópolis"
FUSO = ZoneInfo("America/Sao_Paulo")
SECOES = {"cotidiano": "Cotidiano", "agenda": "Agenda", "cidade": "Cidade"}
DESCRICAO_SECAO = {
    "cotidiano": "Gente, histórias e o dia a dia de quem vive na serra.",
    "agenda": "O que fazer em Petrópolis: shows, teatro, festas, feiras e passeios.",
    "cidade": "Serviços, obras, saúde, educação e o que muda na cidade.",
}
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo"]
POR_PAGINA = 30

# Paletas da arte: (céu de cima, céu de baixo, sol, serra do fundo, serra da frente)
PALETAS = {
    "Cotidiano": [("#ffe3b8", "#fff5e4", "#f08a3c", "#7fb39f", "#2f6b5a"),
                  ("#cfe9df", "#f3fbf7", "#f2a14f", "#6ea893", "#245646")],
    "Agenda": [("#ffcfae", "#fff0e2", "#e4572e", "#e59a78", "#a8431f"),
               ("#f7c6b5", "#fde9df", "#f08a3c", "#d98466", "#8f3a1d")],
    "Cidade": [("#cfe0f7", "#f1f6fd", "#f2a14f", "#8fa9d1", "#33507d"),
               ("#d9e4f5", "#f6f8fc", "#e8833a", "#9ab2d6", "#2c4670")],
}

SOL = """<svg class="marca-sol" width="46" height="46" viewBox="0 0 44 44" aria-hidden="true">
<circle cx="22" cy="23" r="8.5" fill="var(--sol)"/>
<g stroke="var(--sol)" stroke-width="2.6" stroke-linecap="round">
<line x1="22" y1="5" x2="22" y2="9.5"/><line x1="8.5" y1="10.5" x2="11.6" y2="13.6"/>
<line x1="35.5" y1="10.5" x2="32.4" y2="13.6"/><line x1="3.5" y1="23" x2="8" y2="23"/>
<line x1="40.5" y1="23" x2="36" y2="23"/></g>
<path d="M0 40 L12 26 L19 32 L29 19 L44 40 Z" fill="var(--serra)"/></svg>"""

ICONE_WHATS = ('<svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" '
               'd="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.2-.4.2-.4.7-1.3.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.7 11.8 11.8 0 0 0 4.5 4c1.7.7 2.3.8 3.2.6.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.2-1.2-.1-.1-.3-.2-.5-.3Z"/></svg>')


def _icone(corpo: str) -> str:
    return (f'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{corpo}</svg>')


ICONES = {
    "inicio": _icone('<path d="M3 11 12 4l9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>'),
    "cotidiano": _icone('<circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.4"/>'
                        '<path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6"/><path d="M15 14.5c3 0 6 1.8 6 5.5"/>'),
    "agenda": _icone('<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>'
                     '<path d="m9.5 15 2 2 3.5-3.5"/>'),
    "cidade": _icone('<path d="M3 21h18"/><path d="M5 21V9l5-3v15"/><path d="M10 21V4l9 4v13"/>'
                     '<path d="M13 10h2M13 13h2M13 16h2"/>'),
    "tempo": _icone('<circle cx="8" cy="8" r="3"/><path d="M8 2v1.5M2 8h1.5M3.8 3.8l1 1M12.2 3.8l-1 1"/>'
                    '<path d="M9 20h9a4 4 0 0 0 0-8 5.5 5.5 0 0 0-10.4 2A3 3 0 0 0 9 20Z"/>'),
    "busca": _icone('<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>'),
}

@dataclass
class Materia:
    slug: str
    titulo: str
    resumo: str
    secao: str
    tags: list[str]
    data: datetime
    corpo_html: str
    palavras: int
    imagem: str = ""

    @property
    def url(self) -> str:
        return f"materias/{self.slug}.html"

    @property
    def chave_secao(self) -> str:
        return self.secao.lower()


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
        texto = m.group(2).strip()
        secao = meta.get("secao", "Cotidiano")
        if secao not in SECOES.values():
            secao = "Cotidiano"
        materias.append(Materia(
            slug=arq.stem,
            titulo=meta.get("titulo", arq.stem),
            resumo=meta.get("resumo", ""),
            secao=secao,
            tags=meta.get("tags", []) if isinstance(meta.get("tags"), list) else [],
            data=datetime.fromisoformat(meta["data"]),
            corpo_html=markdown.markdown(texto),
            palavras=len(texto.split()),
            imagem=meta.get("imagem", "") if isinstance(meta.get("imagem"), str) else "",
        ))
    return sorted(materias, key=lambda x: x.data, reverse=True)


# ---------------------------------------------------------------- textos curtos

def data_extenso(d: date) -> str:
    return f"{DIAS[d.weekday()]}, {d.day} de {MESES[d.month - 1]} de {d.year}"


def quando(m: Materia) -> str:
    return f"{m.data.day} de {MESES[m.data.month - 1]}, {m.data:%Hh%M}"


def hora(m: Materia, agora: datetime) -> str:
    if m.data.date() == agora.date():
        return f"{m.data:%Hh%M}"
    return f"{m.data.day:02d}/{m.data.month:02d}"


def leitura(m: Materia) -> str:
    return f"{max(1, round(m.palavras / 200))} min de leitura"


def chapeu(m: Materia, base: str = "") -> str:
    return f'<a class="chapeu {m.chave_secao}" href="{base}{m.chave_secao}.html">{escape(m.secao)}</a>'


# ---------------------------------------------------------------- arte

def arte_svg(m: Materia) -> str:
    """Ilustração de serra e sol, diferente para cada matéria, nas cores da editoria."""
    semente = int(hashlib.sha1(m.slug.encode()).hexdigest()[:8], 16)
    rnd = random.Random(semente)
    ceu1, ceu2, sol, fundo, frente = rnd.choice(PALETAS.get(m.secao, PALETAS["Cotidiano"]))
    w, h = 1200, 675

    def serra(base_y: int, amplitude: int, picos: int) -> str:
        pontos = [(0, base_y + rnd.randint(-20, 30))]
        for i in range(1, picos * 2):
            x = round(w * i / (picos * 2)) + rnd.randint(-30, 30)
            topo = i % 2 == 1
            y = base_y - (rnd.randint(amplitude // 2, amplitude) if topo else rnd.randint(0, amplitude // 4))
            pontos.append((x, y))
        pontos.append((w, base_y + rnd.randint(-20, 30)))
        caminho = " ".join(f"L{x} {y}" for x, y in pontos[1:])
        return f"M0 {h} L{pontos[0][0]} {pontos[0][1]} {caminho} L{w} {h} Z"

    sx, sy, sr = rnd.randint(260, 940), rnd.randint(170, 280), rnd.randint(70, 105)
    raios = "".join(
        f'<circle cx="{sx}" cy="{sy}" r="{sr + 40 + i * 46}" fill="none" stroke="{sol}" '
        f'stroke-opacity="{0.20 - i * 0.05:.2f}" stroke-width="14"/>'
        for i in range(3)
    )
    nuvens = "".join(
        f'<rect x="{rnd.randint(40, 1000)}" y="{rnd.randint(70, 230)}" width="{rnd.randint(110, 220)}" '
        f'height="22" rx="11" fill="#fff" fill-opacity=".7"/>'
        for _ in range(rnd.randint(1, 3))
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice">
<defs><linearGradient id="c" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{ceu1}"/><stop offset="1" stop-color="{ceu2}"/></linearGradient></defs>
<rect width="{w}" height="{h}" fill="url(#c)"/>{raios}
<circle cx="{sx}" cy="{sy}" r="{sr}" fill="{sol}"/>{nuvens}
<path d="{serra(430, 170, rnd.randint(2, 4))}" fill="{fundo}"/>
<path d="{serra(540, 150, rnd.randint(2, 3))}" fill="{frente}"/>
</svg>"""


def imagem(m: Materia, base: str = "", classe: str = "") -> str:
    """Foto da fonte quando houver; se ela não existir ou não carregar, a arte da serra."""
    arte = f"{base}artes/{m.slug}.svg"
    if m.imagem.startswith(("http://", "https://")):
        tag = (f'<img src="{escape(m.imagem)}" alt="" loading="lazy" width="1200" height="675" '
               f'referrerpolicy="no-referrer" '
               f'onerror="this.onerror=null;this.src=\'{escape(arte)}\'">')
    else:
        tag = f'<img src="{escape(arte)}" alt="" loading="lazy" width="1200" height="675">'
    return (f'<a class="foto {classe}" href="{base}{m.url}" tabindex="-1" aria-hidden="true">'
            f'{tag}</a>')


# ---------------------------------------------------------------- moldura

def pagina(titulo: str, conteudo: str, agora: datetime, ativo: str = "", base: str = "",
           descricao: str = "", ultimas: list[Materia] | None = None) -> str:
    itens = [("index.html", "Início", "inicio")] + [
        (f"{k}.html", v, k) for k, v in SECOES.items()
    ]
    menu = "".join(
        f'<a class="m-{chave}" href="{base}{href}"{" aria-current=\"page\"" if chave == ativo else ""}>{rotulo}</a>'
        for href, rotulo, chave in itens
    ) + f'<a class="m-busca" href="{base}busca.html">{ICONES["busca"]}<span>Buscar</span></a>'
    atalhos = "".join(
        f'<a href="{base}{href}"><span class="bolinha b-{chave}">{ICONES[chave]}</span>{rotulo}</a>'
        for href, rotulo, chave in itens[1:]
    ) + f'<a href="{base}index.html#tempo"><span class="bolinha b-tempo">{ICONES["tempo"]}</span>Tempo</a>'
    links_rodape = "".join(f'<li><a href="{base}{k}.html">{v}</a></li>' for k, v in SECOES.items())
    titulo_completo = NOME if titulo == NOME else f"{titulo} · {NOME}"
    descricao = descricao or "As boas notícias de Petrópolis: o que acontece, o que fazer e o que muda na cidade."
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(titulo_completo)}</title>
<meta name="description" content="{escape(descricao)}">
<meta property="og:title" content="{escape(titulo)}">
<meta property="og:description" content="{escape(descricao)}">
<meta property="og:site_name" content="{NOME}">
<meta name="theme-color" content="#24574a">
<link rel="icon" href="{base}favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600;9..144,800&family=Source+Sans+3:wght@400;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{base}estilo.css">
<script src="{base}portal.js" defer></script>
</head>
<body data-base="{base}">
<a class="pular" href="#conteudo">Pular para o conteúdo</a>
<header class="topo"><div class="envoltorio topo-grade">
<nav class="atalhos" aria-label="Atalhos">{atalhos}</nav>
<a class="marca" href="{base}index.html" aria-label="{NOME}, página inicial">{SOL}
<span class="marca-nome"><small>Bom Dia</small>Petrópolis</span></a>
<div class="topo-direita">
<div class="relogio"><strong data-relogio>{agora:%H:%M}</strong><span>{data_extenso(agora.date())}</span></div>
<form class="busca" action="{base}busca.html" role="search">
<input type="search" name="q" placeholder="Buscar no portal" aria-label="Buscar no portal">
<button type="submit">Buscar</button></form>
</div>
</div></header>
<nav class="menu" aria-label="Editorias"><div class="envoltorio">{menu}</div></nav>
<main id="conteudo"><div class="envoltorio">
{conteudo}
</div></main>
<footer class="rodape"><div class="envoltorio">
<div class="rodape-marca">{SOL}<div><strong>{NOME}</strong>
<p>As boas notícias da Cidade Imperial: gente que faz, o que fazer e o que muda em Petrópolis.</p></div></div>
<div><h2>Editorias</h2><ul>{links_rodape}<li><a href="{base}busca.html">Buscar</a></li></ul></div>
<div><h2>Sobre</h2><p>Portal independente, atualizado quatro vezes por dia.
As matérias são escritas com ajuda de inteligência artificial a partir de informações públicas.</p></div>
</div>
<div class="envoltorio rodape-fim">© {agora.year} {NOME}</div>
</footer>
</body>
</html>
"""


# ---------------------------------------------------------------- blocos

def cartao(m: Materia, base: str = "", com_foto: bool = True, resumo: bool = False, classe: str = "") -> str:
    foto = imagem(m, base) if com_foto else ""
    linha = f"<p>{escape(m.resumo)}</p>" if resumo and m.resumo else ""
    return f"""<article class="cartao {classe}">{foto}<div class="cartao-texto">
{chapeu(m, base)}
<h3><a href="{base}{m.url}">{escape(m.titulo)}</a></h3>{linha}
<span class="quando">{quando(m)}</span>
</div></article>"""


def manchete(m: Materia) -> str:
    return f"""<article class="manchete">{imagem(m, classe="foto-grande")}
<div class="manchete-texto">{chapeu(m)}
<h2><a href="{m.url}">{escape(m.titulo)}</a></h2>
<p>{escape(m.resumo)}</p>
<span class="quando">{quando(m)} · {leitura(m)}</span></div></article>"""


def carrossel(materias: list[Materia]) -> str:
    slides = "".join(
        f'<div class="slide" role="group" aria-roledescription="slide" aria-label="{i + 1} de {len(materias)}">'
        f'{manchete(m)}</div>'
        for i, m in enumerate(materias)
    )
    pontos = "".join(
        f'<button type="button" aria-label="Ver destaque {i + 1}"{" aria-current=\"true\"" if i == 0 else ""}></button>'
        for i in range(len(materias))
    )
    controles = (f'<div class="carrossel-controles"><button type="button" class="seta" data-anterior aria-label="Anterior">‹</button>'
                 f'<div class="pontos">{pontos}</div>'
                 f'<button type="button" class="seta" data-proximo aria-label="Próximo">›</button></div>') if len(materias) > 1 else ""
    return (f'<section class="carrossel" aria-roledescription="carrossel" aria-label="Principais notícias">'
            f'<div class="carrossel-trilho">{slides}</div>{controles}</section>')


def lista_numerada(materias: list[Materia], agora: datetime, base: str = "") -> str:
    itens = "".join(
        f'<li><a href="{base}{m.url}">{escape(m.titulo)}</a><span>{escape(m.secao)} · {hora(m, agora)}</span></li>'
        for m in materias
    )
    return f'<ol class="numerada">{itens}</ol>'


def evento_li(e: dict, d: date, base: str = "") -> str:
    detalhes = " · ".join(x for x in [e.get("horario", ""), e.get("local", "")] if x)
    gratis = '<em class="gratis">Grátis</em>' if e.get("gratuito") == "sim" else ""
    nome = escape(e["nome"])
    if e.get("materia"):
        nome = f'<a href="{base}materias/{escape(e["materia"])}.html">{nome}</a>'
    return (f'<li class="evento"><div class="dia">{d.day}<small>{MESES[d.month - 1][:3]}</small></div>'
            f"<div><strong>{nome}</strong><span>{escape(detalhes)}</span>{gratis}</div></li>")


def datas_evento(e: dict) -> tuple[date, date] | None:
    try:
        ini = date.fromisoformat(e["data_inicio"])
        fim = date.fromisoformat(e.get("data_fim") or e["data_inicio"])
    except (KeyError, ValueError):
        return None
    return ini, max(ini, fim)


def lista_agenda(eventos: list[dict], hoje: date, limite: int | None = None, base: str = "") -> str:
    if not eventos:
        return '<p class="vazio">Nenhum evento na agenda por enquanto.</p>'
    if limite is not None:
        itens = []
        for e in eventos:
            ds = datas_evento(e)
            if ds:
                itens.append(evento_li(e, max(ds[0], hoje), base))
            if len(itens) == limite:
                break
        return '<ul class="agenda-lista">' + "".join(itens) + "</ul>"

    # Agenda completa: separada em "Acontecendo agora", "Esta semana" e por mês
    grupos: dict[str, list[str]] = {}
    fim_semana = hoje + timedelta(days=6 - hoje.weekday())
    for e in eventos:
        ds = datas_evento(e)
        if not ds:
            continue
        ini, fim = ds
        if ini <= hoje <= fim:
            grupo = "Acontecendo agora"
        elif ini <= fim_semana:
            grupo = "Ainda esta semana"
        else:
            grupo = f"{MESES[ini.month - 1].capitalize()} de {ini.year}"
        grupos.setdefault(grupo, []).append(evento_li(e, max(ini, hoje), base))
    return "".join(
        f'<h2 class="mes">{g}</h2><ul class="agenda-lista">{"".join(itens)}</ul>'
        for g, itens in grupos.items()
    )


def bloco_secao(chave: str, nome: str, materias: list[Materia]) -> str:
    if not materias:
        return ""
    principal, resto = materias[0], materias[1:4]
    if resto:
        miolo = (f'<div class="bloco-grade">{cartao(principal, resumo=True, classe="grande")}'
                 f'<div class="bloco-lista">{"".join(cartao(m, com_foto=False) for m in resto)}</div></div>')
    else:
        miolo = cartao(principal, resumo=True, classe="deitado grande")
    return f"""<section class="bloco {chave}" aria-labelledby="b-{chave}">
<header class="bloco-topo"><h2 id="b-{chave}"><a href="{chave}.html">{nome}</a></h2>
<a class="ver-mais" href="{chave}.html">Ver tudo</a></header>
{miolo}
</section>"""


def lateral(materias: list[Materia], eventos: list[dict], hoje: date, agora: datetime, base: str = "",
            com_agenda: bool = True) -> str:
    agenda = f"""<section class="caixa caixa-agenda"><h2>Agenda da semana</h2>{lista_agenda(eventos, hoje, limite=6, base=base)}
<a class="botao" href="{base}agenda.html">Ver agenda completa</a></section>""" if com_agenda else ""
    return f"""<aside class="lateral">
<section class="caixa caixa-tempo" id="tempo" aria-live="polite"><h2>Tempo em Petrópolis</h2>
<div data-tempo><p class="vazio">Carregando a previsão…</p></div></section>
<section class="caixa"><h2>Últimas</h2>{lista_numerada(materias[:5], agora, base)}</section>
{agenda}
</aside>"""


# ---------------------------------------------------------------- geração

def gerar() -> None:
    if SAIDA.exists():
        shutil.rmtree(SAIDA)
    (SAIDA / "materias").mkdir(parents=True)
    (SAIDA / "artes").mkdir()
    shutil.copy(RAIZ / "site" / "estilo.css", SAIDA / "estilo.css")
    shutil.copy(RAIZ / "site" / "portal.js", SAIDA / "portal.js")
    (SAIDA / "favicon.svg").write_text(
        SOL.replace('class="marca-sol" width="46" height="46" ', 'xmlns="http://www.w3.org/2000/svg" ')
        .replace("var(--sol)", "#e8833a").replace("var(--serra)", "#24574a"), "utf-8")

    agora = datetime.now(FUSO)
    hoje = agora.date()
    materias = ler_materias()
    for m in materias:
        (SAIDA / "artes" / f"{m.slug}.svg").write_text(arte_svg(m), "utf-8")

    eventos = json.loads(ARQ_AGENDA.read_text("utf-8")) if ARQ_AGENDA.exists() else []
    eventos = sorted(
        (e for e in eventos if (datas_evento(e) or (date.min, date.min))[1] >= hoje),
        key=lambda e: e["data_inicio"],
    )

    # Capa
    if materias:
        topo, destaques = materias[:3], materias[3:6]
        usados = {m.slug for m in materias[:6]}
        blocos = ""
        for k, v in SECOES.items():
            da_secao = [m for m in materias if m.secao == v and m.slug not in usados][:4]
            usados |= {m.slug for m in da_secao}
            blocos += bloco_secao(k, v, da_secao)
        mais = [m for m in materias[:POR_PAGINA] if m.slug not in usados]
        bloco_mais = ""
        if mais:
            bloco_mais = ('<section class="bloco"><header class="bloco-topo"><h2>Mais notícias</h2></header>'
                          '<div class="lista-larga">' + "".join(cartao(m, resumo=True, classe="deitado") for m in mais)
                          + "</div></section>")
        corpo_capa = f"""<div class="capa-topo">{carrossel(topo)}
<div class="destaques">{"".join(cartao(m) for m in destaques)}</div></div>
<div class="colunas"><div class="principal">{blocos}{bloco_mais}</div>
{lateral(materias, eventos, hoje, agora)}</div>"""
    else:
        corpo_capa = '<p class="vazio">As primeiras notícias chegam em breve.</p>'
    (SAIDA / "index.html").write_text(pagina(NOME, corpo_capa, agora, "inicio", ultimas=materias), "utf-8")

    # Editorias
    for chave, nome in SECOES.items():
        da_secao = [m for m in materias if m.secao == nome]
        corpo = f"""<header class="cabeca-secao {chave}"><h1>{nome}</h1><p>{DESCRICAO_SECAO[chave]}</p></header>"""
        if chave == "agenda":
            corpo += f'<div class="colunas"><div class="principal">{lista_agenda(eventos, hoje)}'
            if da_secao:
                corpo += ('<section class="bloco"><header class="bloco-topo"><h2>Roteiros e programação</h2></header>'
                          '<div class="lista-larga">' + "".join(cartao(m, resumo=True, classe="deitado") for m in da_secao[:POR_PAGINA])
                          + "</div></section>")
            corpo += f"</div>{lateral(materias, eventos, hoje, agora, com_agenda=False)}</div>"
        elif da_secao:
            principal = f'<div class="capa-secao">{manchete(da_secao[0])}</div>'
            resto = "".join(cartao(m, resumo=True, classe="deitado") for m in da_secao[1:POR_PAGINA])
            resto = resto or '<p class="vazio">Novas matérias desta editoria chegam nas próximas rodadas.</p>'
            corpo += f"""{principal}<div class="colunas"><div class="principal"><div class="lista-larga">{resto}</div></div>
{lateral(materias, eventos, hoje, agora)}</div>"""
        else:
            corpo += '<p class="vazio">Ainda não há matérias nesta seção.</p>'
        (SAIDA / f"{chave}.html").write_text(pagina(nome, corpo, agora, chave, ultimas=materias), "utf-8")

    # Busca: índice com todas as matérias + página de resultados (a busca roda no navegador)
    indice = [{"t": m.titulo, "r": m.resumo, "s": m.secao, "u": m.url, "d": quando(m),
               "k": " ".join(m.tags)} for m in materias]
    (SAIDA / "busca.json").write_text(json.dumps(indice, ensure_ascii=False), "utf-8")
    corpo_busca = """<header class="cabeca-secao"><h1>Buscar</h1><p>Procure por assunto, bairro, evento ou pessoa.</p></header>
<form class="busca busca-grande" action="busca.html" role="search">
<input type="search" name="q" placeholder="Ex.: Natal, Itaipava, teatro" aria-label="Buscar no portal">
<button type="submit">Buscar</button></form>
<p class="busca-status" data-busca-status aria-live="polite"></p>
<div class="lista-larga" data-busca-resultados></div>"""
    (SAIDA / "busca.html").write_text(pagina("Buscar", corpo_busca, agora, ultimas=materias), "utf-8")

    # Matérias
    for m in materias:
        tags = "".join(f"<span>{escape(t)}</span>" for t in m.tags)
        relacionadas = [o for o in materias if o.secao == m.secao and o.slug != m.slug][:3]
        if len(relacionadas) < 3:
            relacionadas += [o for o in materias if o.slug != m.slug and o not in relacionadas][:3 - len(relacionadas)]
        leia = "".join(cartao(o, base="../") for o in relacionadas)
        texto_whats = f"{m.titulo} – {NOME}"
        corpo = f"""<div class="colunas"><article class="materia">
<nav class="trilha" aria-label="Você está em"><a href="../index.html">Início</a> › {chapeu(m, "../")}</nav>
<h1>{escape(m.titulo)}</h1>
<p class="linha-fina">{escape(m.resumo)}</p>
<div class="assinatura"><span><strong>Redação {NOME}</strong><br>{quando(m)} · {leitura(m)}</span>
<a class="compartilhar" data-texto="{escape(texto_whats)}" href="https://wa.me/?text={escape(texto_whats)}" target="_blank" rel="noopener">{ICONE_WHATS}Compartilhar</a></div>
<figure class="foto-materia">{imagem(m, "../")}</figure>
<div class="corpo">{m.corpo_html}</div>
<div class="tags">{tags}</div>
</article>{lateral(materias, eventos, hoje, agora, base="../")}</div>
<section class="bloco leia-tambem"><header class="bloco-topo"><h2>Leia também</h2></header>
<div class="grade-3">{leia}</div></section>
<script>
document.querySelectorAll('.compartilhar').forEach(function (a) {{
  a.href = 'https://wa.me/?text=' + encodeURIComponent(a.dataset.texto + ' ' + location.href);
}});
</script>"""
        (SAIDA / m.url).write_text(
            pagina(m.titulo, corpo, agora, m.chave_secao, base="../", descricao=m.resumo, ultimas=materias), "utf-8"
        )
    print(f"Site gerado: {len(materias)} matérias, {len(eventos)} eventos em {SAIDA}")


if __name__ == "__main__":
    gerar()
