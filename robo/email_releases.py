"""Lê releases enviados para a caixa de e-mail do portal (IMAP, ex.: Gmail).

Configuração por variáveis de ambiente (segredos no GitHub):
  EMAIL_USUARIO     endereço da caixa, ex.: redacao.bomdiapetropolis@gmail.com
  EMAIL_SENHA_APP   senha de app do Gmail (não é a senha normal da conta)
  EMAIL_SERVIDOR    opcional, padrão imap.gmail.com
Sem essas variáveis, a fonte de e-mail é simplesmente pulada.
"""

from __future__ import annotations

import email
import imaplib
import logging
import os
from datetime import date, timedelta
from email.header import decode_header, make_header
from email.message import Message

from bs4 import BeautifulSoup

from .coletar import MAX_CARACTERES_TEXTO, Candidata

log = logging.getLogger(__name__)

DIAS_PARA_TRAS = 3
MAX_EMAILS = 30


def _assunto(msg: Message) -> str:
    return str(make_header(decode_header(msg.get("Subject", "")))).strip()


def _corpo(msg: Message) -> str:
    texto_plano, html = "", ""
    partes = msg.walk() if msg.is_multipart() else [msg]
    for parte in partes:
        if parte.get_content_disposition() == "attachment":
            continue
        tipo = parte.get_content_type()
        if tipo not in ("text/plain", "text/html"):
            continue
        dados = parte.get_payload(decode=True) or b""
        conteudo = dados.decode(parte.get_content_charset() or "utf-8", errors="replace")
        if tipo == "text/plain" and not texto_plano:
            texto_plano = conteudo
        elif tipo == "text/html" and not html:
            html = conteudo
    if not texto_plano and html:
        texto_plano = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    return texto_plano.strip()[:MAX_CARACTERES_TEXTO]


def coletar_emails(fonte: dict, ja_vistas: set[str]) -> list[Candidata]:
    usuario = os.environ.get("EMAIL_USUARIO", "").strip()
    senha = os.environ.get("EMAIL_SENHA_APP", "").replace(" ", "")
    if not usuario or not senha:
        log.info("%s: e-mail não configurado, pulando", fonte["nome"])
        return []
    servidor = os.environ.get("EMAIL_SERVIDOR", "").strip() or "imap.gmail.com"
    remetentes = [r.lower() for r in fonte.get("remetentes", [])]

    desde = (date.today() - timedelta(days=DIAS_PARA_TRAS)).strftime("%d-%b-%Y")
    candidatas: list[Candidata] = []
    nesta_rodada: set[str] = set()
    with imaplib.IMAP4_SSL(servidor) as imap:
        imap.login(usuario, senha)
        imap.select("INBOX", readonly=True)
        _, dados = imap.search(None, "SINCE", desde)
        ids = dados[0].split()[-MAX_EMAILS:]
        for num in ids:
            _, partes = imap.fetch(num, "(BODY.PEEK[])")
            msg = email.message_from_bytes(partes[0][1])
            chave = "email:" + (msg.get("Message-ID") or num.decode()).strip()
            if chave in ja_vistas or chave in nesta_rodada:
                continue
            nesta_rodada.add(chave)
            remetente = msg.get("From", "").lower()
            if remetentes and not any(r in remetente for r in remetentes):
                continue
            corpo = _corpo(msg)
            if len(corpo) < 200:
                continue
            candidatas.append(
                Candidata(fonte["nome"], chave, _assunto(msg), corpo, fonte.get("secao_sugerida", ""))
            )
    log.info("%s: %d releases novos", fonte["nome"], len(candidatas))
    return candidatas
