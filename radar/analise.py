"""Consultas usadas pelo dashboard. Todas recebem filtros e devolvem DataFrames."""

from __future__ import annotations

import pandas as pd

from .config import ROTULOS_TEMAS


def _filtro(apps, inicio, fim, alias=""):
    p = f"{alias}." if alias else ""
    return (f"{p}app IN (SELECT unnest(?::VARCHAR[])) AND {p}data >= ?::TIMESTAMP "
            f"AND {p}data < ?::TIMESTAMP + INTERVAL 1 DAY"), [list(apps), str(inicio), str(fim)]


def _rotular(df: pd.DataFrame) -> pd.DataFrame:
    if "tema" in df:
        df.insert(df.columns.get_loc("tema") + 1, "tema_nome", df["tema"].map(ROTULOS_TEMAS).fillna(df["tema"]))
    return df


def kpis(con, apps, inicio, fim) -> pd.DataFrame:
    f, p = _filtro(apps, inicio, fim, "a")
    return con.execute(f"""
        SELECT a.app,
               COUNT(*)                                             AS avaliacoes,
               ROUND(AVG(a.nota), 2)                                AS nota_media,
               COUNT(c.avaliacao_id)                                AS classificadas,
               ROUND(100 * AVG((c.sentimento = 'negativo')::INT), 1) AS pct_negativas
        FROM avaliacoes a LEFT JOIN classificacoes c USING (avaliacao_id)
        WHERE {f} GROUP BY 1 ORDER BY lower(a.app)
    """, p).df()


def temas_negativos(con, apps, inicio, fim) -> pd.DataFrame:
    """% das avaliações negativas de cada app que citam cada tema."""
    f, p = _filtro(apps, inicio, fim)
    return _rotular(con.execute(f"""
        WITH neg AS (SELECT * FROM avaliacoes_temas WHERE sentimento = 'negativo' AND {f}),
             tot AS (SELECT app, COUNT(DISTINCT avaliacao_id) AS n FROM neg GROUP BY 1)
        SELECT neg.app, tema, COUNT(DISTINCT avaliacao_id) AS avaliacoes,
               ROUND(100.0 * COUNT(DISTINCT avaliacao_id) / ANY_VALUE(tot.n), 1) AS pct_das_negativas
        FROM neg JOIN tot USING (app)
        WHERE tema NOT IN ('elogio_geral', 'outro')
        GROUP BY 1, 2 ORDER BY pct_das_negativas DESC
    """, p).df())


def impacto_na_nota(con, apps, inicio, fim, minimo: int = 10) -> pd.DataFrame:
    """Nota média das avaliações que citam o tema, comparada à nota média geral do app."""
    f_base, p_base = _filtro(apps, inicio, fim)
    f_tema, p_tema = _filtro(apps, inicio, fim, "t")
    return _rotular(con.execute(f"""
        WITH base AS (SELECT app, AVG(nota) AS media_app FROM avaliacoes WHERE {f_base} GROUP BY 1)
        SELECT t.app, t.tema, COUNT(*) AS avaliacoes, ROUND(AVG(t.nota), 2) AS nota_media_tema,
               ROUND(AVG(t.nota) - ANY_VALUE(b.media_app), 2) AS diferenca_vs_media
        FROM avaliacoes_temas t JOIN base b USING (app)
        WHERE {f_tema} AND t.tema NOT IN ('outro', 'elogio_geral')
        GROUP BY 1, 2 HAVING COUNT(*) >= {int(minimo)} ORDER BY diferenca_vs_media
    """, p_base + p_tema).df())


def tendencia_semanal(con, apps, inicio, fim, tema: str) -> pd.DataFrame:
    """% semanal das avaliações de cada app que citam o tema."""
    f, p = _filtro(apps, inicio, fim, "a")
    return con.execute(f"""
        SELECT a.app, date_trunc('week', a.data)::DATE AS semana, COUNT(*) AS avaliacoes,
               ROUND(100 * AVG(list_contains(c.temas, ?)::INT), 1) AS pct_com_tema
        FROM avaliacoes a JOIN classificacoes c USING (avaliacao_id)
        WHERE {f} GROUP BY 1, 2 HAVING COUNT(*) >= 5 ORDER BY 2, 1
    """, [tema, *p]).df()


def exemplos(con, apps, inicio, fim, tema: str, limite: int = 20) -> pd.DataFrame:
    f, p = _filtro(apps, inicio, fim)
    return con.execute(f"""
        SELECT data::DATE AS data, app, nota, problema, texto
        FROM avaliacoes_temas WHERE tema = ? AND sentimento <> 'positivo' AND {f}
        ORDER BY curtidas DESC, data DESC LIMIT {int(limite)}
    """, [tema, *p]).df()


def periodo(con) -> tuple:
    return con.execute("SELECT MIN(data)::DATE, MAX(data)::DATE FROM avaliacoes").fetchall()[0]
