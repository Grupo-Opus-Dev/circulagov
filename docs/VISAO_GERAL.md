# Visão Geral do CirculaGov (Issue 6.1)

Documento de entrada do projeto. Serve para quem nunca viu o sistema entender,
sem abrir o código, o que ele faz, para quem serve, o que já está pronto e o
que não está.

## 1. Identificação

| | |
|---|---|
| Projeto | CirculaGov |
| Disciplina | Políticas de Segurança da Informação |
| Repositório | https://github.com/Grupo-Opus-Dev/circulagov |

### Equipe

| Integrante | GitHub |
|---|---|
| Everson Duarte de Souza | [@everson-duarte](https://github.com/everson-duarte) |
| Emanuel Victor | [@Manuzel](https://github.com/Manuzel) |
| Vitor Dias Santana | [@vitin2505](https://github.com/vitin2505) |
| Maycon Wendyl | [@wendylmaycon](https://github.com/wendylmaycon) |

## 2. O problema

Prefeituras e escolas da rede pública compram livros didáticos e paradidáticos
de forma independente. Cada escola cadastra o próprio acervo do jeito que
acha melhor, inclusive a localização física na estante. O resultado prático é
que ninguém sabe o que existe fora da própria escola.

Isso gera dois desperdícios ao mesmo tempo: uma escola compra um título que a
escola vizinha tem parado na prateleira, e livros sem uso ficam encostados em
um lugar onde poderiam atender a população de outra região.

A ideia do CirculaGov é dar visibilidade a esse acervo e permitir que ele
circule entre unidades, com um padrão único de catalogação para que o mesmo
livro seja identificado da mesma forma em qualquer escola da rede.

## 3. Objetivo desta entrega

Aqui é onde este documento precisa ser honesto, porque o sistema entregue não
é o sistema descrito acima por inteiro.

A disciplina avalia **segurança da informação**, não gestão de acervo. Por
isso a equipe optou por construir em profundidade a camada que a disciplina
cobra, e deixar o domínio de livros apenas indicado.

O que o CirculaGov é hoje, na prática: uma **plataforma de identidade e
proteção de dados pessoais** para o programa de circulação de livros. Ela
resolve autenticação, recuperação de senha, criptografia, conformidade com a
LGPD e auditoria. Sobre essa base, o módulo de acervo poderia ser construído
depois sem refazer nada de segurança.

## 4. Perfis de usuário

Os perfis foram desenhados a partir de identificadores que já existem na vida
real, para não criar um cadastro novo que o próprio sistema teria que validar.

| Perfil | Identificador | Situação |
|---|---|---|
| Aluno | RA (Registro do Aluno) | modelado em `alunos/models.py`, faz login com o RA |
| Bibliotecário | matrícula pública | previsto, ainda não modelado |
| Administrador | matrícula pública | atendido hoje pelo `is_staff` do Django |
| Escola | registro estadual da instituição | previsto, ainda não modelado |

Detalhamento de cada dado coletado e sua finalidade em
[DADOS_PESSOAIS.md](DADOS_PESSOAIS.md).

## 5. O que está implementado

Tudo abaixo funciona pelo front-end e tem teste automatizado.

### Autenticação e credenciais

- login por usuário e senha, com o RA servindo de nome de usuário para alunos
- senha guardada com hash Argon2id, com salt único por usuário
- segundo fator por TOTP, compatível com Google Authenticator e similares
- o login só se completa depois do código do segundo fator
- sessão expira por inatividade em 30 minutos e por tempo absoluto em 12 horas
- logout invalida a sessão no servidor
- proteção contra força bruta: bloqueio após 5 tentativas em 15 minutos, com
  atraso progressivo antes disso

### Recuperação de senha

- solicitação por e-mail, com token gerado por `secrets.token_urlsafe`
- o token em claro nunca é gravado, só o hash SHA-256 dele
- validade de 30 minutos e uso único
- resposta sempre genérica, para não revelar se a conta existe

### Criptografia e comunicação

- HTTPS obrigatório fora de desenvolvimento, com redirecionamento e HSTS
- segredo do segundo fator cifrado em repouso com AES-GCM
- três chaves separadas, uma por finalidade, todas fora do código

### LGPD

- consentimento registrado por finalidade, com versão dos termos e data
- revogação pelo próprio usuário
- consulta aos próprios dados
- exportação dos dados em JSON
- exclusão da conta e dos dados vinculados

### Auditoria

- log dos eventos de autenticação, segundo fator e recuperação de senha
- cada linha do log assinada e encadeada com a anterior por HMAC-SHA256, o que
  torna qualquer alteração detectável
- tela para administrador verificar a integridade do log
- comandos `verificar_logs` e `analisar_logs`

### Telas disponíveis

| Tela | Rota |
|---|---|
| Login | `/contas/login/` |
| Verificação do segundo fator | `/dois-fatores/verificar/` |
| Cadastro do segundo fator | `/dois-fatores/cadastrar/` |
| Início | `/` |
| Solicitar recuperação de senha | `/recuperar-senha/` |
| Redefinir senha | `/recuperar-senha/redefinir/<token>/` |
| Meus consentimentos | `/consentimento/` |
| Meus dados | `/meus-dados/` |
| Integridade do log, só administrador | `/auditoria/integridade/` |
| Administração do Django | `/admin/` |

## 6. O que não está implementado

Listado de propósito, para o documento não prometer o que o sistema não faz.

- catálogo de livros, com o padrão único de catalogação e localização em estante
- empréstimo, reserva e devolução
- transferência de acervo entre unidades
- licitações e controle de estoque
- cadastro de escolas e de bibliotecários como entidades próprias
- envio real de e-mail, que hoje sai no terminal em vez de ir para o destinatário

O `docs/README.md`, escrito no começo do projeto, descreve o produto completo
que foi imaginado. Este documento descreve o que existe.

## 7. Onde está cada requisito do checklist

| Bloco | Onde está | Documentação |
|---|---|---|
| 1. Autenticação e credenciais | `usuarios/`, `dois_fatores/` | [FLUXO_AUTENTICACAO.md](FLUXO_AUTENTICACAO.md) |
| 2. Recuperação de senha | `recuperacao_senha/` | [FLUXO_RECUPERACAO_SENHA.md](FLUXO_RECUPERACAO_SENHA.md) |
| 3. Criptografia e comunicação | `dois_fatores/cripto.py`, `config/settings.py` | [ESTRATEGIA_CRIPTOGRAFIA.md](ESTRATEGIA_CRIPTOGRAFIA.md), [EVIDENCIA_TLS.md](EVIDENCIA_TLS.md) |
| 4. LGPD | `consentimento/`, `direitos_titular/` | [DADOS_PESSOAIS.md](DADOS_PESSOAIS.md), [FLUXO_DIREITOS_TITULAR.md](FLUXO_DIREITOS_TITULAR.md) |
| 5. Auditoria e logs | `auditoria/` | [INTEGRIDADE_LOGS.md](INTEGRIDADE_LOGS.md), [ANALISE_LOGS.md](ANALISE_LOGS.md), [LOGS_AUTENTICACAO.md](LOGS_AUTENTICACAO.md) |
| 6. Documentação | `docs/` | este documento e [ARQUITETURA.md](ARQUITETURA.md) |

As justificativas técnicas de cada decisão de segurança estão reunidas em
[JUSTIFICATIVAS_TECNICAS.md](JUSTIFICATIVAS_TECNICAS.md).

## 8. Tecnologias

| Camada | Escolha |
|---|---|
| Linguagem | Python 3.13 |
| Framework | Django 5.2 LTS |
| Banco | PostgreSQL 17 |
| Interface | Django Templates com Tailwind CSS |
| Arquitetura | monólito modular, padrão MVT |

O detalhamento da arquitetura, com diagramas, está em
[ARQUITETURA.md](ARQUITETURA.md).

## 9. Como executar

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha os valores. As duas chaves de
criptografia precisam ser geradas, e precisam ser diferentes entre si:

```bash
python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
```

Depois:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

A suíte de testes tem 109 testes:

```bash
python manage.py test
```

Verificação da integridade do log:

```bash
python manage.py verificar_logs
```

## 10. Limitações conhecidas

- o contador de força bruta usa o cache local em memória, então em mais de um
  processo cada um teria a própria contagem
- o e-mail de recuperação escreve no terminal em vez de enviar de verdade
- o log é arquivo local: a cadeia de HMAC detecta alteração, mas quem tiver
  acesso de escrita ao servidor ainda pode apagar o arquivo inteiro
- não há rotina de expurgo por tempo de retenção
- o bloqueio por força bruta é por nome de usuário, não por endereço de origem
