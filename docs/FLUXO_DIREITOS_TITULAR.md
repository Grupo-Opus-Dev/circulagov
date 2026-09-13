# Fluxo de Atendimento aos Direitos do Titular (Requisitos 4.6 a 4.10)

Este documento descreve como o CirculaGov atende cada direito do titular
de dados previsto na LGPD: revogação de consentimento, consulta,
exportação e exclusão dos dados pessoais.

## Visão geral

O atendimento aos direitos do titular está dividido em duas apps:

1. **`consentimento`**: gerencia o aceite e a revogação de consentimentos
   por finalidade, incluindo o histórico de data e versão dos termos.
2. **`direitos_titular`**: reúne consulta, exportação e exclusão dos
   dados pessoais do usuário logado, todas acessíveis a partir da tela
   inicial (`templates/usuarios/inicio.html`).

## Passo a passo

### 1. Revogação do consentimento (requisito 4.6)

Na tela `/consentimento/`, cada consentimento ativo exibe um botão
"Revogar". O POST é recebido pela view `revogar`, em
`consentimento/views.py`, que busca o consentimento pelo `id` filtrando
também por `usuario=request.user` — garantindo que ninguém revogue o
consentimento de outra pessoa, mesmo manipulando o `id` na URL. A
revogação em si é feita pelo método `Consentimento.revogar()`
(`consentimento/models.py`), que marca `revogado_em` com a data atual.
Um consentimento revogado pode ser aceito novamente depois, criando um
novo registro e preservando o histórico do anterior.

### 2. Registro de data e versão do consentimento (requisito 4.7)

Todo consentimento guarda automaticamente o momento em que foi aceito
(`aceito_em`, preenchido pelo Django com `auto_now_add=True`) e a versão
dos termos vigente naquele momento (`versao_termos`, usando
`VERSAO_TERMOS_ATUAL` como padrão). Se os termos mudarem no futuro, os
consentimentos antigos continuam associados à versão que estava em vigor
quando foram aceitos, em vez de serem reinterpretados sob a versão nova.

### 3. Consulta aos dados do titular (requisito 4.8)

Na tela `/meus-dados/`, a view `consultar`
(`direitos_titular/views.py`) reúne os dados pessoais do usuário logado
— nome de usuário, e-mail, data de entrada no sistema e, se aplicável,
dados de aluno (RA e nome completo) — junto com a lista de todos os
seus consentimentos (ativos e revogados). A função interna
`_coletar_dados_pessoais` centraliza essa coleta de dados, sendo
reaproveitada também pela exportação (passo seguinte).

### 4. Exportação dos dados (requisito 4.9)

Na mesma tela de consulta, o botão "Baixar meus dados (JSON)" aciona a
view `exportar`, que monta os mesmos dados coletados por
`_coletar_dados_pessoais` e devolve um arquivo `.json` para download,
usando `JsonResponse` (nativo do Django) com o cabeçalho
`Content-Disposition: attachment` para forçar o download em vez de
exibir o conteúdo na tela.

### 5. Exclusão dos dados pessoais (requisito 4.10)

O botão "Excluir meus dados" leva a uma tela de confirmação
(`confirmar_exclusao`) antes de qualquer ação destrutiva. Só um POST
nessa tela aciona a view `excluir`, que encerra a sessão do usuário
(`logout`) e então apaga o registro do `Usuario`
(`usuario.delete()`). Como os models `Aluno`, `Consentimento` e
`DispositivoTOTP` já têm `on_delete=models.CASCADE` configurado em
seus relacionamentos com `Usuario`, o próprio banco de dados apaga
automaticamente todos os registros relacionados, sem necessidade de
apagar cada tabela manualmente.

## Por que a exclusão exige uma tela de confirmação separada

Diferente das outras ações (que respondem a um clique único), a
exclusão é irreversível: uma vez apagado, o `Usuario` e tudo ligado a
ele (aluno, consentimentos, 2FA) desaparece do banco. Por isso a URL de
exclusão (`excluir/`) não realiza a ação sozinha: um `GET` nela apenas
redireciona de volta à tela de confirmação, e só um `POST` — disparado
pelo botão vermelho "Sim, excluir permanentemente" — de fato apaga os
dados. Esse comportamento está coberto pelo teste
`test_get_nao_exclui_mostra_redireciona_para_confirmacao`, em
`direitos_titular/tests.py`.

## Por que a exportação e a consulta reaproveitam a mesma função

A consulta (`consultar`) e a exportação (`exportar`) precisam
exatamente dos mesmos dados pessoais — a diferença está só no formato
de saída (HTML para exibição, JSON para download). Por isso ambas
chamam `_coletar_dados_pessoais`, evitando que uma futura mudança nos
dados exibidos (por exemplo, um novo campo pessoal) precise ser
replicada em dois lugares diferentes e, eventualmente, esquecida em
um deles.