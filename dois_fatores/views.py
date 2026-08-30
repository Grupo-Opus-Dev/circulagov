from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .models import DispositivoTOTP

Usuario = get_user_model()

CHAVE_USUARIO_PENDENTE = 'usuario_pendente_id'


@login_required
def cadastrar(request):
    """Tela onde o usuário liga o 2FA na própria conta e confirma que
    conseguiu gerar um código certo com o app autenticador."""
    dispositivo, _criado = DispositivoTOTP.objects.get_or_create(usuario=request.user)

    if request.method == 'POST':
        codigo = request.POST.get('codigo', '')
        if dispositivo.verificar_codigo(codigo):
            dispositivo.confirmado = True
            dispositivo.save()
            messages.success(request, 'Autenticação de dois fatores ativada.')
            return redirect('usuarios:inicio')
        messages.error(request, 'Código inválido. Confira o relógio do app autenticador.')

    gerador_totp = dispositivo.totp()
    uri = gerador_totp.provisioning_uri(
        name=request.user.get_username(), issuer_name='CirculaGov'
    )
    return render(request, 'dois_fatores/cadastrar.html', {
        'dispositivo': dispositivo,
        'uri': uri,
    })


def verificar(request):
    """Segunda etapa do login. Enquanto usuario_pendente_id existir na
    sessão, o usuário passou pela senha mas ainda não está autenticado -
    login() só é chamado aqui, depois do código certo."""
    pendente_id = request.session.get(CHAVE_USUARIO_PENDENTE)

    if pendente_id is None:
        return redirect('login')

    if request.method == 'POST':
        codigo = request.POST.get('codigo', '')
        dispositivos_confirmados = DispositivoTOTP.objects.filter(
            usuario_id=pendente_id, confirmado=True
        )
        dispositivo = dispositivos_confirmados.first()

        if dispositivo and dispositivo.verificar_codigo(codigo):
            del request.session[CHAVE_USUARIO_PENDENTE]
            usuario = Usuario.objects.get(pk=pendente_id)
            login(request, usuario)
            return redirect('usuarios:inicio')

        messages.error(request, 'Código inválido.')

    return render(request, 'dois_fatores/verificar.html')
