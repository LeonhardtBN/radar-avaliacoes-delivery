"""Classificação das avaliações em lote com o Gemini.

Cada chamada envia um lote de avaliações numeradas (1..N) e recebe, em JSON
validado por schema, sentimento, até 3 temas de uma taxonomia fixa e um resumo
curto do problema. Lotes reduzem o número de chamadas (importante no plano
gratuito). Avaliações que o modelo esquecer de devolver são reenviadas.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from . import banco
from .config import DEFINICOES_TEMAS, MODELO, VERSAO_PROMPT, Tema
from .gemini import ESPERAS_LIMITE_TAXA, cliente_padrao, gerar

TAMANHO_LOTE = 30
MAX_CARACTERES = 600


class Sentimento(str, Enum):
    positivo = "positivo"
    neutro = "neutro"
    negativo = "negativo"


class Classificacao(BaseModel):
    n: int = Field(description="Número da avaliação no lote.")
    sentimento: Sentimento
    temas: list[Tema] = Field(description="De 1 a 3 temas, do mais para o menos importante.")
    problema: str = Field(description="Problema principal em até 12 palavras; vazio se for elogio.")


class Lote(BaseModel):
    classificacoes: list[Classificacao]


_LISTA_TEMAS = "\n".join(f"- {t}: {d}" for t, d in DEFINICOES_TEMAS.items())

PROMPT = f"""Você analisa avaliações de apps de delivery na Google Play para o time de produto.
Para CADA avaliação numerada, devolva: n, sentimento, temas e problema.

Temas permitidos (use só estes códigos):
{_LISTA_TEMAS}

Regras:
- Sentimento pelo texto, não pela nota: a nota às vezes contradiz o texto.
- De 1 a 3 temas por avaliação. Use "elogio_geral" só se não houver nenhum problema citado.
- Use "outro" só se nenhum tema se aplicar.
- `problema`: frase curta e específica em português (ex.: "cupom de primeira compra não aplicado"); vazio se for elogio.
- Devolva exatamente uma classificação para cada número recebido.
"""


def _montar_lote(df) -> str:
    linhas = []
    for i, r in enumerate(df.itertuples(), start=1):
        texto = " ".join(r.texto.split())[:MAX_CARACTERES]
        linhas.append(f"[{i}] app={r.app} nota={r.nota}: {texto}")
    return "\n".join(linhas)


def _normalizar(c: Classificacao) -> dict:
    temas = list(dict.fromkeys(t.value for t in c.temas))[:3] or [Tema.outro.value]
    if len(temas) > 1:
        temas = [t for t in temas if t != Tema.outro.value] or temas
    return {"sentimento": c.sentimento.value, "temas": temas, "problema": c.problema.strip() or None}


def classificar_lote(cliente, df, modelo: str = MODELO, esperas=ESPERAS_LIMITE_TAXA, log=None) -> dict[str, dict]:
    """Classifica um DataFrame (avaliacao_id, app, nota, texto). Retorna {avaliacao_id: classificação}."""
    from google.genai import types

    config = types.GenerateContentConfig(
        system_instruction=PROMPT, response_mime_type="application/json", response_schema=Lote,
    )
    retorno = gerar(cliente, modelo, _montar_lote(df), config, esperas=esperas, log=log)
    lote = retorno.parsed if isinstance(getattr(retorno, "parsed", None), Lote) else Lote.model_validate_json(retorno.text)

    ids = list(df["avaliacao_id"])
    resultado = {}
    for c in lote.classificacoes:
        if 1 <= c.n <= len(ids) and ids[c.n - 1] not in resultado:
            resultado[ids[c.n - 1]] = _normalizar(c)
    return resultado


def classificar_pendentes(con, cliente=None, limite: int | None = None, modelo: str = MODELO,
                          tamanho_lote: int = TAMANHO_LOTE, esperas=ESPERAS_LIMITE_TAXA, log=print) -> int:
    """Classifica tudo que ainda não foi classificado. Retorna quantas foram salvas."""
    cliente = cliente or cliente_padrao()
    df = banco.pendentes(con, limite=limite)
    total = 0
    for inicio in range(0, len(df), tamanho_lote):
        lote = df.iloc[inicio:inicio + tamanho_lote]
        resultado = classificar_lote(cliente, lote, modelo, esperas, log)
        faltando = lote[~lote["avaliacao_id"].isin(resultado)]
        if len(faltando):  # o modelo pulou alguma: uma segunda tentativa só com elas
            resultado.update(classificar_lote(cliente, faltando, modelo, esperas, log))
        banco.salvar_classificacoes(con, [
            {"avaliacao_id": i, **c, "modelo": modelo, "versao_prompt": VERSAO_PROMPT} for i, c in resultado.items()
        ])
        total += len(resultado)
        if log:
            log(f"  classificadas {total}/{len(df)}")
    return total
