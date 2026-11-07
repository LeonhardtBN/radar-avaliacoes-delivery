# Avaliação da classificação

Amostra de **100 avaliações** rotuladas manualmente. Modelo: `gemini-3.5-flash-lite`.

| Métrica | Resultado |
|---|---|
| Acurácia de sentimento, LLM | 97.0% |
| Acurácia de sentimento, baseline pelas estrelas | 92.0% |
| Temas: precisão (micro) | 86.2% |
| Temas: recall (micro) | 88.1% |
| Temas: F1 (micro) | 87.2% |
| Avaliações com pelo menos 1 tema em comum com o rótulo | 92.0% |

## Por tema

| tema                          |   suporte |   precisao |   recall |   f1 |
|:------------------------------|----------:|-----------:|---------:|-----:|
| Elogio geral                  |        44 |       0.93 |     0.98 | 0.96 |
| Outro                         |        13 |       1    |     0.46 | 0.63 |
| Pagamento e reembolso         |        13 |       0.85 |     0.85 | 0.85 |
| Atraso na entrega             |        11 |       0.92 |     1    | 0.96 |
| Atendimento e suporte         |        10 |       0.64 |     0.9  | 0.75 |
| Cupons e promoções            |        10 |       1    |     1    | 1    |
| Bugs, travamentos e lentidão  |         9 |       0.9  |     1    | 0.95 |
| Usabilidade e navegação       |         7 |       0.5  |     0.57 | 0.53 |
| Preços e taxas                |         6 |       0.83 |     0.83 | 0.83 |
| Pedido errado ou incompleto   |         5 |       1    |     0.8  | 0.89 |
| Conta, login e cadastro       |         3 |       0.75 |     1    | 0.86 |
| Entregador                    |         3 |       0.75 |     1    | 0.86 |
| Assinatura/clube de vantagens |         1 |       1    |     1    | 1    |
