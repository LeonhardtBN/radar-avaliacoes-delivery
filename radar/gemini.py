"""Chamada ao Gemini com espera automática quando o limite do plano gratuito (429) é atingido."""

from __future__ import annotations

import re
import time

ESPERAS_LIMITE_TAXA = (10, 30, 60)


def cliente_padrao():
    from google import genai  # importado aqui para os testes rodarem sem a chave

    return genai.Client()  # lê GEMINI_API_KEY do ambiente


def gerar(cliente, modelo: str, conteudos, config, esperas=ESPERAS_LIMITE_TAXA, log=None):
    from google.genai import errors

    for espera in (*esperas, None):
        try:
            return cliente.models.generate_content(model=modelo, contents=conteudos, config=config)
        except errors.APIError as e:
            if e.code != 429 or espera is None:
                raise
            sugerida = re.search(r"retry in (\d+(?:\.\d+)?)s", str(e)) or re.search(r"'retryDelay': '(\d+)s'", str(e))
            segundos = float(sugerida.group(1)) + 1 if sugerida else espera
            if log:
                log(f"  limite do plano gratuito atingido; esperando {segundos:.0f}s...")
            time.sleep(segundos)
