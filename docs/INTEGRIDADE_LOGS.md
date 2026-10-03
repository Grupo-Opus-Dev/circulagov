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
| Vários processos gravando ao mesmo tempo (workers do Gunicorn) | A cadeia se mantém, nenhuma linha se perde |

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
4. **Linhas anteriores à proteção.** O log gravado antes desta
   implementação não tinha assinatura e foi separado em outro arquivo,
   porque não há como provar sua integridade depois do fato.

## Vários processos gravando no mesmo log

Em produção o Gunicorn roda vários processos, cada um com o seu handler,
todos gravando em `logs/seguranca.log`. Isso exige que a cadeia seja
mantida pelo **arquivo**, e não pela memória de cada processo.

**O que aconteceu.** A primeira versão do handler guardava o último MAC
em memória e só lia o arquivo quando o servidor subia. Com um processo,
como em desenvolvimento, funcionava. Em produção, com três workers, cada
um calculava a linha seguinte a partir de uma linha que já podia não ser
a última, e a cadeia quebrava sozinha. A tela de integridade do log
acusou "Log alterado na linha 3" sem que ninguém tivesse mexido no
arquivo. Esse limite estava listado aqui como conhecido, e mesmo assim o
deploy foi feito com três workers: o limite escrito não foi cruzado com a
configuração de produção.

**Como funciona agora.** A cada evento, o handler:

1. pega uma trava entre processos (`flock` no Linux), num arquivo
   `seguranca.log.lock` ao lado do log
2. lê a assinatura da **última linha do arquivo**
3. calcula o MAC dessa assinatura com o texto novo
4. grava a linha e solta a trava

A trava fica num arquivo separado porque, no Windows, travar um trecho
do próprio log impediria o mesmo handler de ler o final dele. A leitura
do final do arquivo usa blocos que dobram de tamanho, então linhas longas
não são assinadas em cima de uma linha cortada.

**Como foi verificado.** Os testes em `CadeiaComVariosProcessosTests`
incluem quatro processos gravando ao mesmo tempo, esperando o mesmo
instante para disputar o arquivo, e conferem que a cadeia fecha e que
nenhuma das 160 linhas se perdeu. Rodados contra o handler antigo, os
testes de regressão falham.

**O arquivo anterior.** Um log cuja cadeia quebrou por esse defeito
não indica adulteração, e também não dá para provar o contrário. O
tratamento é o mesmo do log anterior à proteção: separar em outro
arquivo, sem apagar, e começar uma cadeia nova. O procedimento está em
[DEPLOY.md](DEPLOY.md).
