import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse

from .models import TokenRecuperacaoSenha

Usuario = get_user_model()

logger = logging.getLogger('seguranca.recuperacao_senha')

MENSAGEM_GENERICA = (
    'Se o usuário existir, enviamos um e-mail com instruções de recuperação.'
)


def solicitar(request):
    """Primeira tela: usuário informa o nome de usuário.

    A resposta é sempre a mesma, exista ou não esse usuário no banco.
    Isso evita que alguém descubra quais contas existem só testando
    nomes de usuário no formulário (enumeração de contas).
    """
    if request.method == 'POST':
        nome_usuario = request.POST.get('username', '').strip()
        usuario = Usuario.objects.filter(username=nome_usuario).first()

        if usuario is not None:
            _enviar_email_recuperacao(request, usuario)

        # Registra a solicitacao de recuperacao (issue #30), independente do usuario existir.
        logger.info('solicitacao de recuperacao de senha para username=%s', nome_usuario)

        messages.success(request, MENSAGEM_GENERICA)
        return redirect('login')

    return render(request, 'recuperacao_senha/solicitar.html')


def _enviar_email_recuperacao(request, usuario):
    registro, valor_bruto = TokenRecuperacaoSenha.gerar(usuario)
    link = request.build_absolute_uri(
        reverse('recuperacao_senha:redefinir', args=[valor_bruto])
    )
    send_mail(
        subject='CirculaGov: recuperação de senha',
        message=(
            f'Olá, {usuario.get_username()}.\n\n'
            f'Use o link abaixo para redefinir sua senha. '
            f'Ele vale por {registro.expira_em - registro.criado_em} '
            f'e só pode ser usado uma vez.\n\n{link}'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[usuario.email or f'{usuario.username}@exemplo.local'],
    )


def redefinir(request, token):
    """Segunda tela: usuário define a senha nova.

    Se o token não for válido (não existe, já foi usado ou expirou),
    mostramos um erro genérico e não deixamos passar da tela de senha.
    """
    registro, motivo = TokenRecuperacaoSenha.buscar_com_motivo(token)

    if motivo is not None:
        # Token invalido, expirado ou ja usado, o motivo vai so pro log (issue #31), a resposta pro usuario continua generica.
        logger.warning('falha na recuperacao de senha, motivo=%s', motivo)
        return render(request, 'recuperacao_senha/token_invalido.html', status=400)

    if request.method == 'POST':
        senha_nova = request.POST.get('senha_nova', '')
        confirmacao = request.POST.get('confirmacao', '')

        if not senha_nova or senha_nova != confirmacao:
            # Confirmacao nao bate, nao e um evento grave de seguranca, mas ainda entra no log (issue #31).
            logger.info(
                'falha na recuperacao de senha, motivo=confirmacao_nao_confere, username=%s',
                registro.usuario.get_username(),
            )
            messages.error(request, 'As senhas digitadas não conferem.')
            return render(request, 'recuperacao_senha/redefinir.html', {'token': token})

        registro.usuario.set_password(senha_nova)
        registro.usuario.save()
        registro.marcar_usado()

        # Recuperacao concluida com sucesso (issue #31).
        logger.info('recuperacao de senha concluida com sucesso, username=%s', registro.usuario.get_username())

        messages.success(request, 'Senha redefinida. Faça login com a nova senha.')
        return redirect('login')

    return render(request, 'recuperacao_senha/redefinir.html', {'token': token})
