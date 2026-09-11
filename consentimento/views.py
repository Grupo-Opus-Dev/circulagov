from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import Consentimento, Finalidade


@login_required
def gerenciar(request):
    """Tela onde o usuário vê o que já aceitou e pode aceitar
    finalidades novas. Revogar fica na issue do Vitor (4.6)."""
    if request.method == 'POST':
        finalidade = request.POST.get('finalidade')

        if finalidade not in Finalidade.values:
            messages.error(request, 'Finalidade inválida.')
            return redirect('consentimento:gerenciar')

        ja_ativo = Consentimento.objects.filter(
            usuario=request.user, finalidade=finalidade, revogado_em__isnull=True
        ).exists()

        if not ja_ativo:
            Consentimento.objects.create(usuario=request.user, finalidade=finalidade)
            messages.success(request, 'Consentimento registrado.')

        return redirect('consentimento:gerenciar')

    consentimentos_ativos = Consentimento.objects.filter(
        usuario=request.user, revogado_em__isnull=True
    )
    finalidades_aceitas = set(consentimentos_ativos.values_list('finalidade', flat=True))
    finalidades_pendentes = [
        (valor, rotulo) for valor, rotulo in Finalidade.choices if valor not in finalidades_aceitas
    ]

    return render(request, 'consentimento/gerenciar.html', {
        'consentimentos_ativos': consentimentos_ativos,
        'finalidades_pendentes': finalidades_pendentes,
    })
