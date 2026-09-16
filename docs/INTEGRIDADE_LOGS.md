# Proteção contra Alteração dos Logs (Issue 5.3)

Este documento explica como o CirculaGov detecta alteração no log de
segurança (`logs/seguranca.log`), como verificar a integridade e quais
são os limites da proteção.

## Como funciona

Cada linha gravada no log recebe, no final, uma assinatura HMAC-SHA256:

```
2026-09-16 07:15:00,089 INFO seguranca.recuperacao_senha recuperacao de senha concluida com sucesso, username=usuario_teste | mac=30f72cac...
```

A assinatura de cada linha é calculada sobre duas coisas juntas:

1. o texto da própria linha;
2. a assinatura da linha anterior (a primeira linha usa um valor inicial fixo).

Isso forma uma **cadeia**. Por causa do encadeamento:

- **Alterar** o texto de uma linha invalida a assinatura dela.
- **Apagar** uma linha do meio faz a linha seguinte apontar para uma
  assinatura anterior que não existe mais.
- **Inserir** uma linha falsa exige calcular um HMAC válido, o que só é
  possível com a chave.

A chave fica na variável de ambiente `CHAVE_INTEGRIDADE_LOGS`, fora do
código e do repositório.

## Onde está no código

| Arquivo | Papel |
|---|---|
| `auditoria/integridade.py` | Handler que assina as linhas e função que verifica o arquivo |
| `config/settings.py` (`LOGGING`) | Troca o `FileHandler` comum pelo `HandlerLogIntegro` |
| `auditoria/management/commands/verificar_logs.py` | Verificação pelo terminal |
| `auditoria/views.py` | Verificação pela tela, só para administradores |
| `auditoria/tests.py` | 14 testes cobrindo os ataques descritos abaixo |

O handler fica no logger pai `seguranca`. Qualquer logger filho
(`seguranca.recuperacao_senha`, `seguranca.autenticacao` etc.) é
protegido automaticamente, sem precisar mudar nada no código que gera o
evento.

## Como verificar

**Pela tela** (usuário com `is_staff`): acessar `/auditoria/integridade/`.

**Pelo terminal:**

```bash
python manage.py verificar_logs
```

Se o log estiver íntegro, o comando mostra o total de linhas e o último
MAC da cadeia. Se houver alteração, termina com erro indicando a linha.

## Evidência

Arquivo completo em
[`evidencias/11-evidencia-integridade-logs.txt`](evidencias/11-evidencia-integridade-logs.txt).
A linha 5 teve o usuário trocado de `usuario_teste` para `outro_usuario`,
mantendo a assinatura original:

```
=== Verificacao do log original ===
integro=True total_linhas=13 linha_com_problema=None

=== Verificacao do log adulterado ===
integro=False total_linhas=5 linha_com_problema=5
motivo=assinatura não confere (linha alterada, removida ou inserida)
```

O mesmo teste foi feito pela tela `/auditoria/integridade/` com o
servidor rodando: antes da alteração, "Log íntegro: 13 linhas
verificadas"; depois, "Log alterado na linha 5".

## Ataques cobertos pelos testes

| Ataque | Resultado |
|---|---|
| Alterar texto de uma linha | Detectado na linha alterada |
| Apagar linha do meio | Detectado na linha seguinte à apagada |
| Inserir linha forjada com assinatura inventada | Detectado na linha inserida |
| Acrescentar linha sem assinatura | Detectado |
| Verificar com a chave errada | Falha |
| Quebra de linha dentro do evento (log injection) | Vira espaço, não cria linha falsa |
| Reiniciar o servidor | A cadeia continua de onde o arquivo parou |

## Limites da proteção

Nenhuma proteção de log é absoluta. Os limites conhecidos são:

1. **Remoção das últimas linhas.** Apagar linhas do final deixa uma
   cadeia menor, mas ainda válida. Para detectar isso, o último MAC
   mostrado pela verificação deve ser anotado fora do servidor
   periodicamente e comparado depois.
2. **Vazamento da chave.** Quem tiver a chave consegue recalcular a
   cadeia inteira. Por isso ela fica só em variável de ambiente e é
   diferente da chave de cifragem do 2FA.
3. **Apagar o arquivo inteiro.** A proteção detecta alteração, não
   impede. Em produção, o log deveria ser copiado para um servidor
   separado, onde a aplicação só consegue escrever.
4. **Vários processos gravando ao mesmo tempo.** O handler protege a
   ordem entre threads do mesmo processo. Com vários processos (ex:
   vários workers do gunicorn) escrevendo no mesmo arquivo, a cadeia
   pode se misturar. Nesse cenário, cada processo deveria ter seu
   próprio arquivo.
5. **Linhas anteriores à proteção.** O log gravado antes desta
   implementação não tinha assinatura e foi separado em outro arquivo,
   porque não há como provar sua integridade depois do fato.
