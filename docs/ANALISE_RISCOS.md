# Análise de Riscos

## 6.6 Ativos do Sistema

Ativo é tudo que possui valor para o sistema e precisa ser protegido. O levantamento abaixo considera os dados pessoais, credenciais, software, infraestrutura e segredos utilizados pelo CirculaGov.

### Dados e credenciais

| Ativo                             | Onde fica                                                     | Tipo                       | Criticidade |
| --------------------------------- | ------------------------------------------------------------- | -------------------------- | ----------- |
| Credenciais e senhas dos usuários | `usuarios.Usuario`, campo `password`                          | Dado de autenticação       | Alta        |
| Dados pessoais dos alunos         | `alunos.Aluno` e `usuarios.Usuario`                           | Dado pessoal               | Alta        |
| Segredo do 2FA                    | `dois_fatores.DispositivoTOTP`, campo `segredo_cifrado`       | Credencial de autenticação | Alta        |
| Tokens de recuperação de senha    | `recuperacao_senha.TokenRecuperacaoSenha`, campo `token_hash` | Credencial de recuperação  | Alta        |
| Logs de segurança                 | `logs/seguranca.log`                                          | Registro de auditoria      | Média       |
| Registros de consentimento        | `consentimento.Consentimento`                                 | Registro de privacidade    | Alta        |

### Software e infraestrutura

| Ativo                     | Onde fica                                                  | Tipo           | Criticidade |
| ------------------------- | ---------------------------------------------------------- | -------------- | ----------- |
| Aplicação Django          | Projeto e aplicativos configurados em `config/settings.py` | Software       | Alta        |
| Banco de dados PostgreSQL | Configuração `DATABASES` em `config/settings.py`           | Software       | Alta        |
| Servidor de aplicação     | Ambiente onde o projeto Django é executado                 | Infraestrutura | Alta        |
| Canal TLS                 | Configurações HTTPS/TLS em `config/settings.py`            | Infraestrutura | Alta        |

### Segredos

| Ativo                    | Onde fica                                              | Tipo                  | Criticidade |
| ------------------------ | ------------------------------------------------------ | --------------------- | ----------- |
| `SECRET_KEY`             | Variável de ambiente carregada em `config/settings.py` | Segredo criptográfico | Alta        |
| `CHAVE_CIFRAGEM_2FA`     | Variável de ambiente carregada em `config/settings.py` | Chave criptográfica   | Alta        |
| `CHAVE_INTEGRIDADE_LOGS` | Variável de ambiente carregada em `config/settings.py` | Chave criptográfica   | Alta        |

## 6.7 Ameaças e Vulnerabilidades

As ameaças foram levantadas com base nos ativos identificados na seção 6.6 e nos mecanismos de segurança utilizados pelo sistema.

### 1. Roubo da base de dados e quebra de senha offline

**Descrição:** Um atacante que obtenha uma cópia do banco de dados pode tentar descobrir as senhas a partir dos hashes armazenados.

**Ativo afetado:** Credenciais e senhas dos usuários.

**Impacto:** Acesso não autorizado às contas e possível exposição de dados pessoais.

### 2. Força bruta no login

**Descrição:** Um atacante pode realizar várias tentativas de autenticação para tentar descobrir a senha de um usuário.

**Ativo afetado:** Credenciais e senhas dos usuários.

**Impacto:** Acesso não autorizado às contas.

### 3. Sequestro de sessão

**Descrição:** Um atacante pode tentar obter ou reutilizar uma sessão válida para acessar a aplicação como outro usuário.

**Ativo afetado:** Aplicação Django e credenciais dos usuários.

**Impacto:** Acesso indevido a funcionalidades e dados protegidos.

### 4. Reuso ou interceptação de token de recuperação

**Descrição:** Um token de recuperação pode ser capturado ou reutilizado indevidamente para alterar a senha de uma conta.

**Ativo afetado:** Tokens de recuperação de senha.

**Impacto:** Perda de acesso à conta e possível acesso aos dados do usuário.

### 5. Enumeração de contas pela tela de recuperação

**Descrição:** Um atacante pode tentar descobrir quais usuários possuem conta observando as respostas da funcionalidade de recuperação de senha.

**Ativo afetado:** Dados pessoais dos alunos e credenciais dos usuários.

**Impacto:** Exposição da existência de contas e facilitação de ataques direcionados.

### 6. Adulteração de log por quem tem acesso ao servidor

**Descrição:** Uma pessoa com acesso ao servidor pode tentar modificar ou remover registros de segurança.

**Ativo afetado:** Logs de segurança.

**Impacto:** Perda da confiabilidade dos registros e dificuldade para investigar incidentes.

### 7. Injeção de conteúdo no log

**Descrição:** Dados controlados pelo usuário podem ser utilizados para inserir conteúdo indevido nos registros de segurança.

**Ativo afetado:** Logs de segurança.

**Impacto:** Poluição dos registros e dificuldade para identificar eventos reais.

### 8. Interceptação de tráfego em rede aberta

**Descrição:** Um atacante na mesma rede pode tentar interceptar dados transmitidos entre o usuário e a aplicação.

**Ativo afetado:** Canal TLS e dados pessoais dos alunos.

**Impacto:** Exposição de credenciais, dados pessoais e informações da sessão.

### 9. Vazamento do segredo do 2FA

**Descrição:** Caso o segredo utilizado pelo segundo fator seja obtido por um atacante, ele pode tentar gerar códigos válidos de autenticação.

**Ativo afetado:** Segredo do 2FA.

**Impacto:** Comprometimento do segundo fator e possível acesso não autorizado à conta.

### 10. Força bruta no código do segundo fator

**Descrição:** Quem já conhece a senha de uma conta com 2FA pode tentar códigos de 6 dígitos na etapa de verificação. Essa etapa não tem trava de tentativas por conta no código.

**Ativo afetado:** Contas protegidas por segundo fator.

**Impacto:** Acesso não autorizado, anulando o benefício do segundo fator.

### 11. Zerar o bloqueio de login com nomes inventados

**Descrição:** O contador de tentativas fica numa tabela de cache com teto de entradas. Passando do teto, parte dos contadores é descartada, e quem tenta senhas contra uma conta poderia apagar o próprio bloqueio disparando tentativas com nomes de usuário inventados.

**Ativo afetado:** Credenciais e senhas dos usuários.

**Impacto:** Contorno da proteção contra força bruta.

### 12. Abuso do e-mail de recuperação de senha

**Descrição:** Cada pedido de recuperação dispara um e-mail. Sem limite, alguém pode encher a caixa de uma pessoa e esgotar a cota diária de envios da conta de e-mail.

**Ativo afetado:** Tokens de recuperação e o canal de e-mail.

**Impacto:** Indisponibilidade da recuperação de senha e incômodo ao titular da conta.

### 13. Contorno do segundo fator pelo admin do Django

**Descrição:** O admin do Django tem login próprio, que não passava pelo segundo fator nem pelo bloqueio por tentativas. Quem soubesse a senha de uma conta de gestão entrava no `/admin/` sem o código, e podia tentar senhas sem limite.

**Ativo afetado:** Contas de gestão e o painel administrativo.

**Impacto:** Acesso administrativo sem o segundo fator, anulando a proteção que o 2FA deveria dar justamente às contas mais poderosas.

### 14. Bloqueio de login que nunca termina

**Descrição:** Cada tentativa feita durante o bloqueio por força bruta reiniciava o prazo de 15 minutos. Quem continuasse tentando ficava bloqueado indefinidamente. Um atacante podia, por isso, manter uma conta de vítima trancada enviando uma tentativa a cada poucos minutos, e o próprio dono da conta se trancava ao insistir.

**Ativo afetado:** Disponibilidade das contas.

**Impacto:** Negação de acesso a uma conta específica, sem precisar da senha.

### Lacunas identificadas

Além das ameaças já consideradas pelo projeto, outras ameaças podem ser identificadas durante a análise. Quando uma ameaça ainda não possui uma proteção implementada, ela deve ser registrada como uma lacuna de segurança para avaliação posterior.

Lacunas conhecidas hoje:

- a verificação do segundo fator e o pedido de recuperação de senha não têm trava de tentativas por conta no código (ameaças 10 e 12)
- o limite de requisições por endereço não barra um ataque distribuído por muitos endereços
- não há backup do banco nem do log de segurança

## 6.8 Risco x Contramedida

A análise abaixo relaciona cada ameaça da seção 6.7 com sua probabilidade, impacto, risco resultante, contramedida implementada e risco residual.

### 1. Roubo da base de dados e quebra de senha offline

**Probabilidade:** Média

**Impacto:** Alta

**Risco resultante:** Alto

**Contramedida implementada:** Uso do algoritmo Argon2id para armazenamento das senhas.

**Onde está no código:** `usuarios/hashers.py` e `config/settings.py`.

**Risco residual:** Médio.

### 2. Força bruta no login

**Probabilidade:** Média

**Impacto:** Alta

**Risco resultante:** Alto

**Contramedida implementada:** Bloqueio e atraso após tentativas de autenticação.

**Onde está no código:** `usuarios/seguranca.py`.

**Risco residual:** Baixo.

### 3. Sequestro de sessão

**Probabilidade:** Média

**Impacto:** Alta

**Risco resultante:** Alto

**Contramedida implementada:** Timeout da sessão, cookies HttpOnly e uso de cookie seguro em produção.

**Onde está no código:** `usuarios/middleware.py` e `config/settings.py`.

**Risco residual:** Médio.

### 4. Reuso ou interceptação de token de recuperação

**Probabilidade:** Média

**Impacto:** Alta

**Risco resultante:** Alto

**Contramedida implementada:** O token é armazenado somente como hash, possui validade de 30 minutos e pode ser utilizado apenas uma vez.

**Onde está no código:** `recuperacao_senha/models.py` e `recuperacao_senha/views.py`.

**Risco residual:** Baixo.

### 5. Enumeração de contas pela tela de recuperação

**Probabilidade:** Baixa

**Impacto:** Média

**Risco resultante:** Médio

**Contramedida implementada:** Uso de resposta genérica na solicitação de recuperação, sem informar se a conta existe.

**Onde está no código:** `recuperacao_senha/views.py`.

**Risco residual:** Baixo.

### 6. Adulteração de log por quem tem acesso ao servidor

**Probabilidade:** Média

**Impacto:** Alta

**Risco resultante:** Alto

**Contramedida implementada:** Cadeia de HMAC para verificar a integridade dos registros de segurança.

**Onde está no código:** `auditoria/integridade.py`.

**Risco residual:** Médio.

### 7. Injeção de conteúdo no log

**Probabilidade:** Média

**Impacto:** Média

**Risco resultante:** Médio

**Contramedida implementada:** Não foi identificada uma contramedida específica para todos os cenários de injeção de conteúdo no log.

**Onde está no código:** Configuração dos logs em `config/settings.py`.

**Risco residual:** Risco aceito. A proteção específica contra injeção de conteúdo no log ainda é uma lacuna identificada.

### 8. Interceptação de tráfego em rede aberta

**Probabilidade:** Média

**Impacto:** Alta

**Risco resultante:** Alto

**Contramedida implementada:** Redirecionamento para HTTPS e utilização de HSTS em produção.

**Onde está no código:** `config/settings.py`.

**Risco residual:** Baixo.

### 9. Vazamento do segredo do 2FA

**Probabilidade:** Média

**Impacto:** Alta

**Risco resultante:** Alto

**Contramedida implementada:** O segredo do 2FA é armazenado de forma cifrada utilizando AES-GCM. A chave de cifragem é mantida em variável de ambiente.

**Onde está no código:** `dois_fatores/cripto.py`, `dois_fatores/models.py` e `config/settings.py`.

**Risco residual:** Médio.

### 10. Força bruta no código do segundo fator

**Probabilidade:** Baixa

**Impacto:** Alta

**Risco resultante:** Médio

**Contramedida implementada:** Limite de requisições por endereço na verificação do segundo fator, 10 por minuto, no nginx. Instalado no servidor em 03/10/2026 e conferido de fora, pela internet.

**Onde está no código:** `deploy/nginx/circulagov-limites.conf`. Não há trava por conta na aplicação.

**Risco residual:** Médio. O limite reduz a velocidade por endereço, mas não impede um ataque distribuído, e a aplicação continua sem bloquear a conta.

### 11. Zerar o bloqueio de login com nomes inventados

**Probabilidade:** Média

**Impacto:** Alta

**Risco resultante:** Alto

**Contramedida implementada:** Teto de 100 mil entradas no cache em banco, e limite de requisições por endereço no login.

**Onde está no código:** `config/settings.py` e `deploy/nginx/circulagov-limites.conf`. O teste `test_limite_pequeno_deixa_o_atacante_zerar_o_bloqueio`, em `usuarios/tests.py`, demonstra o mecanismo.

**Risco residual:** Baixo. Seriam necessárias mais de 100 mil tentativas com nomes distintos em 15 minutos.

### 12. Abuso do e-mail de recuperação de senha

**Probabilidade:** Média

**Impacto:** Média

**Risco resultante:** Médio

**Contramedida implementada:** Limite de requisições por endereço no pedido de recuperação, 3 por minuto, no nginx.

**Onde está no código:** `deploy/nginx/circulagov-limites.conf`.

**Risco residual:** Médio. O limite é por endereço e permite mais de 4 mil pedidos por dia de um só, mais que a cota diária de envios da conta de e-mail. Contém o abuso, mas não o impede.

### 13. Contorno do segundo fator pelo admin do Django

**Probabilidade:** Média

**Impacto:** Alta

**Risco resultante:** Alto

**Contramedida implementada:** O `/admin/login/` deixou de autenticar e só redireciona para o login da aplicação. O admin aceita a sessão que sai de lá, e assim herda o segundo fator e o bloqueio por tentativas.

**Onde está no código:** `usuarios/admin_site.py`, `usuarios/admin_config.py` e `config/settings.py`. A classe `TesteAdminUsaOLoginDaAplicacao`, em `usuarios/tests.py`, cobre o caso, e quatro de seus testes falham contra o admin antigo.

**Risco residual:** Baixo para quem ativou o 2FA. O 2FA continua opcional, então uma conta de gestão que nunca o ativou ainda entra só com a senha.

### 14. Bloqueio de login que nunca termina

**Probabilidade:** Média

**Impacto:** Média

**Risco resultante:** Médio

**Contramedida implementada:** Tentativas feitas durante o bloqueio não renovam o prazo. O bloqueio passou a valer por par (usuário, endereço), com teto de 25 falhas por conta somando todos os endereços. Assim, um endereço isolado não tranca a conta para os demais, e quem troca de endereço a cada 5 tentativas também é barrado.

**Onde está no código:** `usuarios/seguranca.py`, `usuarios/views.py` e `CABECALHO_IP_DO_CLIENTE` em `config/settings.py`. Os testes estão em `TesteBloqueioDeLoginPorEndereco`, em `usuarios/tests.py`.

**Risco residual:** Médio-baixo. Um atacante com muitos endereços ainda pode manter o teto de 25 da conta atingido e trancar a vítima. O limite protege a conta contra adivinhação, e o custo é essa indisponibilidade temporária.
