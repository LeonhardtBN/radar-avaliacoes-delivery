from datetime import datetime, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest
from google.genai import errors

from radar import amostra, analise, avaliacao, banco, classificador, coleta
from radar.classificador import Classificacao, Lote


@pytest.fixture
def con():
    return banco.conectar()


# ---------------------------------------------------------------- coleta

def _pagina(inicio, n, base=datetime(2026, 11, 1)):
    return [{"reviewId": f"r{i}", "userName": "Fulano de Tal", "content": f"texto {i}", "score": 1 + i % 5,
             "at": base - timedelta(hours=i), "thumbsUpCount": i, "reviewCreatedVersion": "1.0"}
            for i in range(inicio, inicio + n)]


class BuscaFalsa:
    def __init__(self, total=450, tamanho=200):
        self.todas, self.tamanho, self.chamadas = _pagina(0, total), tamanho, 0

    def __call__(self, app_id, continuation_token=None):
        self.chamadas += 1
        i = continuation_token or 0
        fim = i + self.tamanho
        return self.todas[i:fim], (fim if fim < len(self.todas) else None)


def test_coleta_pagina_ate_a_quantidade(con):
    busca = BuscaFalsa()
    n = coleta.coletar(con, "iFood", "x", quantidade=300, buscar=busca, pausa=0, log=lambda *_: None)
    assert n == 300 and busca.chamadas == 2


def test_coleta_e_incremental(con):
    coleta.coletar(con, "iFood", "x", quantidade=1000, buscar=BuscaFalsa(total=300), pausa=0, log=lambda *_: None)
    busca = BuscaFalsa(total=300)
    busca.todas = _pagina(-50, 50) + busca.todas  # 50 avaliações mais novas apareceram
    n = coleta.coletar(con, "iFood", "x", quantidade=1000, buscar=busca, pausa=0, log=lambda *_: None)
    assert n == 50 and busca.chamadas == 1  # para ao encontrar o que já tinha


def test_coleta_nao_guarda_dados_pessoais_nem_texto_vazio(con):
    busca = BuscaFalsa(total=3)
    busca.todas[1]["content"] = "   "
    coleta.coletar(con, "iFood", "x", buscar=busca, pausa=0, log=lambda *_: None)
    df = con.execute("SELECT * FROM avaliacoes").df()
    assert len(df) == 2
    assert "Fulano" not in df.to_csv() and not any("r0" == v for v in df["avaliacao_id"])


# ---------------------------------------------------------------- classificação

class ClienteFalso:
    """Imita genai.Client().models. `responder(textos) -> list[Classificacao]` decide a resposta."""

    def __init__(self, responder, falhas_429=0):
        self.responder, self.falhas_429, self.chamadas = responder, falhas_429, []
        self.models = self

    def generate_content(self, *, model, contents, config):
        self.chamadas.append(contents)
        if self.falhas_429:
            self.falhas_429 -= 1
            raise errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
        linhas = [l for l in contents.splitlines() if l.startswith("[")]
        lote = Lote(classificacoes=self.responder(linhas))
        return SimpleNamespace(parsed=lote, text=lote.model_dump_json())


def _todas_negativas(linhas):
    return [Classificacao(n=i, sentimento="negativo", temas=["atraso_entrega"], problema="demorou")
            for i in range(1, len(linhas) + 1)]


def _inserir(con, n):
    banco.salvar_avaliacoes(con, [{"avaliacao_id": f"a{i}", "app": "iFood", "nota": 1, "texto": f"demorou {i}",
                                   "data": datetime(2026, 10, 1) + timedelta(hours=i), "versao_app": "1",
                                   "curtidas": 0} for i in range(n)])


def test_classifica_em_lotes(con):
    _inserir(con, 70)
    cliente = ClienteFalso(_todas_negativas)
    n = classificador.classificar_pendentes(con, cliente, tamanho_lote=30, log=None)
    assert n == 70 and len(cliente.chamadas) == 3
    assert banco.pendentes(con).empty


def test_reenvia_as_que_o_modelo_pulou(con):
    _inserir(con, 10)
    respostas = iter([lambda l: _todas_negativas(l)[:7], _todas_negativas])
    cliente = ClienteFalso(lambda linhas: next(respostas)(linhas))
    n = classificador.classificar_pendentes(con, cliente, log=None)
    assert n == 10 and len(cliente.chamadas) == 2
    assert cliente.chamadas[1].count("[") == 3  # só as 3 que faltaram


def test_ignora_numero_fora_do_lote_e_normaliza_temas(con):
    _inserir(con, 2)
    cliente = ClienteFalso(lambda l: [
        Classificacao(n=1, sentimento="negativo", temas=["outro", "pagamento_reembolso", "pagamento_reembolso"],
                      problema="cobrança dupla"),
        Classificacao(n=99, sentimento="positivo", temas=["elogio_geral"], problema=""),
        Classificacao(n=2, sentimento="positivo", temas=["elogio_geral"], problema="  "),
    ])
    classificador.classificar_pendentes(con, cliente, log=None)
    df = con.execute("SELECT * FROM classificacoes").df().set_index("avaliacao_id")
    assert len(df) == 2  # pendentes vêm do mais recente: n=1 é a1, n=2 é a0
    assert list(df.loc["a1", "temas"]) == ["pagamento_reembolso"] and pd.isna(df.loc["a0", "problema"])


def test_espera_no_limite_do_plano_gratuito(con):
    _inserir(con, 5)
    cliente = ClienteFalso(_todas_negativas, falhas_429=2)
    assert classificador.classificar_pendentes(con, cliente, esperas=(0, 0), log=None) == 5


def test_limite_persistente_vira_erro(con):
    _inserir(con, 5)
    with pytest.raises(errors.ClientError):
        classificador.classificar_pendentes(con, ClienteFalso(_todas_negativas, falhas_429=9), esperas=(0,), log=None)


# ---------------------------------------------------------------- análise e avaliação

@pytest.fixture
def con_amostra():
    c = banco.conectar()
    amostra.gerar(c, por_app=300)
    return c


def test_analises_com_amostra(con_amostra):
    c, apps = con_amostra, ["iFood", "Rappi"]
    ini, fim = analise.periodo(c)
    k = analise.kpis(c, apps, ini, fim)
    assert set(k["app"]) == set(apps) and (k["avaliacoes"] == 300).all()
    t = analise.temas_negativos(c, apps, ini, fim)
    assert t["pct_das_negativas"].between(0, 100).all() and "elogio_geral" not in set(t["tema"])
    imp = analise.impacto_na_nota(c, apps, ini, fim)
    assert (imp["diferenca_vs_media"] < 0).any() and "tema_nome" in imp
    assert not analise.tendencia_semanal(c, apps, ini, fim, "atraso_entrega").empty
    ex = analise.exemplos(c, apps, ini, fim, "cupons_promocoes", 5)
    assert len(ex) == 5 and set(ex["app"]) <= set(apps)


def test_filtro_de_app_e_periodo(con_amostra):
    ini, fim = analise.periodo(con_amostra)
    so_ifood = analise.kpis(con_amostra, ["iFood"], fim, fim)
    assert list(so_ifood["app"]) == ["iFood"] and so_ifood["avaliacoes"][0] < 300


def test_avaliacao_compara_com_rotulos(con_amostra, tmp_path):
    arq = tmp_path / "rotulos.csv"
    assert avaliacao.exportar_rotulos(con_amostra, arq, n=40) == 40
    df = pd.read_csv(arq, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    gab = con_amostra.execute("SELECT avaliacao_id, sentimento, temas FROM classificacoes").df().set_index("avaliacao_id")
    df["sentimento_manual"] = df["avaliacao_id"].map(gab["sentimento"])
    df["temas_manual"] = df["avaliacao_id"].map(lambda i: ";".join(gab.loc[i, "temas"]))
    df.loc[0, "sentimento_manual"] = "neutro" if df.loc[0, "sentimento_manual"] != "neutro" else "positivo"
    df.to_csv(arq, index=False, encoding="utf-8-sig")

    m = avaliacao.avaliar(con_amostra, arq)
    assert m["n"] == 40 and m["acuracia_sentimento_llm"] == pytest.approx(39 / 40, abs=1e-3)
    assert m["temas_f1_micro"] == 1.0
    assert "| Acurácia de sentimento, LLM | 97.5% |" in avaliacao.relatorio_markdown(m, "teste")


def test_avaliacao_recusa_tema_desconhecido(con_amostra, tmp_path):
    arq = tmp_path / "r.csv"
    avaliacao.exportar_rotulos(con_amostra, arq, n=3)
    df = pd.read_csv(arq, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df["sentimento_manual"], df["temas_manual"] = "negativo", "tema_inventado"
    df.to_csv(arq, index=False, encoding="utf-8-sig")
    with pytest.raises(ValueError, match="tema_inventado"):
        avaliacao.avaliar(con_amostra, arq)


def test_cli_amostra_e_status(tmp_path, capsys):
    from radar.__main__ import main

    caminho = str(tmp_path / "r.duckdb")
    assert main(["--banco", caminho, "amostra"]) == 0
    assert main(["--banco", caminho, "status"]) == 0
    assert "iFood" in capsys.readouterr().out
