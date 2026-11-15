"""Executa uma rodada do robô: coleta, escreve e salva as matérias.

Uso:  python -m robo.main            (publica de verdade)
      python -m robo.main --teste    (só mostra o que faria, sem salvar)
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from .coletar import _baixar, coletar, extrair_imagem
from .escrever import CotaEsgotada, Redator

RAIZ = Path(__file__).resolve().parent.parent
PASTA_MATERIAS = RAIZ / "conteudo" / "materias"
ARQ_VISTAS = RAIZ / "dados" / "vistas.json"
ARQ_AGENDA = RAIZ / "dados" / "agenda.json"
ARQ_REGISTRO = RAIZ / "dados" / "registro.jsonl"
FUSO = ZoneInfo("America/Sao_Paulo")
MAX_MATERIAS_POR_RODADA = 8

log = logging.getLogger("robo")


def _ler_json(caminho: Path, padrao):
    return json.loads(caminho.read_text("utf-8")) if caminho.exists() else padrao


def _salvar_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), "utf-8")


def slug(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")[:70]


def titulos_recentes() -> list[str]:
    arquivos = sorted(PASTA_MATERIAS.glob("*.md"))[-80:]
    titulos = []
    for arq in arquivos:
        m = re.search(r'^titulo: "(.*)"$', arq.read_text("utf-8"), re.M)
        if m:
            titulos.append(m.group(1))
    return titulos


def salvar_materia(m: dict, agora: datetime, foto: str = "") -> Path:
    PASTA_MATERIAS.mkdir(parents=True, exist_ok=True)
    nome = f"{agora:%Y-%m-%d-%H%M}-{slug(m['titulo'])}.md"
    cabecalho = {
        "titulo": m["titulo"],
        "resumo": m["resumo"],
        "secao": m["secao"],
        "tags": m["tags"],
        "data": agora.isoformat(timespec="minutes"),
    }
    if foto:
        cabecalho["imagem"] = foto
    frontmatter = "\n".join(
        f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in cabecalho.items()
    )
    caminho = PASTA_MATERIAS / nome
    caminho.write_text(f"---\n{frontmatter}\n---\n\n{m['texto'].strip()}\n", "utf-8")
    return caminho


def completar_fotos(limite: int = 15) -> None:
    """Busca a foto das matérias antigas que foram publicadas sem imagem."""
    if not ARQ_REGISTRO.exists():
        return
    origem = {}
    for linha in ARQ_REGISTRO.read_text("utf-8").splitlines():
        r = json.loads(linha)
        if r.get("arquivo") and r["url"].startswith("http"):
            origem[r["arquivo"]] = r["url"]
    for arquivo, url in list(origem.items())[-limite:]:
        caminho = PASTA_MATERIAS / arquivo
        if not caminho.exists():
            continue
        texto = caminho.read_text("utf-8")
        cabeca = re.match(r"^---\n(.*?)\n---\n", texto, re.S)
        if not cabeca or re.search(r"^imagem:", cabeca.group(1), re.M):
            continue
        try:
            foto = extrair_imagem(_baixar(url), url)
        except Exception as erro:
            log.warning("Sem foto para %s: %s", arquivo, erro)
            continue
        if foto:
            texto = texto.replace("\n---\n", f"\nimagem: {json.dumps(foto)}\n---\n", 1)
            caminho.write_text(texto, "utf-8")
            log.info("Foto adicionada: %s", arquivo)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--teste", action="store_true", help="não salva nada")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    fontes = yaml.safe_load((RAIZ / "fontes.yaml").read_text("utf-8"))["fontes"]
    guia = (RAIZ / "guia_editorial.md").read_text("utf-8")
    vistas: list[str] = _ler_json(ARQ_VISTAS, [])
    agenda: list[dict] = _ler_json(ARQ_AGENDA, [])
    agora = datetime.now(FUSO)
    recentes = titulos_recentes()

    if not args.teste:
        completar_fotos()
    candidatas = coletar(fontes, set(vistas))
    log.info("%d notícias novas para avaliar", len(candidatas))

    redator = Redator(guia)
    publicadas = 0
    for c in candidatas:
        if publicadas >= MAX_MATERIAS_POR_RODADA:
            break
        try:
            resultado = redator.escrever(c, recentes, agora.date().isoformat())
        except CotaEsgotada as erro:
            log.warning("Limite diário da IA atingido, o resto fica para a próxima rodada: %s", erro)
            break
        if resultado is None:
            continue  # erro temporário: tenta de novo na próxima rodada
        vistas.append(c.url)
        registro = {"quando": agora.isoformat(), "url": c.url, "fonte": c.fonte,
                    "publicar": resultado["publicar"], "motivo": resultado["motivo"]}
        if not resultado["publicar"] or resultado["repetida"]:
            log.info("Descartada: %s (%s)", c.titulo, resultado["motivo"])
        elif args.teste:
            log.info("[teste] Publicaria em %s: %s", resultado["secao"], resultado["titulo"])
            publicadas += 1
        else:
            caminho = salvar_materia(resultado, agora, c.imagem)
            recentes.append(resultado["titulo"])
            registro["arquivo"] = caminho.name
            ja_na_agenda = {(e["nome"].lower(), e["data_inicio"]) for e in agenda}
            for evento in resultado.get("eventos", []):
                chave = (evento["nome"].lower(), evento["data_inicio"])
                if evento["data_inicio"] and evento["local"] and chave not in ja_na_agenda:
                    ja_na_agenda.add(chave)
                    agenda.append({**evento, "materia": caminho.stem})
            publicadas += 1
            log.info("Publicada: %s", resultado["titulo"])
        if not args.teste:
            with ARQ_REGISTRO.open("a", encoding="utf-8") as f:
                f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    if not args.teste:
        _salvar_json(ARQ_VISTAS, vistas[-5000:])
        hoje = agora.date().isoformat()
        agenda = [e for e in agenda if (e["data_fim"] or e["data_inicio"]) >= hoje]
        _salvar_json(ARQ_AGENDA, sorted(agenda, key=lambda e: e["data_inicio"]))
    log.info("Rodada concluída: %d matérias", publicadas)


if __name__ == "__main__":
    main()
