from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from .integridade import verificar_arquivo


@staff_member_required
def integridade(request):
    """Mostra se o log de segurança está íntegro.

    Só administradores acessam: o resultado indica onde o log foi
    mexido, informação útil pra um invasor tentar esconder rastros.
    """
    resultado = verificar_arquivo(
        settings.LOG_DIR / 'seguranca.log', settings.CHAVE_INTEGRIDADE_LOGS
    )
    return render(request, 'auditoria/integridade.html', {'resultado': resultado})
