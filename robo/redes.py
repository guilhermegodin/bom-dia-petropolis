"""Posta as matérias novas no Facebook e no Instagram, com um card de imagem.

Uso:  python -m robo.redes cartoes    (gera os cards em _site/redes/, antes de publicar o site)
      python -m robo.redes postar     (posta no Facebook e no Instagram, depois do site no ar)
      python -m robo.redes postar --teste   (só mostra o que postaria)
      python -m robo.redes verificar  (confere se o token da Meta funciona, sem postar nada)

Usa as APIs oficiais da Meta. Precisa de um segredo no GitHub:
  META_TOKEN  token de acesso da Página do Facebook (a conta do Instagram precisa ser
              profissional e estar ligada a essa Página).
Variáveis opcionais (Settings > Secrets and variables > Actions > Variables):
  REDES_POR_RODADA  quantas matérias postar por rodada (padrão 3)
  REDES_ATIVAS      "facebook,instagram" (padrão), ou só uma delas
  SITE_URL          endereço do site (padrão: o do GitHub Pages)

Sem o META_TOKEN, nada é postado e o robô segue normalmente.
WhatsApp não é automatizado de propósito: robôs em grupos levam ao bloqueio do número.
"""

from __future__ import annotations

import argparse
import io
import hashlib
import json
import logging
import math
import os
import random
import re
import unicodedata
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .site import FUSO, NOME, PALETAS, SAIDA, Materia, ler_materias

RAIZ = Path(__file__).resolve().parent.parent
ARQ_ESTADO = RAIZ / "dados" / "redes.json"
PASTA_CARDS = SAIDA / "redes"
FONTES = Path(__file__).resolve().parent / "fontes"
API = "https://graph.facebook.com/v24.0"
SITE_PADRAO = "https://guilhermegodin.github.io/bom-dia-petropolis/"
JANELA_POSTAR = timedelta(hours=24)  # só posta matérias desta idade para baixo
JANELA_CARDS = timedelta(hours=48)   # gera cards com folga, para nunca faltar
MAX_TENTATIVAS = 3

# Uma cor por editoria, as mesmas do site (site/estilo.css)
COR_SECAO = {"Cotidiano": "#2f7a63", "Agenda": "#c4502a", "Cidade": "#35598f"}
SOL = "#e8833a"
SERRA_ESCURA = "#173d33"
W, H = 1080, 1350

log = logging.getLogger("redes")


# ---------------------------------------------------------------- estado

def ler_estado() -> dict:
    return json.loads(ARQ_ESTADO.read_text("utf-8")) if ARQ_ESTADO.exists() else {}


def salvar_estado(estado: dict) -> None:
    # guarda só os últimos 400 registros para o arquivo não crescer para sempre
    itens = sorted(estado.items(), key=lambda kv: kv[1].get("quando", ""))[-400:]
    ARQ_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    ARQ_ESTADO.write_text(json.dumps(dict(itens), ensure_ascii=False, indent=2), "utf-8")


def redes_ativas() -> list[str]:
    bruto = os.environ.get("REDES_ATIVAS") or "facebook,instagram"
    return [r.strip() for r in bruto.split(",") if r.strip() in ("facebook", "instagram")]


def pendentes(materias: list[Materia], estado: dict, janela: timedelta) -> list[Materia]:
    """Matérias recentes que ainda faltam em alguma rede (e não estouraram as tentativas)."""
    agora = datetime.now(FUSO)
    saida = []
    for m in materias:
        if agora - m.data > janela:
            continue
        reg = estado.get(m.slug, {})
        if reg.get("tentativas", 0) >= MAX_TENTATIVAS:
            continue
        if any(not reg.get(rede) for rede in redes_ativas()):
            saida.append(m)
    return saida


def escolher(materias: list[Materia], limite: int) -> list[Materia]:
    """As mais novas primeiro, preferindo as que têm foto; posta da mais antiga para a mais nova."""
    ordem = sorted(materias, key=lambda m: (bool(m.imagem), m.data), reverse=True)
    return sorted(ordem[:limite], key=lambda m: m.data)


# ---------------------------------------------------------------- card

def _fonte(nome: str, tamanho: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTES / nome), tamanho)


def _foto(url: str) -> Image.Image | None:
    if not url.startswith(("http://", "https://")):
        return None
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "BomDiaPetropolisBot/1.0"})
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        return img if img.width >= 400 else None
    except Exception as erro:
        log.warning("Foto indisponível (%s): %s", url, erro)
        return None


def _cobrir(img: Image.Image, w: int, h: int) -> Image.Image:
    escala = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * escala), round(img.height * escala)), Image.LANCZOS)
    x = (img.width - w) // 2
    y = max(0, (img.height - h) // 3)  # puxa um pouco para cima, onde costumam estar os rostos
    return img.crop((x, y, x + w, y + h))


def _arte(m: Materia) -> Image.Image:
    """Serra e sol nas cores da editoria, para matérias sem foto (igual ao site)."""
    rnd = random.Random(int(hashlib.sha1(m.slug.encode()).hexdigest()[:8], 16))
    ceu1, ceu2, sol, fundo, frente = rnd.choice(PALETAS.get(m.secao, PALETAS["Cotidiano"]))
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    c1, c2 = Image.new("RGB", (1, 1), ceu1).getpixel((0, 0)), Image.new("RGB", (1, 1), ceu2).getpixel((0, 0))
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(c1, c2)))
    sx, sy, sr = rnd.randint(250, 830), rnd.randint(220, 360), rnd.randint(90, 130)
    d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=sol)

    def serra(base_y: int, amplitude: int, picos: int, cor: str) -> None:
        pontos = [(0, H), (0, base_y + rnd.randint(-20, 30))]
        for i in range(1, picos * 2):
            x = round(W * i / (picos * 2)) + rnd.randint(-30, 30)
            topo = i % 2 == 1
            pontos.append((x, base_y - (rnd.randint(amplitude // 2, amplitude) if topo
                                        else rnd.randint(0, amplitude // 4))))
        pontos += [(W, base_y + rnd.randint(-20, 30)), (W, H)]
        d.polygon(pontos, fill=cor)

    serra(620, 220, rnd.randint(2, 4), fundo)
    serra(760, 190, rnd.randint(2, 3), frente)
    return img


def _quebrar(texto: str, fonte: ImageFont.FreeTypeFont, largura: int) -> list[str]:
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = f"{atual} {palavra}".strip()
        if fonte.getlength(teste) <= largura or not atual:
            atual = teste
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def _sol(d: ImageDraw.ImageDraw, cx: int, cy: int, r: int) -> None:
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=SOL)
    for ang in (-90, -135, -45, 180, 0):
        a = math.radians(ang)
        d.line([(cx + math.cos(a) * r * 1.5, cy + math.sin(a) * r * 1.5),
                (cx + math.cos(a) * r * 2.0, cy + math.sin(a) * r * 2.0)], fill=SOL, width=max(3, r // 3))


def gerar_card(m: Materia) -> Image.Image:
    """Card 1080x1350: foto em tela cheia, degradê escuro, etiqueta da editoria e manchete."""
    cor = COR_SECAO.get(m.secao, COR_SECAO["Cotidiano"])
    foto = _foto(m.imagem)
    base = _cobrir(foto, W, H) if foto else _arte(m)

    margem, altura_rodape = 64, 120

    # Manchete: o maior tamanho que caiba em até 5 linhas
    largura = W - 2 * margem
    for tamanho in (84, 76, 68, 60, 54, 48):
        fonte = _fonte("SourceSans3-ExtraBold.ttf", tamanho)
        linhas = _quebrar(m.titulo, fonte, largura)
        if len(linhas) <= 5:
            break
    linhas = linhas[:6]
    entrelinha = round(tamanho * 1.08)
    y = H - altura_rodape - 56 - entrelinha * len(linhas)
    topo = y - 86  # etiqueta da editoria, logo acima da manchete

    # Degradê escuro que chega quase opaco antes da etiqueta: a manchete fica legível
    # mesmo sobre fotos claras ou cheias de detalhes
    inicio, cheio = topo - 300, topo - 10
    sombra = Image.new("L", (1, H))
    for yy in range(H):
        t = min(1.0, max(0.0, (yy - inicio) / (cheio - inicio)))
        sombra.putpixel((0, yy), round(250 * t ** 1.4))
    escuro = Image.new("RGB", (W, H), "#0d1512")
    base = Image.composite(escuro, base, sombra.resize((W, H)))
    d = ImageDraw.Draw(base)

    for i, linha in enumerate(linhas):
        d.text((margem, y + i * entrelinha), linha, font=fonte, fill="white")

    etiqueta = _fonte("SourceSans3-ExtraBold.ttf", 34)
    rotulo = m.secao.upper()
    larg = etiqueta.getlength(rotulo)
    d.rounded_rectangle([margem, topo, margem + larg + 44, topo + 58], radius=8, fill=cor)
    d.text((margem + 22, topo + 29), rotulo, font=etiqueta, fill="white", anchor="lm")

    # Faixa no rodapé, na cor da editoria, com a marca
    d.rectangle([0, H - altura_rodape, W, H], fill=cor)
    d.rectangle([0, H - altura_rodape, W, H - altura_rodape + 8], fill=SOL)
    _sol(d, margem + 22, H - altura_rodape // 2 + 4, 16)
    marca = _fonte("Fraunces-ExtraBold.ttf", 46)
    d.text((margem + 66, H - altura_rodape // 2 + 4), NOME, font=marca, fill="white", anchor="lm")
    site = _fonte("SourceSans3-SemiBold.ttf", 28)
    d.text((W - margem, H - altura_rodape // 2 + 4), "Leia no site", font=site, fill="#ffffffcc", anchor="rm")

    if foto:
        credito = _fonte("SourceSans3-SemiBold.ttf", 22)
        d.text((W - margem, 48), "Foto: divulgação", font=credito, fill="#ffffffb0", anchor="ra",
               stroke_width=2, stroke_fill="#00000060")
    return base


def gerar_cartoes() -> None:
    PASTA_CARDS.mkdir(parents=True, exist_ok=True)
    lista = pendentes(ler_materias(), ler_estado(), JANELA_CARDS)
    for m in lista:
        gerar_card(m).save(PASTA_CARDS / f"{m.slug}.jpg", "JPEG", quality=88, optimize=True)
    log.info("%d cards gerados em %s", len(lista), PASTA_CARDS)


# ---------------------------------------------------------------- Meta

class Meta:
    def __init__(self, token: str):
        self.token = token
        eu = self._get("me", fields="id,name,instagram_business_account{id,username}")
        self.pagina_id = eu["id"]
        self.pagina_nome = eu.get("name", "")
        ig = eu.get("instagram_business_account") or {}
        self.ig_id = ig.get("id")
        self.ig_nome = ig.get("username", "")

    def _get(self, caminho: str, **params) -> dict:
        resp = requests.get(f"{API}/{caminho}", params={**params, "access_token": self.token}, timeout=60)
        return self._checar(resp)

    def _post(self, caminho: str, **dados) -> dict:
        resp = requests.post(f"{API}/{caminho}", data={**dados, "access_token": self.token}, timeout=120)
        return self._checar(resp)

    @staticmethod
    def _checar(resp: requests.Response) -> dict:
        try:
            corpo = resp.json()
        except ValueError:
            resp.raise_for_status()
            raise
        if "error" in corpo:
            erro = corpo["error"]
            raise RuntimeError(f"{erro.get('message')} (código {erro.get('code')})")
        return corpo

    def facebook(self, imagem: str, texto: str) -> str:
        return self._post(f"{self.pagina_id}/photos", url=imagem, message=texto)["post_id"]

    def instagram(self, imagem: str, legenda: str) -> str:
        if not self.ig_id:
            raise RuntimeError("a Página não tem uma conta profissional do Instagram ligada")
        container = self._post(f"{self.ig_id}/media", image_url=imagem, caption=legenda)["id"]
        for _ in range(20):  # o Instagram processa a imagem antes de publicar
            status = self._get(container, fields="status_code").get("status_code")
            if status == "FINISHED":
                break
            if status in ("ERROR", "EXPIRED"):
                raise RuntimeError(f"o Instagram recusou a imagem ({status})")
            time.sleep(3)
        return self._post(f"{self.ig_id}/media_publish", creation_id=container)["id"]


def _hashtag(texto: str) -> str:
    limpo = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "".join(p[:1].upper() + p[1:] for p in re.split(r"[^A-Za-z0-9]+", limpo))


def textos(m: Materia, link: str) -> tuple[str, str]:
    facebook = f"{m.titulo}\n\n{m.resumo}\n\nLeia a matéria completa: {link}"
    tags = ["Petrópolis", "BomDiaPetrópolis", m.secao] + [t for t in m.tags if "petr" not in t.lower()]
    hashtags, vistos = [], set()
    for t in tags:
        h = _hashtag(t)
        if h and h.lower() not in vistos and len(h) <= 30:
            vistos.add(h.lower())
            hashtags.append("#" + h)
    instagram = (f"{m.titulo}\n\n{m.resumo}\n\n"
                 f"Matéria completa no link da bio.\n\n{' '.join(hashtags[:7])}")
    return facebook, instagram


def postar(teste: bool = False) -> None:
    token = os.environ.get("META_TOKEN", "").strip()
    if not token and not teste:
        log.info("META_TOKEN não configurado: nada a postar nas redes.")
        return
    site = (os.environ.get("SITE_URL") or SITE_PADRAO).rstrip("/") + "/"
    limite = int(os.environ.get("REDES_POR_RODADA") or 3)
    estado = ler_estado()
    escolhidas = escolher(pendentes(ler_materias(), estado, JANELA_POSTAR), limite)
    if not escolhidas:
        log.info("Nenhuma matéria nova para as redes.")
        return
    meta = Meta(token) if token else None
    if meta:
        log.info("Conectado à Página '%s' e ao Instagram @%s", meta.pagina_nome, meta.ig_nome or "(nenhum)")

    for m in escolhidas:
        link = f"{site}{m.url}"
        card = f"{site}redes/{m.slug}.jpg"
        texto_fb, texto_ig = textos(m, link)
        reg = estado.setdefault(m.slug, {})
        if teste:
            log.info("[teste] Postaria: %s\n  card: %s\n--- Facebook ---\n%s\n--- Instagram ---\n%s",
                     m.titulo, card, texto_fb, texto_ig)
            continue
        if requests.head(card, timeout=30).status_code != 200:
            log.warning("Card ainda não está no ar, fica para a próxima: %s", card)
            continue
        reg["quando"] = datetime.now(FUSO).isoformat(timespec="minutes")
        falhou = False
        for rede in redes_ativas():
            if reg.get(rede):
                continue
            try:
                reg[rede] = meta.facebook(card, texto_fb) if rede == "facebook" else meta.instagram(card, texto_ig)
                log.info("Postada no %s: %s", rede, m.titulo)
            except Exception as erro:
                falhou = True
                log.error("Falha no %s (%s): %s", rede, m.titulo, erro)
        if falhou:
            reg["tentativas"] = reg.get("tentativas", 0) + 1
        salvar_estado(estado)


def verificar() -> None:
    token = os.environ.get("META_TOKEN", "").strip()
    if not token:
        sys.exit("Falta o segredo META_TOKEN no GitHub.")
    meta = Meta(token)
    print(f"Página do Facebook: {meta.pagina_nome} (id {meta.pagina_id})")
    if meta.ig_id:
        print(f"Instagram: @{meta.ig_nome} (id {meta.ig_id})")
    else:
        print("Instagram: nenhuma conta profissional ligada a esta Página.")
    print("Tudo certo: o token funciona.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("acao", choices=["cartoes", "postar", "verificar"])
    parser.add_argument("--teste", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.acao == "cartoes":
        gerar_cartoes()
    elif args.acao == "postar":
        postar(args.teste)
    else:
        verificar()


if __name__ == "__main__":
    main()
