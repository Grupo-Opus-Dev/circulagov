# Documentação da Stack Tech (Arquitetura e ferramentas)

**Projeto:** Circula Gov - Livros

**Disciplina:** Políticas de Segurança da informação

O Circula Gov - Livros é uma plataforma web para conectar prefeituras e entes governamentais na gestão, manutenção e empréstimo de livros didáticos ou não com o escopo de garantir a eficiência em licitações bem como na gestão de recursos públicos. O sistema permite gerenciamento de licitações, controle de estoque, empréstimos entre entes governamentais, como também o gerenciamento da disponibilização dos livros para os alunos das escolas públicas (reservas, devolução, controle de cadastro em geral). Construído com Python, Django e PostgreSQL, utiliza Tailwind e CSS, unindo a tecnologia e a qualidade do ensino motor.



Nesta primeira versão (MVP - Produto Mínimo Viável), o sistema terá como foco central o gerenciamento de cadastro dos usuários e livros, em especial licitação, empréstimo, devolução 



---



## 1. Arquitetura do Sistema

Para o projeto **CirculaGov**, selecionamos a arquitetura de software **Monolítica Modular**, aplicando o padrão de projeto **MVT (Model-View-Template)** uma vez que o próprio Django já fornece essa estrutura nativamente.

### Justificativa da Arquitetura:

* **Model (Modelo):** Essa camada lida com a lógica de dados e as regras de negócio, além de abstrair a interação com o banco de dados através de um ORM (Object-Relational Mapping). 
* **View (Visão):** Essa camada vai atuar como um controlador da aplicação, recebendo as requisições HTTP, processando as regras de autorização e consultando os Models, retornando uma resposta adequada.
* **Template (Interface):** Essa camada irá cuidar da apresentação, renderizando o HTML dinamicamente, recebendo os dados já processados pelas Views.

Escolhemos o padrão MVT em um monolito para garantir velocidade de desenvolvimento, facilidade de manutenção e para aproveitar a infraestrutura robusta de autenticação e segurança do framework base (Django).

---

## 2. Stack Tecnológica (Tech Stack)

As ferramentas utilizadas na criação do sistema foram as seguintes:

### Back-end (Lógica e Servidor)

* **Linguagem de Programação:** Python 3.13
* **Framework Web:** Django v5.2 LTS

### Banco de Dados

* **SGBD:** PostgreSQL 17

### Front-end (Interface do Usuário)

* **Estrutura:** HTML5
* **Interatividade:** JavaScript (Vanilla) ES6+.
* **Estilização:** Tailwind CSS v3.4.
* **Motor de Renderização:** Django Templates v5.2 LTS.

---

## 3. Controle de Versão e Gestão

* **Repositório:** Git e GitHub.
* **Metodologia Ágil:** Gestão de tarefas baseada em Kanban, utilizando o GitHub Projects para rastreabilidade de entregas e atribuição de responsáveis.
* **Padrão Commits:** A equipe utiliza o padrão Conventional Commits para manter o histórico de versionamento claro, auditável e semântico durante as entregas do projeto: 
  
  
  
  `feat:` Adição de nova funcionalidade (ex: *feat: cria formulário de histórico de empréstimos*). 
  
  `fix:` Correção de falhas e bugs. 
  
  `docs:` Alterações e adições na documentação oficial e README. 
  
  `chore:` Tarefas de configuração estrutural e atualização de dependências. 
  
  `style:` Ajustes visuais (CSS, HTML) e formatação de código. 
  
  `refactor:` Melhorias estruturais no código sem impacto na funcionalidade.

---


