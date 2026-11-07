# Impacto da Legibilidade de Identificadores no Reparo Automático por Agentes de Código

Trabalho final da disciplina **Manutenção e Evolução de Software**.

> **Status:** experimento final em execução. A infraestrutura, o dataset, a transformação e o piloto já foram concluídos e validados.

## Objetivo

Este trabalho investiga se a redução da informação semântica presente nos identificadores de um programa afeta a capacidade de agentes de código corrigirem bugs automaticamente.

Cada bug é avaliado em duas condições semanticamente equivalentes:

- **Original:** código conforme disponibilizado pelo benchmark;
- **Obfuscated:** mesmo código e mesmo bug, mas com parâmetros e variáveis locais renomeados sistematicamente para identificadores genéricos como `v001`, `v002`, etc.

As funções públicas e interfaces usadas pelos testes são preservadas.

## Perguntas de pesquisa

**RQ1.** A degradação da legibilidade dos identificadores afeta a taxa de sucesso no reparo automático de bugs?

**RQ2.** A degradação da legibilidade afeta o esforço necessário para realizar o reparo, considerando principalmente tempo de execução e tamanho do patch?

**RQ3.** O efeito da legibilidade é semelhante entre diferentes agentes de código?

## Benchmark

Foi utilizado o benchmark **Refactory**, que contém cinco exercícios de programação e submissões corretas e incorretas.

O processo experimental começou com:

- **1.783** programas classificados como `wrong`;
- reprodução automática dos testes de cada exercício;
- tratamento do contexto definido por `global.py`;
- exclusão de casos com timeout, erros de execução ou sem falha reproduzível.

Após essa filtragem, foram obtidos **778 programas elegíveis**.

## Seleção dos 60 bugs

Foram selecionados **60 bugs**, sendo **12 de cada uma das cinco questões**.

A seleção foi estratificada considerando:

- tamanho do programa;
- diversidade na proporção de testes falhando;
- presença de identificadores locais semanticamente informativos.

Para garantir que a manipulação de legibilidade tivesse efeito real, foram utilizados apenas programas com pelo menos **dois identificadores locais potencialmente informativos**.

Manifesto final:

`experiment/selected_60_final.csv`

## Condição Obfuscated

A condição tratada foi gerada automaticamente por um transformador orientado a escopo.

Exemplo conceitual:

```python
def unique_day(day, possible_birthdays):
    count = 0
```

torna-se:

```python
def unique_day(v001, v002):
    v003 = 0
```

A transformação:

- não altera nomes das funções públicas;
- não altera testes;
- não altera a lógica do programa;
- preserva parâmetros usados nominalmente pelos testes;
- preserva identificadores capturados por closures;
- não reformata o código inteiro.

Nos 60 programas foram renomeados **356 identificadores**.

## Validação da transformação

Todos os pares Original/Obfuscated foram executados antes dos experimentos com agentes.

Resultado:

- **60 casos analisados**;
- **60 comportamentos idênticos**;
- **0 diferenças**.

Portanto, cada versão obfuscada reproduz exatamente o mesmo comportamento observável e as mesmas falhas da versão original antes do reparo.

Log:

`experiment/validation_obfuscation.log`

## Agentes avaliados

### OpenAI Codex

- CLI: `codex-cli 0.167.0`
- Modelo: `gpt-6.1-sol`
- Effort: `medium`

### Google Antigravity

- CLI: `1.5.3`
- Modelo: `gemini-4-argon-medium`
- Effort: `medium`

Ambiente experimental completo:

`experiment/experiment_environment.txt`

## Protocolo experimental

Todos os agentes recebem a mesma tarefa.

O agente pode:

- inspecionar os arquivos;
- modificar `bug.py`;
- executar a suíte de testes.

O agente não pode:

- alterar os testes;
- alterar `global.py`;
- modificar `run_tests.py`;
- hardcodar respostas para os inputs fornecidos.

### Critério externo de sucesso

Uma execução só é considerada bem-sucedida quando:

1. `bug.py` foi modificado;
2. todos os testes passam;
3. nenhum arquivo protegido foi alterado.

A declaração textual do agente não é usada como critério de sucesso.

## Piloto

Antes do experimento final foi executado um piloto com:

- 5 bugs;
- 1 bug de cada exercício;
- 2 condições;
- 2 agentes.

Total:

**5 × 2 × 2 = 20 execuções**

Resultado:

**20/20 reparos bem-sucedidos.**

O piloto serviu exclusivamente para validar a infraestrutura e não é usado para responder às perguntas de pesquisa.

## Experimento final

O experimento completo contém:

**60 bugs × 2 condições × 2 agentes = 240 execuções**

As execuções são feitas em ordem pseudoaleatória com seed fixa:

`20261107`

O runner possui checkpoint e pode ser retomado sem repetir execuções concluídas.

Arquivo de resultados ao final:

`experiment/full_results/full_results.csv`

## Métricas coletadas

Quando disponíveis, são registrados:

- sucesso do reparo;
- testes antes e depois;
- wall-clock time;
- tamanho do patch;
- linhas adicionadas e removidas;
- tokens reportados pelo agente;
- comandos/turns;
- timeout;
- alterações de arquivos protegidos;
- erros do harness.

As métricas de tokens de Codex e Antigravity **não devem ser comparadas diretamente entre fornecedores**, pois as ferramentas usam esquemas diferentes para contabilização de cache e raciocínio.

## Análise planejada

A análise principal será **pareada**, porque cada bug existe nas duas condições.

Para cada agente serão contados os casos em que:

- corrigiu Original e Obfuscated;
- corrigiu somente Original;
- corrigiu somente Obfuscated;
- não corrigiu nenhum.

Se houver discordâncias suficientes entre os pares, será considerado o teste de **McNemar** para a variável binária de sucesso.

Também serão analisados:

- wall-clock time;
- tamanho dos patches;
- diferenças entre os dois agentes;
- resultados por exercício, caso tragam informação útil;
- métricas internas de cada agente, sem comparar diretamente taxonomias incompatíveis de tokens.

## Divisão do trabalho

### Yuri — preparação e infraestrutura experimental

Responsabilidades concluídas ou em fase final:

- estudo do benchmark Refactory;
- implementação do runner;
- filtragem dos 1.783 casos;
- seleção dos 60 bugs;
- geração da condição Obfuscated;
- validação Original × Obfuscated;
- configuração dos agentes;
- definição do protocolo;
- construção do harness;
- smoke tests;
- piloto;
- execução dos 240 runs finais.

Na apresentação, esta parte corresponde aproximadamente aos **slides 1–5**:

1. motivação e problema;
2. perguntas de pesquisa;
3. benchmark e seleção;
4. transformação Original × Obfuscated;
5. desenho experimental.

### André — análise dos resultados

Responsabilidades após o término dos 240 runs:

1. auditar `full_results.csv`;
2. confirmar as 240 execuções esperadas;
3. verificar timeouts, erros do harness e violações do protocolo;
4. construir a análise pareada Original × Obfuscated;
5. calcular resultados por agente;
6. analisar wall-clock time;
7. analisar tamanho dos patches;
8. analisar métricas internas quando apropriado;
9. realizar teste estatístico pareado quando aplicável;
10. gerar gráficos e tabelas;
11. elaborar ameaças à validade;
12. preparar os slides 6–10.

Na apresentação, esta parte corresponde aproximadamente aos **slides 6–10**:

6. agentes e protocolo experimental;
7. métricas e método de análise;
8. resultado principal;
9. esforço e diferenças entre agentes;
10. conclusões e ameaças à validade.

## Divisão da apresentação

Planejamento inicial:

- **Yuri:** aproximadamente 6 minutos — slides 1–5;
- **André:** aproximadamente 6 minutos — slides 6–10.

Os dois integrantes devem conhecer o experimento completo e revisar juntos as conclusões finais.

## Reprodutibilidade

O dataset selecionado foi congelado por SHA-256.

Manifesto:

`33004beffa8d42dae8d520b672b90356c2cc3d49455ba4fd933f993c2f508893`

Lista de hashes dos arquivos do dataset:

`e99fc39768f72cbf087cbd5aa7151869a95823bc43ccfaea0a2f06f26c91c5bf`

Esses hashes identificam a versão do dataset utilizada no experimento.

## Status atual

- [x] Tema e RQs
- [x] Benchmark compreendido
- [x] Runner implementado
- [x] 778 casos elegíveis identificados
- [x] 60 bugs selecionados
- [x] Condição Obfuscated gerada
- [x] 356 identificadores renomeados
- [x] Validação 60/60
- [x] Agentes e modelos congelados
- [x] Smoke tests
- [x] Piloto 20/20
- [ ] Experimento final 240/240
- [ ] Auditoria dos resultados
- [ ] Análise estatística
- [ ] Gráficos
- [ ] Slides 1–10
- [ ] Ensaio final

## Observação sobre arquivos grandes

Diretórios de execução, workspaces temporários e logs volumosos não devem ser versionados. O repositório deve manter principalmente:

- scripts;
- manifesto;
- hashes;
- resultados consolidados;
- documentação;
- arquivos de análise;
- apresentação final.
