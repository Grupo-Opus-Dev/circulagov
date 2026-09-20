# Análise do Log de Segurança (Issue 5.4)

Este documento descreve o comando de análise que resume, a partir do
log de segurança, as tentativas de login com falha por usuário, os
bloqueios por força bruta e os eventos de 2FA — depende dos eventos
já registrados pelas issues 5.1 e 5.2, documentados em
`docs/LOGS_AUTENTICACAO.md`.

## O comando

`python manage.py analisar_logs` (em `auditoria/management/commands/analisar_logs.py`)
lê o arquivo `logs/seguranca.log` linha por linha e usa expressões
regulares para extrair o logger, a mensagem e o `username` de cada
uma, ignorando a assinatura de integridade (`| mac=...`) adicionada
pela issue 5.3, que não é relevante para esta análise.

Ele reconhece três grupos de evento:

- **Tentativas de login com falha**, contadas por usuário (logger
  `seguranca.autenticacao`, mensagem "tentativa de login com falha").
- **Bloqueios por força bruta**, contados por usuário (mesmo logger,
  mensagem "bloqueio por forca bruta").
- **Eventos de 2FA**, por usuário: ativações, códigos corretos e
  códigos incorretos (logger `seguranca.dois_fatores`).

## Exemplo de saída real

Executado após a suíte de testes e alguns testes manuais pela tela,
incluindo um bloqueio real por força bruta (usuário `vitor`, 6
tentativas de senha errada seguidas):

A saída completa, com o comando real executado, está em
[`evidencias/13-evidencia-analise-logs.txt`](evidencias/13-evidencia-analise-logs.txt).

## Por que ignorar a assinatura de integridade na análise

A issue 5.3 (`auditoria/integridade.py`) adiciona `| mac=...` ao final
de cada linha do log, para detectar alteração ou remoção de linhas.
Esse valor não tem relação com o conteúdo do evento em si, então o
comando de análise o descarta ao extrair a mensagem, evitando que ele
apareça (ou atrapalhe as expressões regulares) no resumo.

## Testes automatizados

`auditoria/tests.py`, classe `AnalisarLogsCommandTests`: cobre a
contagem de falhas por usuário, a detecção de bloqueio, a contagem
dos três eventos de 2FA, a exclusão de linhas de outros loggers (como
`seguranca.recuperacao_senha`), a compatibilidade com e sem a
assinatura `| mac=...`, e o erro claro quando o arquivo de log não
existe. Usa `call_command` com `StringIO`, no mesmo padrão já usado
para o comando `verificar_logs` (issue 5.3).