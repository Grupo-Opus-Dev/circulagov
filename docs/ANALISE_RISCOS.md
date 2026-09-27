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
