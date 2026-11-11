# Devops1: esteira DevSecOps avançada

Documento da atividade Devops1. O relatório técnico está em
[`Relatorio_Devops1.pdf`](Relatorio_Devops1.pdf).

A esteira `.github/workflows/devsecops-avancado.yml` roda três ferramentas:
OWASP ZAP (análise dinâmica do sistema em execução), Bearer (dados pessoais no
código) e Trivy (SBOM e CVE da imagem Docker). Os jobs `dast-zap`,
`privacidade-bearer` e `sbom-trivy` são checagens obrigatórias da main.

A atividade seguinte, com TruffleHog, Trivy das dependências, Semgrep e
CodeQL, está em [`../devops2/`](../devops2/).
