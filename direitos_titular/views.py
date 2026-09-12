from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render


def _coletar_dados_pessoais(usuario):
    """Reúne os dados pessoais de um usuário num dicionário só.

    Usado tanto pela consulta (#51) quanto pela exportação (#52), pra não
    duplicar a lógica de quais dados existem sobre o titular.
    """
    dados = {
        'Nome de usuário': usuario.username,
        'E-mail': usuario.email or 'não informado',
        'Data de entrada no sistema': usuario.date_joined,
    }

    if hasattr(usuario, 'aluno'):
        dados['RA'] = usuario.aluno.ra
        dados['Nome completo'] = usuario.aluno.nome_completo

    return dados


@login_required
def consultar(request):
    """Requisito 4.8: usuário vê quais dados pessoais o sistema tem sobre ele."""
    dados_pessoais = _coletar_dados_pessoais(request.user)
    consentimentos = request.user.consentimentos.all()

    return render(request, 'direitos_titular/consultar.html', {
        'dados_pessoais': dados_pessoais,
        'consentimentos': consentimentos,
    })


@login_required
def exportar(request):
    """Requisito 4.9: usuário baixa os próprios dados em formato JSON."""
    dados_pessoais = _coletar_dados_pessoais(request.user)
    consentimentos = [
        {
            'finalidade': c.get_finalidade_display(),
            'ativo': c.ativo,
            'versao_termos': c.versao_termos,
            'aceito_em': c.aceito_em,
        }
        for c in request.user.consentimentos.all()
    ]

    payload = {
        'dados_pessoais': dados_pessoais,
        'consentimentos': consentimentos,
    }

    resposta = JsonResponse(payload, json_dumps_params={
                            'ensure_ascii': False, 'indent': 2})
    resposta['Content-Disposition'] = 'attachment; filename="meus_dados_circulagov.json"'
    return resposta
