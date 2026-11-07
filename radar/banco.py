"""Armazenamento em DuckDB: avaliações coletadas e classificações do LLM.

Não guardamos nome nem foto de quem avaliou: o projeto só precisa do texto,
da nota, da data e da versão do app.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

SCHEMA = """
CREATE TABLE IF NOT EXISTS avaliacoes (
    avaliacao_id VARCHAR PRIMARY KEY,
    app          VARCHAR NOT NULL,
    nota         INTEGER NOT NULL,
    texto        VARCHAR NOT NULL,
    data         TIMESTAMP NOT NULL,
    versao_app   VARCHAR,
    curtidas     INTEGER,
    coletado_em  TIMESTAMP DEFAULT current_timestamp
);
CREATE TABLE IF NOT EXISTS classificacoes (
    avaliacao_id    VARCHAR PRIMARY KEY,
    sentimento      VARCHAR NOT NULL,
    temas           VARCHAR[] NOT NULL,
    problema        VARCHAR,
    modelo          VARCHAR,
    versao_prompt   VARCHAR,
    classificado_em TIMESTAMP DEFAULT current_timestamp
);
CREATE OR REPLACE VIEW avaliacoes_temas AS
SELECT a.*, c.sentimento, c.problema, unnest(c.temas) AS tema
FROM avaliacoes a JOIN classificacoes c USING (avaliacao_id);
"""


def conectar(caminho: str | Path = ":memory:") -> duckdb.DuckDBPyConnection:
    if str(caminho) != ":memory:":
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(caminho))
    con.execute(SCHEMA)
    return con


def salvar_avaliacoes(con, linhas: list[dict]) -> int:
    """Insere avaliações novas (ignora IDs já existentes). Retorna quantas entraram."""
    if not linhas:
        return 0
    df = pd.DataFrame(linhas)[["avaliacao_id", "app", "nota", "texto", "data", "versao_app", "curtidas"]]
    antes = con.execute("SELECT COUNT(*) FROM avaliacoes").fetchall()[0][0]
    con.register("novas", df)
    con.execute("""
        INSERT INTO avaliacoes (avaliacao_id, app, nota, texto, data, versao_app, curtidas)
        SELECT DISTINCT ON (avaliacao_id) * FROM novas
        WHERE avaliacao_id NOT IN (SELECT avaliacao_id FROM avaliacoes)
    """)
    con.unregister("novas")
    return con.execute("SELECT COUNT(*) FROM avaliacoes").fetchall()[0][0] - antes


def ids_existentes(con, app: str) -> set[str]:
    return {r[0] for r in con.execute("SELECT avaliacao_id FROM avaliacoes WHERE app = ?", [app]).fetchall()}


def pendentes(con, limite: int | None = None, app: str | None = None) -> pd.DataFrame:
    """Avaliações ainda sem classificação, mais recentes primeiro."""
    sql = """
        SELECT a.avaliacao_id, a.app, a.nota, a.texto FROM avaliacoes a
        LEFT JOIN classificacoes c USING (avaliacao_id)
        WHERE c.avaliacao_id IS NULL AND (? IS NULL OR a.app = ?)
        ORDER BY a.data DESC
    """
    if limite:
        sql += f" LIMIT {int(limite)}"
    return con.execute(sql, [app, app]).df()


def salvar_classificacoes(con, linhas: list[dict]) -> None:
    if not linhas:
        return
    df = pd.DataFrame([{
        "avaliacao_id": l["avaliacao_id"], "sentimento": l["sentimento"], "temas": list(l["temas"]),
        "problema": l.get("problema"), "modelo": l.get("modelo"), "versao_prompt": l.get("versao_prompt"),
    } for l in linhas])
    con.register("novas_classificacoes", df)
    con.execute("""
        INSERT OR REPLACE INTO classificacoes (avaliacao_id, sentimento, temas, problema, modelo, versao_prompt)
        SELECT avaliacao_id, sentimento, temas::VARCHAR[], problema, modelo, versao_prompt FROM novas_classificacoes
    """)
    con.unregister("novas_classificacoes")
