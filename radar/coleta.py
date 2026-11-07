"""Coleta incremental de avaliações públicas da Google Play.

Para de paginar quando atinge a quantidade pedida ou quando encontra
avaliações que já estão no banco (as mais recentes vêm primeiro).
"""

from __future__ import annotations

import hashlib
import time

from . import banco


def _buscar_google_play(app_id, continuation_token=None, tamanho=200):
    from google_play_scraper import Sort, reviews

    return reviews(app_id, lang="pt", country="br", sort=Sort.NEWEST, count=tamanho,
                   continuation_token=continuation_token)


def _converter(app: str, bruta: dict) -> dict | None:
    texto = (bruta.get("content") or "").strip()
    if not texto:
        return None
    return {
        # hash do ID original: estável para deduplicar, sem expor o identificador da Google
        "avaliacao_id": hashlib.sha1(f"{app}:{bruta['reviewId']}".encode()).hexdigest()[:16],
        "app": app,
        "nota": int(bruta["score"]),
        "texto": texto,
        "data": bruta["at"],
        "versao_app": bruta.get("reviewCreatedVersion") or bruta.get("appVersion"),
        "curtidas": int(bruta.get("thumbsUpCount") or 0),
    }


def coletar(con, app: str, app_id: str, quantidade: int = 1000, buscar=_buscar_google_play,
            pausa: float = 1.0, log=print) -> int:
    """Coleta até `quantidade` avaliações novas do app. Retorna quantas foram salvas."""
    existentes = banco.ids_existentes(con, app)
    token, total_novas = None, 0
    while total_novas < quantidade:
        lote, token = buscar(app_id, continuation_token=token)
        if not lote:
            break
        convertidas = [c for c in (_converter(app, b) for b in lote) if c]
        novas = [c for c in convertidas if c["avaliacao_id"] not in existentes][: quantidade - total_novas]
        total_novas += banco.salvar_avaliacoes(con, novas)
        existentes.update(c["avaliacao_id"] for c in novas)
        log(f"  {app}: {total_novas}/{quantidade} novas")
        if len(novas) < len(convertidas) or token is None:
            break  # chegou ao que já tinha sido coletado, ou acabaram as páginas
        time.sleep(pausa)
    return total_novas
