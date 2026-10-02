# Guia de Avaliação

Roteiro para testar cada item do checklist pelo front-end do sistema em
produção, sem precisar instalar nada.

**Endereço:** https://circulagov.nossoprojeto.app.br

## Contas

O CirculaGov não tem autocadastro, e isso é uma decisão de projeto, não uma
ausência: o aluno é identificado pelo RA emitido pela rede estadual, e deixar
qualquer pessoa criar conta inventando um RA tornaria o identificador inútil. A
justificativa está em [DADOS_PESSOAIS.md](DADOS_PESSOAIS.md).

Por isso as contas de avaliação são criadas pela equipe. **As senhas foram
entregues junto com a submissão no ambiente acadêmico, e não estão neste
repositório, que é público.**

| Conta | Para que serve |
|---|---|
| `professor` | conta principal, com acesso à tela de integridade do log |
| `professor_descartavel` | existe para ser apagada no teste do item 4.10 |
| `professor_reserva` | reserva, caso o acesso se perca ao testar o 2FA |

As três usam o e-mail institucional do avaliador, então a recuperação de senha
pode ser testada sem depender da equipe.

Comece por `professor`. Deixe `professor_descartavel` para o momento de testar
a exclusão de dados, porque aquela conta deixa de existir depois do teste.

---

## 1. Autenticação e Gestão de Credenciais

| Item | Onde testar |
|---|---|
| 1.1 e 1.2 Hash Argon2id com parâmetros justificados | não tem tela. Código em `usuarios/hashers.py`, justificativa em [JUSTIFICATIVAS_TECNICAS.md](JUSTIFICATIVAS_TECNICAS.md) seção 1 |
| 1.3 e 1.4 Salt único e armazenamento | o salt vem embutido no hash. Veja [GESTAO_CREDENCIAIS.md](GESTAO_CREDENCIAIS.md) |
| 1.5 2FA implementado | entre em `/dois-fatores/cadastrar/`, escaneie o QR com Google Authenticator ou Authy e confirme com o código |
| 1.6 2FA validado após a senha | faça logout e entre de novo: depois da senha certa, o sistema pede o código antes de autenticar |
| 1.7 Fluxo documentado | [FLUXO_AUTENTICACAO.md](FLUXO_AUTENTICACAO.md) |
| 1.8 Evidências | [EVIDENCIAS.md](EVIDENCIAS.md) e `docs/evidencias/` |
| 1.9 Sessão expira | 30 minutos de inatividade, ou 12 horas desde o login. Para não esperar, veja o teste automatizado em `usuarios/tests.py` |
| 1.10 Logout invalida a sessão | clique em Sair e use o botão voltar do navegador: não volta para a área logada |
| 1.11 Proteção contra força bruta | erre a senha 5 vezes seguidas na tela de login. A partir daí a conta é recusada por 15 minutos, mesmo com a senha certa. Use `professor_descartavel` para não travar a principal |
| 1.12 Justificativas | [JUSTIFICATIVAS_TECNICAS.md](JUSTIFICATIVAS_TECNICAS.md) |

Para o 1.11, o atraso progressivo também é perceptível: cada tentativa errada
demora um pouco mais que a anterior, até 2,5 segundos.

---

## 2. Recuperação de Senha

Todo o bloco se testa em `/recuperar-senha/`.

| Item | Como verificar |
|---|---|
| 2.1 Funcionalidade existe | peça a recuperação com o e-mail da conta. A mensagem chega de verdade, por SMTP |
| 2.2 Token seguro | veja o link recebido: 43 caracteres aleatórios, gerados por `secrets.token_urlsafe` |
| 2.3 Expiração | o token vale 30 minutos |
| 2.4 Invalidado após uso | use o link, redefina a senha, e tente abrir o mesmo link de novo: é recusado |
| 2.5 Falha correta | o link já usado leva a uma tela de token inválido, sem dizer o motivo |
| 2.6 e 2.7 Registro em log | os eventos vão para `logs/seguranca.log`. Veja [LOGS_AUTENTICACAO.md](LOGS_AUTENTICACAO.md) |

**Repare numa coisa de propósito:** peça a recuperação para um usuário que não
existe. A resposta é idêntica à de um usuário que existe. Isso impede descobrir
quais contas existem testando a tela, e está explicado em
[FLUXO_RECUPERACAO_SENHA.md](FLUXO_RECUPERACAO_SENHA.md).

---

## 3. Criptografia e Comunicação Segura

| Item | Como verificar |
|---|---|
| 3.1 TLS/HTTPS | o cadeado do navegador. Certificado Let's Encrypt válido |
| 3.2 Bloqueio de conexão insegura | digite `http://circulagov.nossoprojeto.app.br` sem o "s": é redirecionado para HTTPS |
| 3.3 Evidência de tráfego cifrado | TLS 1.3 com `TLS_AES_256_GCM_SHA384`. Veja [EVIDENCIA_TLS.md](EVIDENCIA_TLS.md) |
| 3.4 e 3.5 Dados cifrados em repouso | o segredo do 2FA é cifrado com AES-GCM antes de ir ao banco. Código em `dois_fatores/cripto.py` |
| 3.6 Chaves protegidas | três chaves distintas, em variáveis de ambiente, fora do código e fora do repositório |
| 3.7 e 3.8 Documentado e justificado | [ESTRATEGIA_CRIPTOGRAFIA.md](ESTRATEGIA_CRIPTOGRAFIA.md) |

Para conferir o 3.3 por conta própria:

```bash
openssl s_client -connect circulagov.nossoprojeto.app.br:443 \
  -servername circulagov.nossoprojeto.app.br < /dev/null 2>/dev/null \
  | grep -E "Protocol|Cipher"
```

---

## 4. Conformidade com a LGPD

| Item | Onde testar |
|---|---|
| 4.1 a 4.3 Dados coletados, finalidade e minimização | [DADOS_PESSOAIS.md](DADOS_PESSOAIS.md) |
| 4.4 e 4.5 Consentimento por finalidade | `/consentimento/`, aceite uma finalidade |
| 4.6 Revogação | na mesma tela, clique em Revogar |
| 4.7 Data e versão | aparecem ao lado de cada consentimento ativo |
| 4.8 Consulta aos dados | `/meus-dados/` |
| 4.9 Exportação | botão de exportar na mesma tela, baixa um JSON |
| 4.10 Exclusão | **use `professor_descartavel`**. Em `/meus-dados/`, exclua a conta. Ela deixa de existir |
| 4.11 Fluxo documentado | [FLUXO_DIREITOS_TITULAR.md](FLUXO_DIREITOS_TITULAR.md) |

Sobre o 4.6: revogar não apaga o registro, só marca a data de revogação. É
proposital, para preservar o histórico de que houve consentimento. Isso aparece
na própria tela, que separa ativos de revogados.

---

## 5. Auditoria e Logs

| Item | Onde testar |
|---|---|
| 5.1 e 5.2 Logs de autenticação, falhas e 2FA | [LOGS_AUTENTICACAO.md](LOGS_AUTENTICACAO.md) e `docs/evidencias/` |
| 5.3 Proteção contra alteração | **`/auditoria/integridade/`**, com a conta `professor` |
| 5.4 Exemplo de análise | [ANALISE_LOGS.md](ANALISE_LOGS.md) |

A tela de integridade mostra quantas linhas foram verificadas e o último MAC
válido da cadeia. Cada linha do log carrega um HMAC-SHA256 que cobre o MAC da
linha anterior, então apagar, alterar ou reordenar qualquer linha quebra a
verificação. O mecanismo e seus limites estão em
[INTEGRIDADE_LOGS.md](INTEGRIDADE_LOGS.md).

A tela exige `is_staff`. A conta `professor` tem essa marcação, mas **nenhuma
permissão sobre dados**: ela abre a tela de integridade sem receber controle
sobre o conteúdo do sistema.

---

## 6. Documentação Técnico-Científica

Todo o bloco está em `docs/`. O ponto de entrada é
[VISAO_GERAL.md](VISAO_GERAL.md), e o mapa completo de qual documento atende
qual item está no [README da raiz](../README.md).

---

## Testes automatizados

117 testes cobrindo os cinco blocos. Para rodar, com o projeto instalado:

```bash
python manage.py test
```

A descrição do que cada bloco de testes cobre, e contra qual ameaça, está em
[TESTES_SEGURANCA.md](TESTES_SEGURANCA.md).

---

## Limitações conhecidas

Registradas aqui para não dar a impressão de que passaram despercebidas:

- não há tela para desativar o 2FA depois de ativado. Quem perder o app
  autenticador precisa que alguém remova o dispositivo pelo `/admin/`
- não há rotina de expurgo por tempo de retenção
- o bloqueio por força bruta é por nome de usuário, não por endereço de origem,
  pelo motivo explicado em [JUSTIFICATIVAS_TECNICAS.md](JUSTIFICATIVAS_TECNICAS.md)
- o log fica em arquivo no servidor: a cadeia de HMAC detecta alteração, mas
  quem tiver acesso de escrita ainda pode apagar o arquivo inteiro

A lista completa está em [VISAO_GERAL.md](VISAO_GERAL.md).
