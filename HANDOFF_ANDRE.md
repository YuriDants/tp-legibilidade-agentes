# Handoff para análise — André

A coleta experimental está concluída e congelada.

## Estado recebido

- 60 bugs do Refactory;
- 2 condições: Original e Obfuscated;
- 2 agentes: Codex e Antigravity;
- 240 execuções finais;
- 240/240 reparos bem-sucedidos;
- auditoria estrutural: PASS;
- 0 duplicatas;
- 0 harness errors;
- 0 timeouts;
- 0 policy violations;
- 0 protected changes.

SHA-256 do CSV final:

`a036c5d59cbd627c9fce258cd5cfd26c61f0aa013a415a4a7b7a30853dd7d431`

## Ponto importante

A taxa de sucesso apresentou efeito teto:

| Agente | Original | Obfuscated |
| --- | ---: | ---: |
| Codex | 60/60 | 60/60 |
| Antigravity | 60/60 | 60/60 |

Isso significa que não há pares discordantes para um teste de McNemar informativo.

A conclusão não deve ser generalizada para “legibilidade não importa”. O resultado correto é limitado ao conjunto de 60 bugs, aos dois agentes, aos modelos/configurações e ao protocolo utilizados.

## Próximos passos de análise

1. Conferir o CSV e a auditoria.
2. Resumir a taxa de sucesso por agente/condição.
3. Analisar wall-clock time Original × Obfuscated de forma pareada.
4. Analisar patch size Original × Obfuscated.
5. Analisar comandos/turns e métricas internas quando úteis.
6. Tratar tokens somente dentro de cada fornecedor; não comparar totais de Codex e Antigravity diretamente.
7. Produzir 3–4 gráficos finais.
8. Responder RQ1, RQ2 e RQ3.
9. Documentar ameaças à validade.
10. Preparar slides 6–10 e aproximadamente 6 minutos de fala.

## Sugestão de foco dos slides 6–10

6. Agentes e protocolo experimental.
7. Métricas e método de análise.
8. Resultado principal: 100% de sucesso em todas as condições.
9. Esforço: tempo, patches e diferenças relevantes.
10. Conclusões e ameaças à validade.

## Arquivos principais

- `experiment/full_results/full_results.csv`
- `experiment/full_results/audit.txt`
- `experiment/full_results/full_results.sha256`
- `experiment/selected_60_final.csv`
- `experiment/experiment_environment.txt`
- `experiment/agent_prompt.txt`
- `experiment/run_full.py`
- `experiment/audit_full_results.py`

O README do repositório contém a metodologia completa e a divisão da apresentação.
