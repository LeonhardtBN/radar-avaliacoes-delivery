"""Mede a qualidade da classificação do LLM contra rótulos feitos à mão.

Fluxo:
1. `python -m radar exportar-rotulos` gera um CSV com uma amostra aleatória.
2. Você preenche `sentimento_manual` e `temas_manual` (códigos separados por `;`).
3. `python -m radar avaliar` compara com o LLM e com um baseline ingênuo
   (sentimento pela quantidade de estrelas) e grava um relatório em markdown.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import ROTULOS_TEMAS, Tema

COLUNAS = ["avaliacao_id", "app", "nota", "texto", "sentimento_manual", "temas_manual"]
TEMAS_VALIDOS = {t.value for t in Tema}


def exportar_rotulos(con, caminho: str | Path, n: int = 100, seed: int = 7) -> int:
    df = con.execute("""
        SELECT a.avaliacao_id, a.app, a.nota, a.texto FROM avaliacoes a
        JOIN classificacoes c USING (avaliacao_id)
        ORDER BY hash(a.avaliacao_id || ?) LIMIT ?
    """, [str(seed), n]).df()
    df["sentimento_manual"], df["temas_manual"] = "", ""
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    df[COLUNAS].to_csv(caminho, index=False, encoding="utf-8-sig")  # utf-8-sig abre certo no Excel
    return len(df)


def _ler_rotulos(caminho) -> pd.DataFrame:
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df = df[(df["sentimento_manual"].str.strip() != "") & (df["temas_manual"].str.strip() != "")].copy()
    df["sentimento_manual"] = df["sentimento_manual"].str.strip().str.lower()
    df["temas_manual"] = df["temas_manual"].apply(
        lambda s: {t.strip().lower() for t in s.replace(",", ";").split(";") if t.strip()})
    invalidos = set().union(*df["temas_manual"]) - TEMAS_VALIDOS if len(df) else set()
    if invalidos:
        raise ValueError(f"Temas desconhecidos no CSV: {', '.join(sorted(invalidos))}. "
                         f"Use: {', '.join(sorted(TEMAS_VALIDOS))}")
    return df


def _sentimento_por_estrelas(nota: int) -> str:
    return "negativo" if nota <= 2 else "neutro" if nota == 3 else "positivo"


def avaliar(con, caminho_rotulos: str | Path) -> dict:
    rot = _ler_rotulos(caminho_rotulos)
    if rot.empty:
        raise ValueError("Nenhuma linha rotulada no CSV (preencha sentimento_manual e temas_manual).")
    llm = con.execute("SELECT avaliacao_id, sentimento, temas FROM classificacoes").df()
    df = rot.merge(llm, on="avaliacao_id", how="inner")
    df["temas_llm"] = df["temas"].apply(set)

    acc_llm = (df["sentimento"] == df["sentimento_manual"]).mean()
    acc_base = (df["nota"].astype(int).map(_sentimento_por_estrelas) == df["sentimento_manual"]).mean()

    linhas, vp_tot, fp_tot, fn_tot = [], 0, 0, 0
    for tema in sorted(TEMAS_VALIDOS):
        real = df["temas_manual"].apply(lambda s: tema in s)
        prev = df["temas_llm"].apply(lambda s: tema in s)
        vp, fp, fn = int((real & prev).sum()), int((~real & prev).sum()), int((real & ~prev).sum())
        vp_tot, fp_tot, fn_tot = vp_tot + vp, fp_tot + fp, fn_tot + fn
        if real.sum() == 0 and prev.sum() == 0:
            continue
        p = vp / (vp + fp) if vp + fp else 0.0
        r = vp / (vp + fn) if vp + fn else 0.0
        linhas.append({"tema": ROTULOS_TEMAS[tema], "suporte": int(real.sum()), "precisao": round(p, 2),
                       "recall": round(r, 2), "f1": round(2 * p * r / (p + r), 2) if p + r else 0.0})

    p_micro = vp_tot / (vp_tot + fp_tot) if vp_tot + fp_tot else 0.0
    r_micro = vp_tot / (vp_tot + fn_tot) if vp_tot + fn_tot else 0.0
    return {
        "n": len(df),
        "acuracia_sentimento_llm": round(acc_llm, 3),
        "acuracia_sentimento_estrelas": round(acc_base, 3),
        "temas_precisao_micro": round(p_micro, 3),
        "temas_recall_micro": round(r_micro, 3),
        "temas_f1_micro": round(2 * p_micro * r_micro / (p_micro + r_micro), 3) if p_micro + r_micro else 0.0,
        "pct_tema_principal_correto": round(
            df.apply(lambda r: len(r["temas_llm"] & r["temas_manual"]) > 0, axis=1).mean(), 3),
        "por_tema": pd.DataFrame(linhas).sort_values("suporte", ascending=False),
    }


def relatorio_markdown(m: dict, modelo: str) -> str:
    pct = lambda x: f"{100 * x:.1f}%"  # noqa: E731
    return f"""# Avaliação da classificação

Amostra de **{m['n']} avaliações** rotuladas manualmente. Modelo: `{modelo}`.

| Métrica | Resultado |
|---|---|
| Acurácia de sentimento, LLM | {pct(m['acuracia_sentimento_llm'])} |
| Acurácia de sentimento, baseline pelas estrelas | {pct(m['acuracia_sentimento_estrelas'])} |
| Temas: precisão (micro) | {pct(m['temas_precisao_micro'])} |
| Temas: recall (micro) | {pct(m['temas_recall_micro'])} |
| Temas: F1 (micro) | {pct(m['temas_f1_micro'])} |
| Avaliações com pelo menos 1 tema em comum com o rótulo | {pct(m['pct_tema_principal_correto'])} |

## Por tema

{m['por_tema'].to_markdown(index=False)}
"""
