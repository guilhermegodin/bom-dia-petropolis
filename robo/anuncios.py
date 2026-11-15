"""Banners de publicidade, lidos de anuncios.yaml.

Cada espaço (topo, lateral, meio, materia) pode ter vários anúncios; só entram os que
estão dentro das datas "de"/"ate". Se houver mais de um ativo, um script curto sorteia
qual aparece em cada visita. Espaço vazio vira um convite "Anuncie aqui" para o Mídia Kit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from html import escape
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
ARQ = RAIZ / "anuncios.yaml"
PASTA_IMAGENS = RAIZ / "anuncios"

ESPACOS = {
    "topo": {"nome": "Faixa do topo", "tamanho": "970x90", "celular": "320x100",
             "onde": "No alto de todas as páginas, logo abaixo do menu."},
    "lateral": {"nome": "Quadrado lateral", "tamanho": "300x250", "celular": "300x250",
                "onde": "Na coluna ao lado das notícias, na capa, nas editorias e nas matérias."},
    "meio": {"nome": "Faixa da capa", "tamanho": "728x90", "celular": "728x90",
             "onde": "No meio da página inicial, entre as editorias."},
    "materia": {"nome": "Faixa na matéria", "tamanho": "728x90", "celular": "728x90",
                "onde": "Dentro de todas as matérias, logo depois do texto."},
}


@dataclass
class Anuncio:
    nome: str
    imagem: str
    link: str
    imagem_celular: str = ""


@dataclass
class Config:
    email: str = ""
    whatsapp: str = ""
    precos: dict[str, str] = field(default_factory=dict)
    ativos: dict[str, list[Anuncio]] = field(default_factory=dict)

    @property
    def link_whatsapp(self) -> str:
        numero = re.sub(r"\D", "", self.whatsapp)
        return f"https://wa.me/{numero}?text=Quero%20anunciar%20no%20Bom%20Dia%20Petr%C3%B3polis" if numero else ""


def _data(valor) -> date | None:
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(str(valor).strip()) if valor else None
    except ValueError:
        print(f"Aviso (anuncios.yaml): data inválida {valor!r}, ignorada.")
        return None


def _imagem(caminho) -> str:
    caminho = str(caminho or "").strip().lstrip("/")
    if caminho.startswith(("http://", "https://")):
        return caminho
    if caminho and not caminho.startswith("anuncios/"):
        caminho = "anuncios/" + caminho
    if caminho and not (RAIZ / caminho).is_file():
        print(f"Aviso (anuncios.yaml): imagem {caminho} não encontrada na pasta anuncios/.")
        return ""
    return caminho


def carregar(hoje: date) -> Config:
    if not ARQ.exists():
        return Config()
    try:
        bruto = yaml.safe_load(ARQ.read_text("utf-8")) or {}
    except yaml.YAMLError as erro:
        # Um erro de digitação no arquivo não pode derrubar o site: segue sem banners.
        print(f"Aviso: anuncios.yaml com erro de formatação, banners desligados nesta rodada.\n{erro}")
        return Config()
    contato = bruto.get("contato") or {}
    cfg = Config(email=str(contato.get("email") or "").strip(),
                 whatsapp=str(contato.get("whatsapp") or "").strip())
    for chave in ESPACOS:
        espaco = (bruto.get("espacos") or {}).get(chave) or {}
        cfg.precos[chave] = str(espaco.get("preco") or "").strip()
        ativos = []
        for item in espaco.get("anuncios") or []:
            if not isinstance(item, dict):
                continue
            de, ate = _data(item.get("de")), _data(item.get("ate"))
            if (de and hoje < de) or (ate and hoje > ate):
                continue
            img, link = _imagem(item.get("imagem")), str(item.get("link") or "").strip()
            if not img or not link.startswith(("http://", "https://")):
                print(f"Aviso (anuncios.yaml): anúncio {item.get('nome')!r} em {chave} sem imagem ou link válido.")
                continue
            ativos.append(Anuncio(nome=str(item.get("nome") or "Anunciante"), imagem=img, link=link,
                                  imagem_celular=_imagem(item.get("imagem_celular"))))
        cfg.ativos[chave] = ativos
    return cfg


def _src(caminho: str, base: str) -> str:
    return caminho if caminho.startswith("http") else base + caminho


def _evento(chave: str, nome: str) -> str:
    return "anuncio-" + chave + "-" + (re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-") or "sem-nome")


def banner(cfg: Config, chave: str, base: str = "") -> str:
    info = ESPACOS[chave]
    w, h = info["tamanho"].split("x")
    ativos = cfg.ativos.get(chave, [])
    if not ativos:
        return (f'<aside class="anuncio anuncio-{chave} anuncio-vazio" aria-label="Espaço publicitário">'
                f'<a href="{base}midia-kit.html" data-goatcounter-click="anuncie-aqui-{chave}">'
                f'<strong>Seu negócio aqui</strong><span>Anuncie no Bom Dia Petrópolis</span></a></aside>')
    pecas = []
    for i, a in enumerate(ativos):
        img = f'<img src="{escape(_src(a.imagem, base))}" alt="{escape(a.nome)}" width="{w}" height="{h}" loading="lazy">'
        if a.imagem_celular:
            img = (f'<picture><source media="(max-width: 600px)" srcset="{escape(_src(a.imagem_celular, base))}">'
                   f"{img}</picture>")
        pecas.append(f'<a href="{escape(a.link)}" target="_blank" rel="sponsored noopener"'
                     f'{" hidden" if i else ""} data-goatcounter-click="{_evento(chave, a.nome)}"'
                     f' data-goatcounter-title="{escape(a.nome)}">{img}</a>')
    rodizio = " data-rodizio" if len(pecas) > 1 else ""
    return (f'<aside class="anuncio anuncio-{chave}" aria-label="Publicidade"{rodizio}>'
            f'<span class="anuncio-rotulo">Publicidade</span>{"".join(pecas)}</aside>')


# Sorteia um dos anúncios quando o espaço tem mais de um ativo.
SCRIPT_RODIZIO = """<script>
document.querySelectorAll('[data-rodizio]').forEach(function (e) {
  var a = e.querySelectorAll('a'), n = Math.floor(Math.random() * a.length);
  a.forEach(function (x, i) { x.hidden = i !== n; });
});
</script>"""
