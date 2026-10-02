"""Controle de acesso das telas restritas a quem administra o sistema."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def exige_gestor(view):
    """Permite a entrada só a quem tem is_staff.

    Existe em vez do staff_member_required do Django porque aquele
    manda quem não está logado para o login do admin, com a aparência
    do Django, e não para a tela da própria aplicação. Numa área que
    faz parte do sistema, e não do admin, isso quebra a experiência.

    Quem está logado mas não tem permissão recebe 403, e não um
    redirecionamento para o login: mandar alguém já autenticado para a
    tela de entrar não resolve nada e só confunde.
    """

    @wraps(view)
    def interna(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied(
                'Esta área é restrita a quem administra o sistema.')
        return view(request, *args, **kwargs)

    return login_required(interna)
