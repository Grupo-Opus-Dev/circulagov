---
name: conventional-commit
description: Padroniza mensagens de commit neste repositório (CirculaGov) seguindo Conventional Commits. Use sempre que for criar um commit neste projeto, mesmo que o usuário só diga "comita isso", "cria um commit", "salva essa mudança" ou peça para subir/enviar código para o GitHub — não espere o usuário pedir explicitamente o formato.
---

# Conventional Commits — CirculaGov

Este repositório segue o padrão Conventional Commits, documentado em `docs/README.md`. Todo commit criado neste projeto deve seguir este formato, para manter o histórico legível e rastreável ao longo do desenvolvimento (isso importa aqui porque o projeto é avaliado academicamente por ter "commits organizados e distribuídos no tempo").

## Antes de commitar

1. Rode `git status` e `git diff` (staged e unstaged) para entender exatamente o que mudou.
2. Se as mudanças cobrem mais de um assunto (ex: uma feature + uma correção de docs), separe em commits distintos — **um commit = uma mudança lógica**. Não empacote tudo junto só porque está tudo modificado ao mesmo tempo.
3. Stage só os arquivos relevantes para aquele commit específico (evite `git add -A`/`git add .` cego se houver arquivos de assuntos diferentes misturados).

## Formato da mensagem

```
tipo: descrição curta no imperativo, minúscula, sem ponto final

corpo opcional explicando o porquê (não repita o que já está óbvio no diff)

Closes #N
```

### Tipos válidos (do README do projeto)

| Tipo | Quando usar |
|---|---|
| `feat` | nova funcionalidade |
| `fix` | correção de bug |
| `docs` | mudanças só na documentação |
| `chore` | configuração estrutural, dependências |
| `style` | formatação, CSS, ajustes visuais — sem mudar lógica |
| `refactor` | reorganização de código sem mudar comportamento |

Escolha o tipo pelo efeito líquido da mudança, não pelo que foi "mais difícil" de fazer — um refactor grande que também corrige um bug pequeno no caminho ainda é `refactor`, a menos que o bug seja o motivo principal do commit.

### Referenciando issues

Se o commit resolve total ou parcialmente uma issue do GitHub, referencie no rodapé:

```
Closes #5
```

Para várias issues no mesmo commit:

```
Closes #5, Closes #9
```

Isso fecha a issue automaticamente quando o commit chegar na branch `main` via merge do Pull Request. Só use `Closes` se a mudança realmente resolve a issue por completo — se for só um passo intermediário, referencie sem o `Closes` (ex: `Relacionado a #5`) ou omita.

## Não incluir

**Não adicione a linha `Co-Authored-By: Claude` (ou qualquer variação) nas mensagens de commit deste repositório.** Essa é uma decisão explícita do time — a colaboração com IA no projeto é documentada separadamente na documentação técnica do repositório, não em cada commit individual.

## Exemplo completo

```
feat: implementa hasher Argon2 customizado com parâmetros de custo justificados

Configura time_cost, memory_cost e parallelism explicitamente em vez de
usar os valores padrão do Django, alinhado à recomendação da OWASP para
Argon2id.

Closes #1, Closes #2
```
