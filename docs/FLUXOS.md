# Índice de Fluxos e Fluxo de Dados (Issue 6.3)

Este documento é o ponto único de entrada para os fluxos de autenticação
e tratamento de dados pessoais do CirculaGov. Reúne o índice dos fluxos
já documentados e o fluxo de dados propriamente dito: que dado entra no
sistema, por onde ele passa, onde é gravado e por quanto tempo fica.

## Índice dos fluxos

| Documento | O que descreve |
|---|---|
| [`FLUXO_AUTENTICACAO.md`](FLUXO_AUTENTICACAO.md) | Login, senha e autenticação em dois fatores (2FA) |
| [`FLUXO_RECUPERACAO_SENHA.md`](FLUXO_RECUPERACAO_SENHA.md) | Geração do token, redefinição de senha e registro em log |
| [`FLUXO_DIREITOS_TITULAR.md`](FLUXO_DIREITOS_TITULAR.md) | Consentimento, consulta, exportação e exclusão de dados pessoais (LGPD) |

Cada um desses documentos foi conferido contra o código em `main` nesta
revisão. A única divergência encontrada foi a proteção contra força
bruta no login (`usuarios/seguranca.py`, `usuarios/views.py`), que já
existia no código mas não estava descrita em `FLUXO_AUTENTICACAO.md`; o
passo a passo desse documento foi atualizado para incluí-la.

## Fluxo de dados

| Dado | Onde entra | Por onde passa | Onde é gravado | Por quanto tempo fica |
|---|---|---|---|---|
| Senha (texto puro) | Formulário de login (`login.html`) ou de redefinição (`redefinir.html`) | `LoginComDoisFatoresView` ou view `redefinir`, só na memória da requisição | Nunca em texto puro. Vira hash Argon2id em `usuarios_usuario.password` (`usuarios/hashers.py`) | Enquanto a senha não for trocada de novo, sem expiração automática |
| Nome de usuário (`username`) | Formulário de login | `LoginComDoisFatoresView`, sinais de `usuarios/signals.py` | `usuarios_usuario.username`, linhas do log de segurança (`logs/seguranca.log`) | Usuário: enquanto a conta existir. Log: até o arquivo ser rotacionado ou apagado manualmente, fora do controle de versão e sem rotina automática de retenção |
| Token de recuperação de senha (valor bruto) | Nunca vem do usuário, é gerado pelo servidor em `TokenRecuperacaoSenha.gerar` (`recuperacao_senha/models.py`) | Enviado por e-mail (backend console em desenvolvimento), existe só na memória da requisição | Nunca é gravado. Só o hash SHA-256 vai para `recuperacao_senha_tokenrecuperacaosenha.token_hash` | O hash vale por 30 minutos (`MINUTOS_VALIDADE_TOKEN`) ou até o primeiro uso, o que ocorrer primeiro. O registro continua no banco depois de expirado ou usado, não há limpeza automática |
| Segredo do 2FA (TOTP) | Gerado pelo servidor no primeiro `save()` de `DispositivoTOTP` | Cifrado com AES-GCM em `dois_fatores/cripto.py` antes de tocar o banco | `dois_fatores_dispositivototp.segredo_cifrado`, sempre cifrado | Enquanto o dispositivo existir. É apagado junto com o `Usuario` (`on_delete=models.CASCADE`) |
| Código de 6 dígitos do 2FA | Formulário de verificação ou cadastro do 2FA | `DispositivoTOTP.verificar_codigo`, comparado e descartado | Nunca gravado, só o resultado (certo ou errado) vira log | Não persiste além da requisição atual |
| Cookie de sessão | Requisição do navegador | Middleware de sessão do Django, `TimeoutAbsolutoMiddleware` (`usuarios/middleware.py`) | Tabela `django_session` (backend padrão do Django, banco de dados) | Expira por inatividade em 30 minutos (`SESSION_COOKIE_AGE`) ou 12 horas desde o login (`TEMPO_MAXIMO_SESSAO_SEGUNDOS`), o que ocorrer primeiro. Não há limpeza automática das linhas expiradas em `django_session` |
| Dados pessoais do titular (nome, e-mail institucional, RA) | Cadastro do usuário e do aluno | Views de `direitos_titular` (consulta e exportação) | `usuarios_usuario` (username, e-mail), `alunos_aluno` (RA, nome completo) | Enquanto a conta existir. Apagados em cascata quando o próprio titular exclui os dados (requisito 4.10) |
| Consentimento (aceite ou revogação) | Tela `/consentimento/` | `consentimento/views.py` | `consentimento_consentimento` | Indefinidamente. Revogar não apaga a linha, só marca `revogado_em`, para preservar o histórico (requisito 4.7) |

A lista completa de dados pessoais coletados e a finalidade de cada
campo estão em [`DADOS_PESSOAIS.md`](DADOS_PESSOAIS.md). As chaves
usadas para cifrar ou assinar os dados acima estão detalhadas em
[`ESTRATEGIA_CRIPTOGRAFIA.md`](ESTRATEGIA_CRIPTOGRAFIA.md) e em
[`GESTAO_CREDENCIAIS.md`](GESTAO_CREDENCIAIS.md).
