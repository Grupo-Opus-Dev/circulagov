"""Regra de quem pode excluir uma conta.

Superusuário não se exclui sozinho: só outro superusuário pode excluí-lo.
Assim quem exclui continua existindo, e o sistema nunca fica sem nenhum
administrador desse nível. Vale para "Meus dados" e para o admin do Django.
"""


def pode_excluir(conta, quem_exclui):
    if not conta.is_superuser:
        return True
    return quem_exclui.is_superuser and quem_exclui.pk != conta.pk
