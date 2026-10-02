# CirculaGov

Plataforma de identidade e proteção de dados pessoais para um programa de
circulação de livros entre escolas da rede pública.

Trabalho da disciplina **Políticas de Segurança da Informação**.

## Comece por aqui

| Documento | Para quê |
|---|---|
| [docs/GUIA_AVALIACAO.md](docs/GUIA_AVALIACAO.md) | **roteiro para testar cada item do checklist no sistema em produção** |
| [docs/VISAO_GERAL.md](docs/VISAO_GERAL.md) | o que o sistema faz, o que não faz, e como rodar |
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | diagramas de camadas, apps, requisição e chaves |
| [docs/ANALISE_RISCOS.md](docs/ANALISE_RISCOS.md) | ativos, ameaças e contramedidas |

## Escopo entregue

A disciplina avalia segurança da informação. Foi nessa camada que o projeto
aprofundou: autenticação, recuperação de senha, criptografia, conformidade com
a LGPD e auditoria.

O módulo de acervo (catálogo, empréstimo, devolução, licitações e estoque) não
foi implementado. O documento [docs/README.md](docs/README.md), escrito no
início do projeto, descreve o produto completo que foi imaginado. Para o que
existe hoje, veja a [visão geral](docs/VISAO_GERAL.md).

## Onde está cada requisito do checklist

| Bloco | Código | Documentação |
|---|---|---|
| 1. Autenticação e credenciais | `usuarios/`, `dois_fatores/` | [FLUXO_AUTENTICACAO.md](docs/FLUXO_AUTENTICACAO.md), [GESTAO_CREDENCIAIS.md](docs/GESTAO_CREDENCIAIS.md), [JUSTIFICATIVAS_TECNICAS.md](docs/JUSTIFICATIVAS_TECNICAS.md) |
| 2. Recuperação de senha | `recuperacao_senha/` | [FLUXO_RECUPERACAO_SENHA.md](docs/FLUXO_RECUPERACAO_SENHA.md), [EVIDENCIAS_RECUPERACAO_SENHA.md](docs/EVIDENCIAS_RECUPERACAO_SENHA.md) |
| 3. Criptografia e comunicação | `dois_fatores/cripto.py`, `config/settings.py` | [ESTRATEGIA_CRIPTOGRAFIA.md](docs/ESTRATEGIA_CRIPTOGRAFIA.md), [EVIDENCIA_TLS.md](docs/EVIDENCIA_TLS.md) |
| 4. LGPD | `consentimento/`, `direitos_titular/` | [DADOS_PESSOAIS.md](docs/DADOS_PESSOAIS.md), [FLUXO_DIREITOS_TITULAR.md](docs/FLUXO_DIREITOS_TITULAR.md) |
| 5. Auditoria e logs | `auditoria/` | [INTEGRIDADE_LOGS.md](docs/INTEGRIDADE_LOGS.md), [ANALISE_LOGS.md](docs/ANALISE_LOGS.md), [LOGS_AUTENTICACAO.md](docs/LOGS_AUTENTICACAO.md) |
| 6. Documentação técnico-científica | `docs/` | [VISAO_GERAL.md](docs/VISAO_GERAL.md), [ARQUITETURA.md](docs/ARQUITETURA.md), [FLUXOS.md](docs/FLUXOS.md), [ANALISE_RISCOS.md](docs/ANALISE_RISCOS.md), [TESTES_SEGURANCA.md](docs/TESTES_SEGURANCA.md), [REFERENCIAS.md](docs/REFERENCIAS.md) |

Evidências de funcionamento em [docs/evidencias/](docs/evidencias).

## Stack

Python 3.13, Django 5.2 LTS, PostgreSQL 17, Django Templates com Tailwind CSS.
Arquitetura monólito modular, padrão MVT.

## Como rodar

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha. As duas chaves de criptografia
precisam ser geradas e precisam ser diferentes entre si:

```bash
python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
```

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Testes e verificação de integridade do log:

```bash
python manage.py test
python manage.py verificar_logs
```

## Equipe

| Integrante | GitHub |
|---|---|
| Everson Duarte de Souza | [@everson-duarte](https://github.com/everson-duarte) |
| Emanuel Victor | [@Manuzel](https://github.com/Manuzel) |
| Vitor Dias Santana | [@vitin2505](https://github.com/vitin2505) |
| Maycon Wendyl da Silva Pereira | [@wendylmaycon](https://github.com/wendylmaycon) |

## Entregas

As releases seguem as etapas da disciplina. Veja
[Releases](https://github.com/Grupo-Opus-Dev/circulagov/releases) e o
[quadro Kanban](https://github.com/orgs/Grupo-Opus-Dev/projects/1).
