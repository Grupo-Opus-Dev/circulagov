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

## Como rodar tudo

```bash
python manage.py test
```

