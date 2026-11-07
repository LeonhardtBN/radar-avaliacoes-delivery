"""Resumo executivo para o time de produto, escrito pelo Gemini a partir de números AGREGADOS."""

from __future__ import annotations

from .config import MODELO_RESUMO
from .gemini import ESPERAS_LIMITE_TAXA, gerar

PROMPT = """Você é analista de produto de um app de delivery. Escreva em português do Brasil,
para o time de produto, um resumo com no máximo 5 bullets curtos:
- os problemas que mais aparecem nas avaliações negativas, com os percentuais;
- os temas que mais derrubam a nota, com a diferença;
- diferenças relevantes entre os apps, se houver mais de um;
- 1 ou 2 hipóteses de ação para investigar, marcadas como hipótese.
Use SOMENTE os números das tabelas. Não invente dados."""


def gerar_resumo(cliente, kpis, temas, impacto, exemplos_por_tema: dict[str, list[str]] | None = None,
                 modelo: str = MODELO_RESUMO, esperas=ESPERAS_LIMITE_TAXA) -> str:
    from google.genai import types

    partes = [
        "KPIs por app:\n" + kpis.to_csv(index=False),
        "Temas nas avaliações negativas (% das negativas de cada app):\n"
        + temas.drop(columns=["tema"], errors="ignore").head(20).to_csv(index=False),
        "Impacto na nota (nota média de quem cita o tema vs média do app):\n"
        + impacto.drop(columns=["tema"], errors="ignore").head(15).to_csv(index=False),
    ]
    if exemplos_por_tema:
        partes.append("Problemas resumidos mais citados:\n" + "\n".join(
            f"- {t}: " + "; ".join(ex[:5]) for t, ex in exemplos_por_tema.items()))
    retorno = gerar(cliente, modelo, "\n\n".join(partes), types.GenerateContentConfig(system_instruction=PROMPT),
                    esperas=esperas)
    return (retorno.text or "").strip()
