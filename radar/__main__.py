"""Linha de comando do Radar.

    python -m radar coletar --quantidade 1000        # coleta avaliações novas dos apps em config.APPS
    python -m radar classificar                       # classifica tudo que ainda não foi classificado
    python -m radar amostra                           # dados sintéticos para testar sem API
    python -m radar exportar-rotulos --n 100          # CSV para rotular à mão
    python -m radar avaliar                           # compara LLM x rótulos e grava o relatório
    python -m radar status                            # quantas avaliações coletadas e classificadas
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from . import amostra, avaliacao, banco, classificador, coleta  # noqa: E402
from .config import APPS, CAMINHO_BANCO, MODELO  # noqa: E402

ROTULOS_PADRAO = "data/rotulos.csv"
RELATORIO_PADRAO = "resultados/avaliacao.md"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m radar", description="Radar de Avaliações de apps de delivery")
    ap.add_argument("--banco", default=CAMINHO_BANCO)
    sub = ap.add_subparsers(dest="comando", required=True)

    c = sub.add_parser("coletar", help="coleta avaliações novas da Google Play")
    c.add_argument("--quantidade", type=int, default=1000, help="máximo de avaliações novas por app")
    c.add_argument("--apps", nargs="*", default=list(APPS), help=f"apps de config.APPS ({', '.join(APPS)})")

    k = sub.add_parser("classificar", help="classifica as avaliações pendentes com o Gemini")
    k.add_argument("--limite", type=int, default=None, help="máximo de avaliações nesta rodada")

    sub.add_parser("amostra", help="gera dados sintéticos já classificados (sem API)")

    e = sub.add_parser("exportar-rotulos", help="exporta amostra para rotular à mão")
    e.add_argument("--n", type=int, default=100)
    e.add_argument("--arquivo", default=ROTULOS_PADRAO)

    a = sub.add_parser("avaliar", help="mede a acurácia do LLM contra os rótulos")
    a.add_argument("--arquivo", default=ROTULOS_PADRAO)
    a.add_argument("--relatorio", default=RELATORIO_PADRAO)

    sub.add_parser("status", help="resumo do que há no banco")

    args = ap.parse_args(argv)
    con = banco.conectar(args.banco)

    if args.comando == "coletar":
        for nome in args.apps:
            if nome not in APPS:
                print(f"App desconhecido: {nome}. Opções: {', '.join(APPS)}", file=sys.stderr)
                return 2
            print(f"Coletando {nome} ({APPS[nome]})...")
            n = coleta.coletar(con, nome, APPS[nome], args.quantidade)
            print(f"{nome}: {n} avaliações novas.")
    elif args.comando == "classificar":
        print(f"Classificando com {MODELO}...")
        n = classificador.classificar_pendentes(con, limite=args.limite)
        print(f"{n} avaliações classificadas.")
    elif args.comando == "amostra":
        print(f"{amostra.gerar(con)} avaliações sintéticas criadas em {args.banco}.")
    elif args.comando == "exportar-rotulos":
        n = avaliacao.exportar_rotulos(con, args.arquivo, args.n)
        print(f"{n} avaliações exportadas para {args.arquivo}. Preencha sentimento_manual e temas_manual.")
    elif args.comando == "avaliar":
        m = avaliacao.avaliar(con, args.arquivo)
        texto = avaliacao.relatorio_markdown(m, MODELO)
        Path(args.relatorio).parent.mkdir(parents=True, exist_ok=True)
        Path(args.relatorio).write_text(texto, encoding="utf-8")
        print(texto)
        print(f"Relatório salvo em {args.relatorio}.")
    elif args.comando == "status":
        print(con.execute("""
            SELECT a.app, COUNT(*) AS coletadas, COUNT(c.avaliacao_id) AS classificadas,
                   MIN(a.data)::DATE AS de, MAX(a.data)::DATE AS ate
            FROM avaliacoes a LEFT JOIN classificacoes c USING (avaliacao_id) GROUP BY 1 ORDER BY 1
        """).df().to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
