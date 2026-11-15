# Dados Pessoais Coletados (Issues 4.1 e 4.3)

Este documento lista todo dado pessoal que o CirculaGov guarda hoje,
pra qual finalidade cada um serve, e as decisões que já foram tomadas
pra coletar o mínimo necessário.

## 1. Tipos de usuário previstos

O CirculaGov previu quatro tipos de usuário até agora, cada um
identificado do jeito que já existe na vida real, sem inventar um
registro novo que o próprio sistema teria que validar sozinho.

| Tipo | Identificador principal | Outros dados |
|---|---|---|
| Aluno (rede pública estadual de SP) | RA (Registro do Aluno) | Nome completo, e-mail institucional (obrigatório) |
| Bibliotecário | Matrícula pública | Nome completo |
| Administrador | Matrícula pública | Nome completo |
| Escola | Registro estadual da instituição | |

### Aluno

O aluno tem **RA**, **nome completo** e **e-mail institucional**. O
login é feito com o nome de usuário da conta e a senha. O RA fica no
cadastro de aluno ligado à conta, e o nome de usuário é escolhido por
quem cria a conta, podendo ser o próprio RA.

RA e nome completo bastam pro uso normal do sistema, porque, no fluxo
pensado pro programa, quem toma a ação sobre um aluno com devolução
atrasada não é o CirculaGov, é a escola. Quando o prazo passa, o
sistema avisa o bibliotecário, e é a escola, fora do sistema, quem
localiza o aluno pelo RA e decide o que fazer. Como o cadastro
completo do aluno já existe na rede estadual, o CirculaGov não precisa
duplicar esse dado, só precisa de um identificador que aponte pra ele.

O e-mail institucional é a exceção obrigatória, e tem uma finalidade
própria e diferente das outras duas: recuperação de senha. A rede
estadual já fornece esse tipo de conta pro aluno vinculada ao RA
(Google Workspace/Centro de Mídias), então não é um dado novo pedido
só pro CirculaGov, é outro identificador que a própria rede emite. Ele
precisa ser obrigatório porque, sem isso, um aluno que esquecesse a
senha ficaria sem nenhuma forma de recuperá-la sozinho (ver diferença
pro `email` opcional dos outros tipos, na seção 3).

### Bibliotecário e Administrador

Os dois são servidores públicos, então usam o identificador que já
existe pro cargo deles: **matrícula pública** mais **nome completo**.
Diferenciar bibliotecário de administrador não exige outro dado
pessoal, essa diferença fica a cargo da permissão de acesso dentro do
sistema (`is_staff`, grupos etc.), não de mais um campo.

### Escola

A escola é identificada pelo **registro estadual da instituição**, o
código que a própria Secretaria de Educação já usa pra identificar
cada unidade escolar. É um identificador da instituição, não de uma
pessoa física, por isso não tem uma segunda coluna preenchida na
tabela acima.

### Situação atual

O Aluno já está implementado (model `Aluno` no app `alunos`, ligado ao
`Usuario` genérico por um `OneToOneField`). O RA também é usado como
`username`, então o aluno entra pela mesma tela de login de todo
mundo, sem view nova. O e-mail institucional é obrigatório no
cadastro, o model recusa salvar um aluno sem ele.

Bibliotecário, Administrador e Escola seguem só no desenho, sem
código ainda.

## 2. Listagem completa

### `usuarios.Usuario` (herda de `AbstractUser` do Django)

| Campo | Finalidade |
|---|---|
| `username` | Identificar o usuário no login |
| `password` | Autenticação (guardado como hash Argon2id, nunca em texto puro) |
| `email` | Enviar o link de recuperação de senha, quando preenchido |
| `first_name`, `last_name` | Exibição do nome do usuário nas telas |
| `is_staff`, `is_active`, `date_joined`, `last_login` | Controle de acesso e auditoria, não são dados fornecidos pelo usuário |

### `dois_fatores.DispositivoTOTP`

| Campo | Finalidade |
|---|---|
| `segredo_cifrado` | Gerar e validar o código de autenticação de dois fatores |

Não é um dado pessoal no sentido da LGPD (não identifica a pessoa
sozinho), mas é uma credencial de segurança ligada a ela, por isso
fica cifrado em repouso (ver `JUSTIFICATIVAS_TECNICAS.md`).

### `recuperacao_senha.TokenRecuperacaoSenha`

| Campo | Finalidade |
|---|---|
| `token_hash` | Validar o link de recuperação de senha, uso único |
| `criado_em`, `expira_em`, `usado_em` | Controlar a validade do link |

Também não é dado pessoal: só o hash do token fica salvo, o valor
original nunca chega ao banco.

### Log de segurança (`logs/seguranca.log`)

| Campo | Finalidade |
|---|---|
| `username` | Identificar de qual conta foi o evento de login, logout, 2FA ou recuperação de senha, pra investigar um incidente depois |

Único dado pessoal gravado no log. O `username` é escolhido por quem
cria a conta: pode ser o RA ou outro identificador, e quando for um
nome de pessoa também é dado pessoal (ver seção 1). Nenhum outro dado da pessoa entra em nenhuma linha, e
senha, código do 2FA, segredo do TOTP e token de recuperação nunca são
gravados. Detalhes de cada evento, exemplo de linha e por que cada
campo existe em `LOGS_AUTENTICACAO.md`.

## 3. Evidência de minimização de dados

Nenhum dado além do necessário pra login, recuperação de senha e 2FA
é coletado nesta etapa do projeto:

- **Sem CPF, telefone ou endereço.** O MVP de autenticação não precisa
  identificar a pessoa fisicamente, só autenticá-la no sistema.
- **`email` é opcional no `Usuario` genérico**, não obrigatório
  (`blank=True`, herdado do `AbstractUser` padrão do Django, nunca foi
  alterado). Quem não preencher não recebe e-mail de recuperação de
  senha de verdade (a view usa um endereço fictício de fallback nesse
  caso), mas continua usando o sistema normalmente com usuário e
  senha. Essa regra vale pra Bibliotecário, Administrador e Escola;
  o Aluno é a exceção, com e-mail institucional obrigatório, porque
  sem contato nenhum ele não teria como recuperar a senha sozinho
  (ver seção 1).
- **O model `Aluno` (app `alunos`) só guarda RA, nome completo e
  e-mail institucional**, cada um com uma finalidade própria
  (identificação, exibição pro bibliotecário e recuperação de senha).
  Nada de CPF, telefone, endereço ou data de nascimento, mesmo sendo
  dados que a própria rede estadual já tem sobre esse aluno.
  Bibliotecário, Administrador e Escola ainda não têm model no código
  (ver seção 1), só o desenho dos dados de cada um. Adiar a
  implementação até precisar de fato de cada tipo de usuário também é,
  em si, minimização.
- **O segredo do 2FA e o token de recuperação não são "coletados"
  do usuário**, são gerados pelo próprio sistema e nunca ficam
  salvos em texto puro (segredo cifrado, token só como hash).
- **O log de segurança só grava o `username`** de quem gerou o evento
  (login, logout, 2FA, recuperação de senha), nunca senha, código,
  segredo ou token (ver seção 2).

## 4. Política de retenção

Quanto tempo cada dado fica guardado, por quê, e o que acontece no fim. O
que é apagado automaticamente sai pelo comando `manage.py expurgar`, que o
`cron` da VPS roda todo dia às 03:30 UTC (`deploy/cron/circulagov.cron`).

| Dado | Onde fica | Por quanto tempo | Por quê | No fim |
|---|---|---|---|---|
| Conta: `username`, `email`, nome, hash da senha, datas de acesso | `usuarios_usuario` | Enquanto a conta existir | Sem eles não há login nem recuperação de senha. Base: consentimento de cadastro (LGPD, art. 7º, I) | Apagados na hora quando o titular pede a exclusão ou quando a gestão exclui a conta (`FLUXO_DIREITOS_TITULAR.md`, seção 5) |
| Aluno: RA (cifrado) e nome completo | `alunos_aluno` | Enquanto a conta existir | Identificar o aluno na rede estadual | Apagados junto com a conta (CASCADE) |
| Segredo do 2FA e último intervalo de código usado | `dois_fatores_dispositivototp` | Enquanto o 2FA estiver ativo | Gerar e conferir o código | Apagados junto com a conta, ou quando a gestão remove o dispositivo |
| Consentimentos, inclusive os revogados | `consentimento_consentimento` | Enquanto a conta existir | Provar quando cada consentimento foi dado e revogado: o ônus da prova é do controlador (LGPD, art. 8º, § 2º) | Apagados junto com a conta |
| Token de recuperação de senha (só o hash) | `recuperacao_senha_tokenrecuperacaosenha` | Vale 30 minutos. Depois de vencido, fica mais 7 dias | Os 7 dias permitem investigar um pedido de recuperação suspeito | Apagado pelo `expurgar` |
| Contador de tentativas (chave é um hash, sem nome nem endereço em claro) | `usuarios_contadordetentativas` | Até a janela vencer: 15 minutos, ou o tempo do bloqueio | Bloqueio por força bruta | Apagado pelo `expurgar` e pelo próprio login, que limpa os vencidos |
| Sessão (guarda o id da conta) | `django_session` | 30 minutos sem uso, 12 horas no máximo | Manter o login entre as páginas | Apagada no logout, e as vencidas pelo `expurgar` |
| Log de segurança: `username` e o evento | `logs/seguranca.log` | Até a rotação, que é feita a cada 6 meses junto com a troca da chave. O arquivo arquivado fica mais 6 meses | Investigar incidentes. Os 6 meses usam como referência o prazo que o Marco Civil da Internet (Lei 12.965/2014, art. 15) fixa para registros de acesso a aplicações | O arquivo arquivado é apagado inteiro, à mão, 6 meses depois da rotação. Linhas não são apagadas uma a uma, porque isso quebraria a cadeia HMAC (`INTEGRIDADE_LOGS.md`) |
| Âncoras do log | `logs/ancoras.log` e e-mail de integrantes | Junto com o log a que se referem | Detectar o corte do final do log | Saem junto com o log arquivado |
| Backup | Não existe backup próprio | Não se aplica | O projeto não configura backup do banco nem do log | Se o provedor da VPS fizer backup por conta própria, ele fica fora do controle da aplicação e guarda os dados até ser substituído, no prazo do provedor |

**O que não é automático.** A rotação do log e a remoção do arquivo
arquivado são manuais, porque dependem de parar o container e trocar a
chave (`deploy/rotacionar-chave-do-log.sh`). A data da próxima rotação é
responsabilidade de quem opera o servidor.
