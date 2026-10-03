import logging
import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from . import limite, qrcode_totp
from .models import DispositivoTOTP

Usuario = get_user_model()

CHAVE_USUARIO_PENDENTE = 'usuario_pendente_id'
CHAVE_PENDENTE_DESDE = 'usuario_pendente_desde'

# Quanto tempo a pessoa tem pra digitar o código depois de acertar a senha.
# Sem prazo, a sessão com a senha já validada ficaria aberta até expirar
# por inatividade, e como ela renova a cada requisição, quase indefinidamente.
SEGUNDOS_PARA_O_SEGUNDO_FATOR = getattr(
    settings, 'SEGUNDOS_PARA_O_SEGUNDO_FATOR', 5 * 60)

logger = logging.getLogger('seguranca.dois_fatores')


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
            # Requisito 5.2: evento separado do "código correto" (que já é
            # logado dentro de verificar_codigo), porque ativar o 2FA é uma
            # mudança de configuração da conta, não só uma checagem de código.
            logger.info('2FA ativado, username=%s', request.user.get_username())
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
        # SVG embutido no HTML, gerado no servidor. Ver qrcode_totp.py.
        'qrcode_svg': qrcode_totp.gerar_svg(uri),
    })


def iniciar_etapa_pendente(sessao, usuario_id):
    """Guarda que a senha foi aceita e quando, pra etapa do código expirar."""
    sessao[CHAVE_USUARIO_PENDENTE] = usuario_id
    sessao[CHAVE_PENDENTE_DESDE] = int(time.time())


def _encerrar_etapa_pendente(sessao):
    sessao.pop(CHAVE_USUARIO_PENDENTE, None)
    sessao.pop(CHAVE_PENDENTE_DESDE, None)


def verificar(request):
    """Segunda etapa do login. Enquanto usuario_pendente_id existir na
    sessão, o usuário passou pela senha mas ainda não está autenticado -
    login() só é chamado aqui, depois do código certo."""
    pendente_id = request.session.get(CHAVE_USUARIO_PENDENTE)

    if pendente_id is None:
        return redirect('login')

    desde = request.session.get(CHAVE_PENDENTE_DESDE, 0)
    if time.time() - desde > SEGUNDOS_PARA_O_SEGUNDO_FATOR:
        _encerrar_etapa_pendente(request.session)
        logger.warning('etapa do 2FA expirou, usuario_id=%s', pendente_id)
        messages.error(request, 'Tempo esgotado. Entre de novo com usuário e senha.')
        return redirect('login')

    if request.method == 'POST':
        usuario = Usuario.objects.get(pk=pendente_id)

        if limite.bloqueado(pendente_id):
            # Nao confere o codigo (nem o certo passa) e nao soma falha:
            # somar durante o bloqueio renovaria o prazo.
            logger.warning(
                'bloqueio por forca bruta no 2FA, username=%s',
                usuario.get_username())
            messages.error(
                request,
                'Muitas tentativas com código incorreto. '
                'Aguarde alguns minutos e entre de novo.')
            return render(request, 'dois_fatores/verificar.html')

        codigo = request.POST.get('codigo', '')
        dispositivo = DispositivoTOTP.objects.filter(
            usuario_id=pendente_id, confirmado=True
        ).first()

        if dispositivo and dispositivo.verificar_codigo(codigo):
            _encerrar_etapa_pendente(request.session)
            limite.limpar(pendente_id)
            login(request, usuario)
            return redirect('usuarios:inicio')

        limite.registrar_falha(pendente_id)
        messages.error(request, 'Código inválido.')

    return render(request, 'dois_fatores/verificar.html')
