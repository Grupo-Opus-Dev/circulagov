import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse

from .models import MINUTOS_VALIDADE_TOKEN, TokenRecuperacaoSenha

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
            enviar_email_recuperacao(request, usuario)

        # Registra a solicitacao de recuperacao (issue #30), independente do usuario existir.
        logger.info('solicitacao de recuperacao de senha para username=%s', nome_usuario)

        messages.success(request, MENSAGEM_GENERICA)
        return redirect('login')

    return render(request, 'recuperacao_senha/solicitar.html')


def enviar_email_recuperacao(request, usuario, nova_conta=False):
    """Manda o link de definição de senha.

    Serve a dois casos: quem esqueceu a senha, e quem acabou de ter a
    conta criada pela gestão e ainda não tem senha nenhuma. O link e o
    token são os mesmos, só o texto muda.
    """
    registro, valor_bruto = TokenRecuperacaoSenha.gerar(usuario)
    link = request.build_absolute_uri(
        reverse('recuperacao_senha:redefinir', args=[valor_bruto])
    )

    if nova_conta:
        assunto = 'CirculaGov: sua conta foi criada'
        abertura = (
            f'Olá, {usuario.get_username()}.\n\n'
            f'Uma conta no CirculaGov foi criada para você, com o usuário '
            f'"{usuario.get_username()}". Use o link abaixo para criar a '
            f'sua senha.'
        )
        fechamento = (
            '\n\nSe o link expirar, use "Esqueci minha senha" na tela de '
            'login, informando o seu usuário.'
        )
    else:
        assunto = 'CirculaGov: recuperação de senha'
        abertura = (
            f'Olá, {usuario.get_username()}.\n\n'
            f'Use o link abaixo para redefinir sua senha.'
        )
        fechamento = ''

    send_mail(
        subject=assunto,
        message=(
            f'{abertura} Ele vale por {MINUTOS_VALIDADE_TOKEN} minutos '
            f'e só pode ser usado uma vez.\n\n{link}{fechamento}'
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

        # Sem isto, a recuperacao aceitava qualquer senha, ate "1", porque
        # so conferia se as duas digitadas batiam. Os validadores valiam
        # no cadastro e na troca de senha, mas nao aqui.
        try:
            validate_password(senha_nova, registro.usuario)
        except ValidationError as erros:
            logger.info(
                'falha na recuperacao de senha, motivo=senha_recusada_pelos_validadores, username=%s',
                registro.usuario.get_username(),
            )
            for erro in erros.messages:
                messages.error(request, erro)
            return render(request, 'recuperacao_senha/redefinir.html', {'token': token})

        registro.usuario.set_password(senha_nova)
        registro.usuario.save()
        registro.marcar_usado()

        # Recuperacao concluida com sucesso (issue #31).
        logger.info('recuperacao de senha concluida com sucesso, username=%s', registro.usuario.get_username())

        messages.success(request, 'Senha redefinida. Faça login com a nova senha.')
        return redirect('login')

    return render(request, 'recuperacao_senha/redefinir.html', {'token': token})
