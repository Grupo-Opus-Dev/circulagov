# Política de segurança

## Como reportar uma vulnerabilidade

Se você encontrar uma falha de segurança no CirculaGov, não abra uma issue
pública. Use a aba **Security > Report a vulnerability** deste repositório,
que mantém o relato privado até a correção.

Inclua no relato o que foi encontrado, como reproduzir e qual o impacto
esperado.

## O que é verificado automaticamente

A cada Pull Request e a cada push na `main`, o GitHub Actions roda:

- **Segredos (TruffleHog):** procura chaves e senhas em todo o histórico do Git
- **Dependências (Trivy):** procura CVE de severidade alta ou crítica
- **Código (Semgrep e CodeQL):** análise estática de segurança
- **Aplicação em execução (OWASP ZAP):** varredura dinâmica
- **Testes automatizados:** suíte com PostgreSQL 17

Um achado de severidade alta ou crítica bloqueia o merge na `main`.

## Versões com suporte

Só a versão mais recente, publicada em Releases, recebe correções.
