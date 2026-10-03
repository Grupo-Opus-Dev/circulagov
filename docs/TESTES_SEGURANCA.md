# Testes de Segurança (Issues 6.9 e 6.10)

O CirculaGov já tem uma suíte automatizada com `python manage.py test`.
Este documento apresenta essa suíte pelo ângulo de segurança: para cada
área, o que está sendo testado, contra qual ameaça, e onde encontrar
cada teste no código. A seção final registra os resultados de uma
execução real.

## 1. Autenticação e 2FA

**Ameaça:** um invasor conseguir acessar a conta de outra pessoa sabendo
só a senha (sem o segundo fator), ou continuar autenticado depois de já
ter saído do sistema.

| Teste | Arquivo | O que prova |
|---|---|---|
| `test_senha_correta_sozinha_nao_autentica` | `dois_fatores/tests.py` (`TesteLoginComDoisFatores`) | Senha certa sozinha não é suficiente pra quem tem 2FA ativado |
| `test_senha_e_codigo_certos_autenticam` | `dois_fatores/tests.py` (`TesteLoginComDoisFatores`) | O login só completa depois do código certo |
| `test_codigo_errado_nao_autentica` | `dois_fatores/tests.py` (`TesteLoginComDoisFatores`) | Código errado barra o acesso mesmo com a senha certa |
| `test_acessar_verificacao_sem_passar_pela_senha_e_recusado` | `dois_fatores/tests.py` (`TesteLoginComDoisFatores`) | Não dá pra pular direto pra tela de código sem antes passar pela senha |
| `test_cookie_antigo_nao_reautentica_depois_do_logout` | `usuarios/tests.py` (`TesteLoginELogout`) | Um cookie de sessão roubado antes do logout para de funcionar depois dele |
| `test_logout_remove_sessao_do_banco` | `usuarios/tests.py` (`TesteLoginELogout`) | O logout invalida a sessão no servidor, não só no navegador |

## 2. Força bruta e atraso progressivo

**Ameaça:** um script tentando adivinhar a senha de um usuário por
tentativa e erro repetida.

| Teste | Arquivo | O que prova |
|---|---|---|
| `test_bloqueio_apos_limite_de_tentativas_gera_log` | `usuarios/tests.py` (`TesteLogDeBloqueioPorForcaBruta`) | Depois de 5 falhas seguidas, a próxima tentativa é recusada antes mesmo de checar a senha |

O atraso progressivo em si (`calcular_atraso`, em `usuarios/seguranca.py`)
não tem um teste próprio que meça o tempo de resposta, só é exercitado
de passagem pelas chamadas de login nos testes acima, sem falhar. O
teste listado cobre o limite de tentativas, que é a parte que
efetivamente bloqueia o ataque.

## 3. Expiração e invalidação de sessão

**Ameaça:** uma sessão continuar válida indefinidamente, mesmo depois
de roubada ou esquecida aberta.

| Teste | Arquivo | O que prova |
|---|---|---|
| `test_sessao_expira_apos_tempo_maximo_mesmo_com_uso_continuo` | `usuarios/tests.py` (`TesteTimeoutDeSessao`) | A sessão expira depois de um tempo máximo, mesmo com uso contínuo |
| `test_sessao_dentro_do_tempo_maximo_continua_valida` | `usuarios/tests.py` (`TesteTimeoutDeSessao`) | Confirma que o corte é só depois do prazo, não antes |
| `test_sessao_sem_marca_de_inicio_e_tratada_como_expirada` | `usuarios/tests.py` (`TesteTimeoutDeSessao`) | Comportamento fail closed: sem marca de início, a sessão é tratada como inválida, não como "sem limite" |
| `test_logout_via_get_nao_faz_nada` | `usuarios/tests.py` (`TesteLoginELogout`) | Um GET não derruba a sessão de outra pessoa (o logout exige POST) |

## 4. Token de recuperação de senha

**Ameaça:** token de recuperação previsível, reaproveitável, ou a tela
revelando quais contas existem no sistema (enumeração de conta).

| Teste | Arquivo | O que prova |
|---|---|---|
| `test_token_expirado_nao_valida` | `recuperacao_senha/tests.py` (`TokenRecuperacaoSenhaTests`) | Token vencido não serve mais |
| `test_token_expirado_por_um_segundo_ja_nao_vale` | `recuperacao_senha/tests.py` (`TesteExpiracaoDoToken`) | O corte de validade é exato, não aproximado |
| `test_token_usado_nao_valida_de_novo` | `recuperacao_senha/tests.py` (`TokenRecuperacaoSenhaTests`) | Token de uso único não pode ser reaproveitado |
| `test_segunda_tentativa_de_redefinir_com_mesmo_token_nao_troca_senha_de_novo` | `recuperacao_senha/tests.py` (`TesteInvalidacaoAposUso`) | Confirma o uso único também pelo fluxo completo da view |
| `test_valor_bruto_nao_fica_salvo_no_banco` | `recuperacao_senha/tests.py` (`TokenRecuperacaoSenhaTests`) | Só o hash do token é gravado, o valor original não fica no banco |
| `test_solicitar_nao_revela_se_usuario_existe` | `recuperacao_senha/tests.py` (`FluxoRecuperacaoSenhaTests`) | A resposta é igual exista ou não o usuário, contra enumeração de conta |
| `test_token_expirado_usado_e_inexistente_mostram_a_mesma_pagina` | `recuperacao_senha/tests.py` (`TesteMensagemGenericaDeFalha`) | Os três motivos de falha mostram a mesma tela, sem dar pista de qual foi |

## 5. Consentimento e direitos do titular

**Ameaça:** um usuário conseguir ver, exportar, revogar ou apagar dados
de **outra** pessoa (falha de controle de acesso horizontal), ou o
sistema tratar consentimento como um "aceito tudo" genérico.

| Teste | Arquivo | O que prova |
|---|---|---|
| `test_nao_pode_ter_dois_consentimentos_ativos_pra_mesma_finalidade` | `consentimento/tests.py` (`ConsentimentoModelTests`) | Consentimento é por finalidade específica, não um aceite genérico |
| `test_nao_pode_revogar_consentimento_de_outro_usuario` | `consentimento/tests.py` (`GerenciarConsentimentoViewTests`) | Um usuário não consegue revogar o consentimento de outra conta |
| `test_revogar_via_get_nao_revoga` | `consentimento/tests.py` (`GerenciarConsentimentoViewTests`) | Revogação exige POST, não pode ser disparada por um link/GET |
| `test_nao_mostra_dados_de_outro_usuario` | `direitos_titular/tests.py` (`ConsultarDadosViewTests`) | A consulta de dados só mostra os dados do próprio usuário logado |
| `test_nao_exporta_dados_de_outro_usuario` | `direitos_titular/tests.py` (`ExportarDadosViewTests`) | A exportação também respeita esse limite |
| `test_apos_excluir_usuario_e_deslogado` | `direitos_titular/tests.py` (`ExcluirDadosViewTests`) | Depois da exclusão, a sessão não continua válida |
| `test_confirmar_exclusao_exige_login` | `direitos_titular/tests.py` (`ExcluirDadosViewTests`) | Exclusão de dados exige estar autenticado |

## 6. Integridade do log

**Ameaça:** alguém com acesso ao servidor apagar ou editar linhas do
log de segurança pra esconder um incidente.

| Teste | Arquivo | O que prova |
|---|---|---|
| `test_alterar_texto_de_uma_linha_e_detectado` | `auditoria/tests.py` (`CadeiaDeIntegridadeTests`) | Alterar o texto de uma linha quebra a assinatura dela |
| `test_apagar_linha_do_meio_e_detectado` | `auditoria/tests.py` (`CadeiaDeIntegridadeTests`) | Apagar uma linha do meio é detectado na linha seguinte |
| `test_inserir_linha_forjada_sem_a_chave_e_detectado` | `auditoria/tests.py` (`CadeiaDeIntegridadeTests`) | Não dá pra inserir uma linha falsa sem ter a chave |
| `test_verificar_com_chave_errada_falha` | `auditoria/tests.py` (`CadeiaDeIntegridadeTests`) | Verificar com a chave errada não aprova o log |
| `test_quebra_de_linha_na_mensagem_nao_forja_linha_nova` | `auditoria/tests.py` (`CadeiaDeIntegridadeTests`) | Um username malicioso com quebra de linha não consegue forjar uma linha extra (log injection) |
| `test_linha_sem_assinatura_e_detectada` | `auditoria/tests.py` (`CadeiaDeIntegridadeTests`) | Uma linha acrescentada na mão, sem assinatura, é rejeitada |

## 7. Controle de acesso à gestão de contas

**Ameaça:** um usuário comum, ou alguém sem login, abrir as telas que mostram
e alteram os dados de todas as contas.

| Teste | Arquivo | O que prova |
|---|---|---|
| `test_sem_login_vai_pro_login_da_aplicacao` | `usuarios/tests.py` (`TesteAcessoAGestaoDeUsuarios`) | Sem login, as rotas de gestão mandam para a tela de entrar da aplicação, e não para a do admin do Django |
| `test_usuario_comum_recebe_403` | `usuarios/tests.py` (`TesteAcessoAGestaoDeUsuarios`) | Quem está logado sem o perfil de gestão recebe 403 nas três rotas |
| `test_usuario_staff_entra` | `usuarios/tests.py` (`TesteAcessoAGestaoDeUsuarios`) | O perfil de gestão abre as três rotas |
| `test_usuario_comum_nao_remove_2fa_de_ninguem` | `usuarios/tests.py` (`TesteRemocaoDoDoisFatores`) | Um usuário comum não consegue remover o segundo fator de outra conta |
| `test_so_por_post` | `usuarios/tests.py` (`TesteRemocaoDoDoisFatores`) | Remover o 2FA exige POST, não pode ser disparado por um link |
| `test_remocao_vai_pro_log_como_aviso` | `usuarios/tests.py` (`TesteRemocaoDoDoisFatores`) | A remoção entra no log como aviso, com o nome de quem a fez, porque reduz a proteção da conta |
| `test_nao_pode_remover_o_proprio_acesso_de_gestao` | `usuarios/tests.py` (`TesteEdicaoDeUsuario`) | Ninguém rebaixa a si mesmo, o que deixaria o sistema sem administrador |
| `test_nao_pode_desativar_a_propria_conta` | `usuarios/tests.py` (`TesteEdicaoDeUsuario`) | Pelo mesmo motivo, ninguém desativa a própria conta |
| `test_desativar_impede_o_login` | `usuarios/tests.py` (`TesteEdicaoDeUsuario`) | Uma conta desativada não consegue entrar |
| `test_edicao_vai_pro_log_de_seguranca` | `usuarios/tests.py` (`TesteEdicaoDeUsuario`) | Toda alteração de conta fica registrada com o autor |

## 8. Cadastro por convite e senha na redefinição

**Ameaça:** quem cadastra conhecer a senha de quem foi cadastrado, e a tela de
redefinição aceitar senhas fracas.

| Teste | Arquivo | O que prova |
|---|---|---|
| `test_conta_nasce_sem_senha_utilizavel` | `usuarios/tests.py` (`TesteCadastroComLinkDeSenha`) | No modo de convite a conta é criada sem senha, então ninguém a conhece |
| `test_fluxo_completo_do_convite_ate_o_login` | `usuarios/tests.py` (`TesteCadastroComLinkDeSenha`) | Cadastro, e-mail, link, senha escolhida pela pessoa e login, de ponta a ponta |
| `test_falha_no_email_nao_esconde_o_problema` | `usuarios/tests.py` (`TesteCadastroComLinkDeSenha`) | Se o e-mail falhar, a conta fica criada e a tela avisa, em vez de parecer que deu certo |
| `test_senha_curta_e_recusada` | `recuperacao_senha/tests.py` (`TesteValidadoresNaRedefinicao`) | A redefinição passa a aplicar os validadores de senha do projeto |
| `test_senha_recusada_nao_queima_o_token` | `recuperacao_senha/tests.py` (`TesteValidadoresNaRedefinicao`) | Errar a senha não obriga a pedir outro link |
| `test_recusa_vai_pro_log_sem_a_senha` | `recuperacao_senha/tests.py` (`TesteValidadoresNaRedefinicao`) | A recusa é registrada sem gravar a senha digitada |

A redefinição aceitava qualquer senha, até `1`, porque só conferia se as duas
digitadas eram iguais. Foi descoberto ao implementar o convite. Os seis testes da
classe `TesteValidadoresNaRedefinicao`, e não só os três da tabela, foram rodados
contra o código antigo e todos falharam.

## 9. Falhas que só aparecem em produção

**Ameaça:** proteções que funcionam com um processo, como em desenvolvimento, e
deixam de funcionar com os três workers do Gunicorn.

| Teste | Arquivo | O que prova |
|---|---|---|
| `test_quatro_processos_gravando_ao_mesmo_tempo` | `auditoria/tests.py` (`CadeiaComVariosProcessosTests`) | Quatro processos disputando o log não quebram a cadeia nem perdem linhas |
| `test_handlers_alternando_no_mesmo_arquivo_mantem_a_cadeia` | `auditoria/tests.py` (`CadeiaComVariosProcessosTests`) | A cadeia vive no arquivo, não na memória de cada processo |
| `test_ultima_linha_maior_que_o_bloco_de_leitura` | `auditoria/tests.py` (`CadeiaComVariosProcessosTests`) | Uma linha longa não é assinada em cima de uma leitura cortada |
| `test_limite_pequeno_deixa_o_atacante_zerar_o_bloqueio` | `usuarios/tests.py` (`TesteDescarteDoCacheDeBloqueio`) | Demonstra o mecanismo: com limite baixo, tentativas com nomes inventados apagam o contador de uma conta |
| `test_limite_folgado_preserva_o_contador` | `usuarios/tests.py` (`TesteDescarteDoCacheDeBloqueio`) | Com limite alto o contador sobrevive |
| `test_configuracao_de_producao_tem_limite_folgado` | `usuarios/tests.py` (`TesteDescarteDoCacheDeBloqueio`) | Lê o settings de produção e garante que o limite não foi removido |

Os dois defeitos foram encontrados depois do deploy. O primeiro apareceu na
própria tela de integridade, que acusou "Log alterado" sem ninguém ter mexido
no arquivo. O segundo, ao documentar o cache. O relato de cada um está em
[INTEGRIDADE_LOGS.md](INTEGRIDADE_LOGS.md) e em
[JUSTIFICATIVAS_TECNICAS.md](JUSTIFICATIVAS_TECNICAS.md), seção 5.

## 10. Tela de eventos do log

**Ameaça:** conteúdo digitado por um atacante virar código na tela do
administrador, e uma lista de log que pede confiança sem permitir conferência.

| Teste | Arquivo | O que prova |
|---|---|---|
| `test_html_digitado_pelo_usuario_nao_e_executado` | `auditoria/tests.py` (`ListaDeEventosTests`) | Um `<script>` digitado como nome de usuário aparece escapado, não executa |
| `test_log_adulterado_aparece_na_lista_e_marca_o_que_vem_depois` | `auditoria/tests.py` (`ListaDeEventosTests`) | Da primeira quebra da cadeia em diante, nenhuma linha é apresentada como confirmada |
| `test_linha_fora_do_formato_aparece_em_vez_de_sumir` | `auditoria/tests.py` (`ListaDeEventosTests`) | Uma linha estranha é mostrada, não escondida |
| `test_usuario_comum_recebe_403` | `auditoria/tests.py` (`ListaDeEventosTests`) | Só o perfil de gestão abre a tela |

Os testes de escape e de marcação da cadeia foram conferidos quebrando o código
de propósito: com o escape desligado e com a marcação sempre verdadeira, ambos
falham.

## 15. CSS próprio e política de conteúdo

**Ameaça:** código de terceiro ou injetado executando dentro das páginas (ameaça 16 de `ANALISE_RISCOS.md`).

| Teste | Arquivo | O que prova |
|---|---|---|
| `test_toda_resposta_tem_o_cabecalho` | `usuarios/test_csp.py` (`TestePoliticaDeConteudo`) | O cabeçalho `Content-Security-Policy` vem com `script-src 'self'`, `object-src 'none'` e `frame-ancestors 'none'` |
| `test_politica_nao_libera_codigo_inline_nem_cdn` | idem | A política não tem `unsafe-inline`, `unsafe-eval` nem o CDN do Tailwind |
| `test_cabecalho_vem_tambem_em_erro_e_redirecionamento` | idem | Respostas 404 e redirecionamentos também levam o cabeçalho |
| `test_nenhuma_tela_depende_de_codigo_dentro_do_html` | idem | Dezesseis telas, da aplicação e do admin, não têm script, `<style>`, `onclick`, `style=` nem `javascript:` dentro do HTML |
| `test_nenhum_template_carrega_script_de_terceiro` | idem | Nenhum template usa `<script src>` externo |
| `test_toda_classe_usada_nos_templates_existe_no_css` | `usuarios/test_csp.py` (`TesteCssDoTailwindVersionado`) | Cada classe usada nos templates e nas strings `CLASSE_*` tem regra em `static/css/tailwind.css` |
| `test_o_css_nao_depende_do_cdn` | idem | O arquivo de CSS não referencia o CDN |

Conferência manual feita em 03/10/2026: a tela de login abre com o CSS estático, sem o objeto `tailwind` no navegador e sem erros de CSP no console.

## Execução contínua

Os testes rodam sozinhos no GitHub Actions, em `.github/workflows/testes.yml`,
a cada push na `main` e a cada Pull Request. O fluxo sobe um PostgreSQL 17
descartável, instala as dependências, gera chaves de teste na hora, roda a suíte,
valida a configuração de produção com `DEBUG=False` e confere se há migração
pendente.

A `main` está configurada para recusar o merge de um Pull Request cuja checagem
`testes` não esteja verde. Quem é administrador do repositório ainda pode contornar a
regra, de propósito e com uma ação explícita, para o caso de emergência. O
histórico de execuções, com data, hora e log de cada uma, fica em
https://github.com/Grupo-Opus-Dev/circulagov/actions.

## Como rodar tudo

```bash
python manage.py test
```

## Resultados da execução

O registro abaixo é de uma execução datada. Desde então a suíte cresceu, e em
03/10/2026 tem 192 testes. A execução mais recente, com resultado e log, está
sempre na aba Actions do repositório.

Execução real em **24/09/2026**, com **Python 3.13.15** e **Django
5.2.17**.

### `python manage.py test`

```
Ran 109 tests in 10.667s

OK
```

Saída completa, sem cortes, em
[`evidencias/14-evidencia-saida-python-manage-test.txt`](evidencias/14-evidencia-saida-python-manage-test.txt).
As linhas com data e hora misturadas aos pontos dos testes não são
erro de formatação: são os próprios eventos de segurança sendo
gravados de verdade enquanto os testes que os disparam rodam.

### `python manage.py verificar_logs`

Com o log íntegro (3 eventos reais gerados pela tela: login errado,
login certo e logout):

```
Log íntegro: 3 linhas verificadas.
Último MAC da cadeia: 506414722c93054166fba2c59563b9b060f1f8b376d82f10ff03ee66b83f1c64
```

Depois de adulterar de propósito a linha 2 (trocando "sucesso" por
"SUCESSO", mantendo a assinatura antiga):

```
CommandError: Log ALTERADO na linha 2: assinatura não confere (linha alterada, removida ou inserida)
```

A detecção aponta exatamente a linha alterada. Evidência completa,
com as três linhas originais e as adulteradas, em
[`evidencias/15-evidencia-verificar-logs.txt`](evidencias/15-evidencia-verificar-logs.txt).

Pra reproduzir: gerar alguns eventos de login pela tela, rodar
`python manage.py verificar_logs` (deve aprovar), editar manualmente
uma palavra de qualquer linha de `logs/seguranca.log` e rodar o
comando de novo (deve apontar a linha alterada).
