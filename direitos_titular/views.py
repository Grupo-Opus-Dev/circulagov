from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def consultar(request):
    """Requisito 4.8: usuário vê quais dados pessoais o sistema tem sobre ele."""
    usuario = request.user

    dados_pessoais = {
        'Nome de usuário': usuario.username,
        'E-mail': usuario.email or 'não informado',
        'Data de entrada no sistema': usuario.date_joined,
    }

    if hasattr(usuario, 'aluno'):
        dados_pessoais['RA'] = usuario.aluno.ra
        dados_pessoais['Nome completo'] = usuario.aluno.nome_completo

    consentimentos = usuario.consentimentos.all()

    return render(request, 'direitos_titular/consultar.html', {
        'dados_pessoais': dados_pessoais,
        'consentimentos': consentimentos,
    })