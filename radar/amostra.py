"""Amostra SINTÉTICA para testar o projeto sem coletar nem gastar cota da API.

Gera avaliações inventadas a partir de modelos de frases e já grava a
classificação "correta" de cada uma. Os números NÃO representam os apps reais.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from . import banco

FRASES = {
    "atraso_entrega": ["Pedido demorou mais de 1 hora e chegou frio", "Passou muito do horário previsto",
                       "O pedido nunca chegou e o status ficou parado"],
    "entregador": ["O entregador pediu para eu descer e foi grosso", "Entregador marcou como entregue e não entregou",
                   "Entregador não achou meu endereço e cancelou"],
    "pedido_errado": ["Veio faltando a bebida do meu pedido", "Recebi o pedido de outra pessoa",
                      "Embalagem chegou violada e faltando item"],
    "qualidade_produto": ["Comida chegou fria e sem gosto", "Produto do mercado veio vencido"],
    "pagamento_reembolso": ["Fui cobrado duas vezes e não devolveram", "O reembolso está demorando semanas",
                            "Cartão recusado sem motivo na hora de pagar"],
    "cupons_promocoes": ["O cupom não aplica no carrinho", "Promoção enganosa, o desconto some no final",
                         "Cupom de primeira compra não funcionou"],
    "precos_taxas": ["Taxa de entrega absurda", "Preço no app é mais caro que no restaurante",
                     "Cobram taxa de serviço em tudo"],
    "atendimento_suporte": ["O chat de ajuda é só robô e não resolve", "Suporte demora e encerra a conversa sozinho"],
    "bugs_desempenho": ["App trava na hora de finalizar o pedido", "Depois da atualização o app fecha sozinho",
                        "Muito lento para carregar os restaurantes"],
    "usabilidade": ["Difícil achar onde muda o endereço", "O novo layout ficou confuso"],
    "conta_cadastro": ["Minha conta foi bloqueada sem explicação", "Não consigo fazer login, código não chega"],
    "assinatura_clube": ["Cancelei a assinatura e continuam cobrando", "O clube não vale a pena, frete grátis sumiu"],
}
ELOGIOS = ["Ótimo app, entrega rápida", "Adoro, uso todo dia", "Muito prático e sempre chega certinho",
           "Melhor app de delivery", "Atendimento resolveu meu problema rápido"]

PESOS = {
    "iFood": {"atraso_entrega": 14, "entregador": 9, "pedido_errado": 8, "qualidade_produto": 5,
              "pagamento_reembolso": 8, "cupons_promocoes": 10, "precos_taxas": 12, "atendimento_suporte": 11,
              "bugs_desempenho": 7, "usabilidade": 4, "conta_cadastro": 6, "assinatura_clube": 6},
    "Rappi": {"atraso_entrega": 16, "entregador": 8, "pedido_errado": 9, "qualidade_produto": 5,
              "pagamento_reembolso": 12, "cupons_promocoes": 13, "precos_taxas": 9, "atendimento_suporte": 12,
              "bugs_desempenho": 9, "usabilidade": 4, "conta_cadastro": 5, "assinatura_clube": 3},
}


def gerar(con, por_app: int = 800, semanas: int = 16, seed: int = 42, hoje: datetime | None = None) -> int:
    rnd = random.Random(seed)
    hoje = hoje or datetime(2026, 11, 1)
    avaliacoes, classificacoes = [], []
    for app, pesos in PESOS.items():
        temas, w = zip(*pesos.items())
        for i in range(por_app):
            data = hoje - timedelta(days=rnd.uniform(0, semanas * 7))
            semana = (hoje - data).days // 7
            prob_elogio = 0.45 if app == "iFood" else 0.38
            if rnd.random() < prob_elogio:
                texto, sent, ts, nota = rnd.choice(ELOGIOS), "positivo", ["elogio_geral"], rnd.choice([4, 5, 5, 5])
            else:
                w_ajustado = [p * (3 if (t == "bugs_desempenho" and app == "iFood" and semana in (2, 3)) else 1)
                              for t, p in zip(temas, w)]  # pico de bugs após uma "atualização"
                ts = list(dict.fromkeys(rnd.choices(temas, w_ajustado, k=rnd.choice([1, 1, 2]))))
                texto = ". ".join(rnd.choice(FRASES[t]) for t in ts)
                sent, nota = "negativo", rnd.choice([1, 1, 1, 2, 2, 3])
                if rnd.random() < 0.08:
                    sent, nota = "neutro", 3
            aid = f"amostra-{app}-{i}"
            avaliacoes.append({"avaliacao_id": aid, "app": app, "nota": nota, "texto": texto, "data": data,
                               "versao_app": f"10.{semanas - semana}.0", "curtidas": rnd.randint(0, 20)})
            classificacoes.append({"avaliacao_id": aid, "sentimento": sent, "temas": ts,
                                   "problema": None if sent == "positivo" else texto.split(".")[0].lower()[:80],
                                   "modelo": "amostra", "versao_prompt": "amostra"})
    n = banco.salvar_avaliacoes(con, avaliacoes)
    banco.salvar_classificacoes(con, classificacoes)
    return n
