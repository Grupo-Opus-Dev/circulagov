# Logs de Autenticação e 2FA (Issues 5.1 e 5.2)

Este documento lista os eventos de autenticação e 2FA que o CirculaGov
registra no log de segurança, com um exemplo real de cada linha e o
motivo de cada campo gravado.

## 1. Eventos registrados

| Evento | Logger | Nível | Onde no código | Gatilho |
|---|---|---|---|---|
| Login com sucesso | `seguranca.autenticacao` | INFO | `usuarios/signals.py` | Sinal nativo `user_logged_in` |
| Logout | `seguranca.autenticacao` | INFO | `usuarios/signals.py` | Sinal nativo `user_logged_out` |
| Tentativa de login com falha | `seguranca.autenticacao` | WARNING | `usuarios/signals.py` | Sinal nativo `user_login_failed` |
| Bloqueio por força bruta | `seguranca.autenticacao` | WARNING | `usuarios/views.py` | `LoginComDoisFatoresView.post`, quando `usuario_bloqueado()` já existente é `True` |
| 2FA ativado | `seguranca.dois_fatores` | INFO | `dois_fatores/views.py` | Confirmação do dispositivo em `cadastrar` |
| Código 2FA correto | `seguranca.dois_fatores` | INFO | `dois_fatores/models.py` | `DispositivoTOTP.verificar_codigo`, usado no cadastro e no login |
| Código 2FA incorreto | `seguranca.dois_fatores` | WARNING | `dois_fatores/models.py` | `DispositivoTOTP.verificar_codigo`, usado no cadastro e no login |

Login e logout usam os sinais nativos do Django (`user_logged_in`,
`user_logged_out`, `user_login_failed`) em vez de logar direto dentro
da view de login, então nenhuma lógica de autenticação precisou ser
reescrita, só uma função nova conectada a cada sinal.

O código do 2FA é conferido em um único lugar
(`DispositivoTOTP.verificar_codigo`), usado tanto na tela de cadastro
quanto na de verificação do login. Colocar o log ali, em vez de
repetir nas duas views, evita duplicar a mesma lógica duas vezes.

## 2. Formato de uma linha

```
2026-09-17 19:49:52,065 INFO seguranca.autenticacao login com sucesso, username=demo_logs | mac=3f67a17a120dae0f57ed77a8d1cccdc78ce78ca9908a2198c7d43968d0d26192
```

| Campo | Exemplo | Por quê |
|---|---|---|
| Data e hora | `2026-09-17 19:49:52,065` | Saber quando o evento aconteceu |
| Nível | `INFO` / `WARNING` | Falha e bloqueio são `WARNING`, sucesso é `INFO`, pra dar pra filtrar o que é suspeito |
| Logger | `seguranca.autenticacao` | Identifica de qual parte do sistema veio o evento |
| Mensagem | `login com sucesso, username=demo_logs` | O evento em si e o único dado pessoal necessário pra auditoria: o usuário envolvido |
| `mac=...` | `3f67a17a...` | Não é gerado por este código. É a assinatura da issue 5.3 (`auditoria/integridade.py`), aplicada automaticamente a todo logger filho de `seguranca` |

## 3. O que nunca entra no log

Nenhum evento grava senha, código do 2FA, segredo do TOTP ou token de
recuperação. Só o `username` do usuário envolvido.

- No login com falha, o sinal `user_login_failed` do Django já chega
  com a senha removida do dicionário de credenciais antes de disparar
  o sinal. Mesmo assim, o código só lê o campo `username` desse
  dicionário, nunca o dicionário inteiro, por garantia.
- No 2FA, o código digitado é comparado e descartado, só o resultado
  (certo ou errado) vira log.
- Isso é coberto pelo teste `test_log_de_falha_nao_vaza_senha`, em
  `usuarios/tests.py`.

## 4. Por que registrar o username, mesmo sendo dado pessoal

Pro Aluno, o `username` é o RA (ver `docs/DADOS_PESSOAIS.md`), que é
dado pessoal. Ainda assim, é o único jeito de um log de segurança
servir pra alguma coisa: sem saber *quem* tentou logar ou ativou o
2FA, não dá pra investigar um incidente depois. É o mínimo necessário
pra essa finalidade específica (auditoria de segurança), nenhum outro
dado do usuário entra no log.

## 5. Evidência

Testado pela tela com o servidor rodando (usuário `demo_logs`): senha
errada, login certo, ativação do 2FA com código certo e errado,
verificação do 2FA no login com código certo e errado, logout, e um
usuário separado (`usuario_forca_bruta`) levando 5 senhas erradas
seguidas até o bloqueio. As linhas geradas de verdade em
`logs/seguranca.log` estão em
[`evidencias/12-evidencia-logs-autenticacao-2fa.txt`](evidencias/12-evidencia-logs-autenticacao-2fa.txt).

## 6. Testes automatizados

- `usuarios/tests.py`: `TesteLogDeAutenticacao` (login com sucesso,
  logout, falha, e que a falha não vaza senha) e
  `TesteLogDeBloqueioPorForcaBruta` (bloqueio gera log separado da
  falha comum).
- `dois_fatores/tests.py`: `TesteLogDeEventosDoisFatores` (ativação,
  código correto e incorreto, tanto no cadastro quanto no login).

Todos usam `assertLogs`, no mesmo padrão já usado em
`recuperacao_senha/tests.py`.
