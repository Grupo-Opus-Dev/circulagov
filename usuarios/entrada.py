"""Sanitização de entrada vinda do usuário.

Centraliza o tratamento que faz mais sentido aplicar logo depois de
`request.POST.get(...)` ou `request.GET.get(...)`: remover bytes nulos
que o PostgreSQL recusa em campos de texto e que, sem tratamento,
viravam erro 500 (achado do DAST em 03/11/2026).
"""

# O PostgreSQL recusa NUL (0x00) em text/varchar. Qualquer busca ou
# gravacao que passe por ele vira DataError, que o Django converte em
# 500 opaco. Como NUL nao tem valor legitimo num formulario, removemos
# antes de qualquer validacao.
_BYTE_NULO = '\x00'


def texto(valor, maximo=None):
    """Devolve o texto sem bytes nulos nas pontas nem no meio.

    Equivalente a `(valor or '').replace('\\x00', '').strip()`, com um
    limite opcional de tamanho que corta o excesso em vez de salvar uma
    string gigante no banco.
    """
    limpo = (valor or '').replace(_BYTE_NULO, '').strip()
    if maximo is not None:
        limpo = limpo[:maximo]
    return limpo
