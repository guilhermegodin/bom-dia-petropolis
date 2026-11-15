"""Números de audiência do GoatCounter para o Mídia Kit.

Precisa da variável GOATCOUNTER_CODIGO (o "código" do site, ex.: bomdiapetropolis) e do
segredo GOATCOUNTER_TOKEN (chave da API com permissão de leitura). Sem eles, ou se a API
falhar, o Mídia Kit sai sem os números de audiência, e o resto do site segue normal.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import requests

DIAS = 30


@dataclass
class Audiencia:
    visitas: int
    media_dia: int
    melhor_dia: int
    paginas_mais_vistas: list[tuple[str, str, int]] = field(default_factory=list)  # (título, caminho, visitas)
    dias_medidos: int = DIAS


def codigo() -> str:
    return os.environ.get("GOATCOUNTER_CODIGO", "").strip().lower()


def buscar() -> Audiencia | None:
    cod, token = codigo(), os.environ.get("GOATCOUNTER_TOKEN", "").strip()
    if not cod or not token:
        return None
    fim = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    ini = fim - timedelta(days=DIAS)
    params = {"start": ini.strftime("%Y-%m-%dT%H:%M:%SZ"), "end": fim.strftime("%Y-%m-%dT%H:%M:%SZ")}
    sessao = requests.Session()
    sessao.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    api = f"https://{cod}.goatcounter.com/api/v0"
    try:
        total = sessao.get(f"{api}/stats/total", params=params, timeout=30)
        total.raise_for_status()
        dados = total.json()
        hits = sessao.get(f"{api}/stats/hits", params={**params, "limit": 15}, timeout=30)
        hits.raise_for_status()
        lista = hits.json().get("hits", [])
    except (requests.RequestException, ValueError) as erro:
        print(f"Aviso: não consegui ler o GoatCounter ({erro}). Mídia Kit sai sem números de audiência.")
        return None
    por_dia = [s.get("daily", 0) for s in dados.get("stats", [])]
    dias_com_visita = [i for i, v in enumerate(por_dia) if v]
    # Conta só a partir do primeiro dia com visita, para a média não cair nos dias antes da medição.
    medidos = len(por_dia) - dias_com_visita[0] if dias_com_visita else 0
    visitas = int(dados.get("total", 0))
    mais_vistas = [
        (h.get("title") or h.get("path", ""), h.get("path", ""), int(h.get("count", 0)))
        for h in lista
        if not h.get("event") and "/materias/" in h.get("path", "")
    ][:5]
    return Audiencia(
        visitas=visitas,
        media_dia=round(visitas / medidos) if medidos else 0,
        melhor_dia=max(por_dia, default=0),
        paginas_mais_vistas=mais_vistas,
        dias_medidos=medidos,
    )
