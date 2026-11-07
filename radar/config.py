"""Configuração: apps monitorados e taxonomia de temas.

Para incluir outro app, copie o `id=` da URL dele na Google Play
(ex.: play.google.com/store/apps/details?id=br.com.brainweb.ifood).
"""

import os
from enum import Enum

APPS = {
    "iFood": "br.com.brainweb.ifood",
    "Rappi": "com.grability.rappi",
}

MODELO = os.getenv("RADAR_MODELO", "gemini-3.5-flash-lite")
MODELO_RESUMO = os.getenv("RADAR_MODELO_RESUMO", "gemini-3.8-flash")
CAMINHO_BANCO = os.getenv("RADAR_BANCO", "data/radar.duckdb")
VERSAO_PROMPT = "v1"  # mude quando alterar o prompt ou a taxonomia, para comparar resultados


class Tema(str, Enum):
    atraso_entrega = "atraso_entrega"
    entregador = "entregador"
    pedido_errado = "pedido_errado"
    qualidade_produto = "qualidade_produto"
    pagamento_reembolso = "pagamento_reembolso"
    cupons_promocoes = "cupons_promocoes"
    precos_taxas = "precos_taxas"
    atendimento_suporte = "atendimento_suporte"
    bugs_desempenho = "bugs_desempenho"
    usabilidade = "usabilidade"
    conta_cadastro = "conta_cadastro"
    assinatura_clube = "assinatura_clube"
    elogio_geral = "elogio_geral"
    outro = "outro"


ROTULOS_TEMAS = {
    "atraso_entrega": "Atraso na entrega",
    "entregador": "Entregador",
    "pedido_errado": "Pedido errado ou incompleto",
    "qualidade_produto": "Qualidade da comida/produto",
    "pagamento_reembolso": "Pagamento e reembolso",
    "cupons_promocoes": "Cupons e promoções",
    "precos_taxas": "Preços e taxas",
    "atendimento_suporte": "Atendimento e suporte",
    "bugs_desempenho": "Bugs, travamentos e lentidão",
    "usabilidade": "Usabilidade e navegação",
    "conta_cadastro": "Conta, login e cadastro",
    "assinatura_clube": "Assinatura/clube de vantagens",
    "elogio_geral": "Elogio geral",
    "outro": "Outro",
}

DEFINICOES_TEMAS = {
    "atraso_entrega": "pedido demorou, passou do horário previsto, nunca chegou",
    "entregador": "comportamento do entregador, entregou no lugar errado, pediu para descer, não achou o endereço",
    "pedido_errado": "item faltando, trocado, pedido de outra pessoa, embalagem violada",
    "qualidade_produto": "comida fria, ruim, estragada, produto vencido ou danificado",
    "pagamento_reembolso": "cobrança indevida, cartão recusado, estorno, reembolso negado ou demorado",
    "cupons_promocoes": "cupom não funciona, promoção enganosa, falta de desconto",
    "precos_taxas": "preço alto, taxa de entrega ou de serviço, preço diferente do restaurante",
    "atendimento_suporte": "chat de ajuda, atendente, robô, demora ou falta de solução do suporte",
    "bugs_desempenho": "app trava, fecha, lento, erro ao abrir ou finalizar, não carrega",
    "usabilidade": "difícil de achar opções, interface confusa, mudança de layout, filtros",
    "conta_cadastro": "login, senha, conta bloqueada ou banida, verificação, endereço cadastrado",
    "assinatura_clube": "clube ou assinatura de vantagens (ex.: Clube iFood, Rappi Prime), cobrança da assinatura",
    "elogio_geral": "elogio sem problema específico (ótimo app, entrega rápida, adoro)",
    "outro": "nenhum dos temas acima",
}
