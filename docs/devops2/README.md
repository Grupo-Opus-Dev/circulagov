# Devops2: esteira DevSecOps

Documento da atividade Devops2. O relatório técnico completo está em
[`Relatorio_Devops2.pdf`](Relatorio_Devops2.pdf), e
os prints de evidência ficam em [`prints/`](prints/). A atividade anterior
está em [`../devops1/`](../devops1/).

## O que a esteira faz

A esteira `.github/workflows/devsecops-pipeline.yml` roda a cada Pull Request
e a cada push na main, com quatro verificações de segurança: TruffleHog
(segredos em todo o histórico do Git, inclusive as chaves AES e HMAC do
projeto), Trivy (CVE nas dependências), Semgrep e CodeQL (análise estática).
Qualquer achado de severidade alta ou crítica faz o job falhar, e as quatro
verificações são obrigatórias para o merge na main. O bloqueio foi comprovado
no PR #121, que plantou de propósito uma chave, uma dependência vulnerável e
uma injeção de comando: os quatro jobs ficaram vermelhos e o merge ficou
bloqueado.

## Checagens obrigatórias da main

A `main` recusa o merge de um Pull Request enquanto qualquer uma das oito
checagens obrigatórias não estiver verde: `testes`, `dast-zap`, `sbom-trivy`,
`privacidade-bearer`, `Segredos (TruffleHog)`, `SCA (Trivy)`,
`SAST (Semgrep)` e `SAST (CodeQL)`. Quem é administrador do repositório ainda
pode contornar a regra, de propósito e com uma ação explícita, para o caso de
emergência. O histórico de execuções fica em
https://github.com/Grupo-Opus-Dev/circulagov/actions.

## Contribuições dos integrantes

- Esteira, relatório e evidências: Everson Duarte de Souza (PRs #120, #122, #123)
- Selo da esteira no README: Emanuel Victor (PR #124)
- Política de segurança, `SECURITY.md`: Vitor Dias Santana (PR #125)
- Texto da esteira na documentação: Maycon Wendyl da Silva Pereira (PR #126),
  movido para este documento para manter separado o relatório de testes da
  entrega anterior
