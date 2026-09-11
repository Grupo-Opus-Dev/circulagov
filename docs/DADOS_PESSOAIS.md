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
login é feito com RA e senha.

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

Hoje, nenhum desses quatro tipos existe como model separado no
código, só o `Usuario` genérico (ver seção 2). O Aluno é o único com
os dados já definidos para entrar em implementação nesta etapa;
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
- **Aluno, Bibliotecário, Administrador e Escola ainda não têm model
  no código** (ver seção 1), só o desenho dos dados de cada um. Mesmo
  antes de existir, o desenho do Aluno já nasce mínimo: RA, nome
  completo e e-mail institucional são os únicos dados necessários,
  cada um com uma finalidade própria (identificação, exibição pro
  bibliotecário e recuperação de senha). Nada de CPF, telefone,
  endereço ou data de nascimento, mesmo sendo dados que a própria rede
  estadual já tem sobre esse aluno. Adiar a implementação até precisar
  de fato de cada tipo de usuário também é, em si, minimização.
- **O segredo do 2FA e o token de recuperação não são "coletados"
  do usuário**, são gerados pelo próprio sistema e nunca ficam
  salvos em texto puro (segredo cifrado, token só como hash).
