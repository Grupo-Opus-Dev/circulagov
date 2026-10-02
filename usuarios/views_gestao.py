"""Área de gestão de usuários, com a interface da própria aplicação.

Existe porque o admin do Django mostra os campos genéricos dele e não o
que importa neste sistema: quem tem 2FA ativo, quem tem aluno vinculado,
quem consentiu o quê. O admin continua disponível como recurso de
emergência.

Tudo aqui exige is_staff. Toda alteração entra no log de segurança,
porque mexer em conta alheia muda quem tem acesso ao sistema.
"""

import logging

from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.forms import SetPasswordForm
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from recuperacao_senha.views import enviar_email_recuperacao

from .decoradores import exige_gestor
from .forms import FormularioEditarUsuario, FormularioNovoUsuario

Usuario = get_user_model()

logger = logging.getLogger('seguranca.gestao')


def _consulta_com_relacoes():
    # select_related nas duas relações um-para-um evita uma consulta por
    # linha só para saber se há aluno e 2FA.
    return Usuario.objects.select_related('aluno', 'dispositivo_totp')


@exige_gestor
def lista_usuarios(request):
    busca = request.GET.get('busca', '').strip()
    usuarios = _consulta_com_relacoes()

    if busca:
        usuarios = usuarios.filter(
            Q(username__icontains=busca)
            | Q(email__icontains=busca)
            | Q(aluno__nome_completo__icontains=busca)
            | Q(aluno__ra__icontains=busca)
        )

    return render(request, 'usuarios/gestao/lista.html', {
        'usuarios': usuarios.order_by('username'),
        'busca': busca,
        'total': Usuario.objects.count(),
    })


@exige_gestor
def detalhe_usuario(request, usuario_id):
    usuario = get_object_or_404(_consulta_com_relacoes(), pk=usuario_id)
    return render(request, 'usuarios/gestao/detalhe.html', {
        'usuario_exibido': usuario,
        'consentimentos': usuario.consentimentos.order_by('-aceito_em'),
        'e_a_propria_conta': usuario.pk == request.user.pk,
    })


@exige_gestor
def novo_usuario(request):
    if request.method == 'POST':
        formulario = FormularioNovoUsuario(request.POST)
        if formulario.is_valid():
            criado = formulario.save()
            logger.info(
                'usuario criado, username=%s, is_staff=%s, criado_por=%s',
                criado.get_username(), criado.is_staff,
                request.user.get_username(),
            )
            messages.success(
                request, f'Usuário {criado.get_username()} criado.')
            return redirect('usuarios:gestao_detalhe', usuario_id=criado.pk)
    else:
        formulario = FormularioNovoUsuario()

    return render(request, 'usuarios/gestao/novo.html', {
        'formulario': formulario,
    })


@exige_gestor
def editar_usuario(request, usuario_id):
    usuario = get_object_or_404(_consulta_com_relacoes(), pk=usuario_id)
    e_a_propria_conta = usuario.pk == request.user.pk

    if request.method == 'POST':
        formulario = FormularioEditarUsuario(request.POST, instance=usuario)

        # Deixar alguém se rebaixar ou se desativar sozinho é o caminho
        # mais curto pro sistema ficar sem administrador nenhum.
        if e_a_propria_conta:
            if not formulario.data.get('is_staff'):
                formulario.add_error(
                    'is_staff', 'Você não pode remover o próprio acesso de gestão.')
            if not formulario.data.get('is_active'):
                formulario.add_error(
                    'is_active', 'Você não pode desativar a própria conta.')

        if formulario.is_valid():
            formulario.save()
            logger.info(
                'usuario alterado, username=%s, is_staff=%s, is_active=%s, '
                'alterado_por=%s',
                usuario.get_username(), usuario.is_staff, usuario.is_active,
                request.user.get_username(),
            )
            messages.success(request, 'Dados atualizados.')
            return redirect('usuarios:gestao_detalhe', usuario_id=usuario.pk)
    else:
        formulario = FormularioEditarUsuario(instance=usuario)

    return render(request, 'usuarios/gestao/editar.html', {
        'formulario': formulario,
        'usuario_exibido': usuario,
        'e_a_propria_conta': e_a_propria_conta,
    })


@exige_gestor
def definir_senha(request, usuario_id):
    """Administrador escolhe a senha nova.

    Serve pra conta cujo e-mail não recebe mensagem, como as contas de
    avaliação. Tem o custo de o administrador passar a conhecer a senha
    da pessoa, e por isso a tela avisa e oferece o caminho por e-mail.
    """
    usuario = get_object_or_404(Usuario, pk=usuario_id)

    if request.method == 'POST':
        formulario = SetPasswordForm(usuario, request.POST)
        if formulario.is_valid():
            formulario.save()

            # Sem isto, trocar a propria senha derruba a propria sessao.
            if usuario.pk == request.user.pk:
                update_session_auth_hash(request, usuario)

            logger.warning(
                'senha definida por administrador, username=%s, definida_por=%s',
                usuario.get_username(), request.user.get_username(),
            )
            messages.success(
                request, f'Senha de {usuario.get_username()} redefinida.')
            return redirect('usuarios:gestao_detalhe', usuario_id=usuario.pk)
    else:
        formulario = SetPasswordForm(usuario)

    for campo in formulario.fields.values():
        campo.widget.attrs['class'] = (
            'w-full rounded-md border border-slate-300 px-3 py-2 text-sm '
            'focus:outline-none focus:ring-2 focus:ring-blue-600 '
            'focus:border-blue-600'
        )

    return render(request, 'usuarios/gestao/definir_senha.html', {
        'formulario': formulario,
        'usuario_exibido': usuario,
    })


@exige_gestor
@require_POST
def enviar_link_de_senha(request, usuario_id):
    """Dispara o mesmo e-mail do "Esqueci minha senha".

    Melhor que definir a senha na mão: ninguém além do dono fica
    sabendo qual é.
    """
    usuario = get_object_or_404(Usuario, pk=usuario_id)

    if not usuario.email:
        messages.error(
            request, 'Esta conta não tem e-mail cadastrado. '
                     'Cadastre um e-mail ou defina a senha manualmente.')
        return redirect('usuarios:gestao_detalhe', usuario_id=usuario.pk)

    enviar_email_recuperacao(request, usuario)
    logger.info(
        'link de redefinicao enviado por administrador, username=%s, '
        'enviado_por=%s',
        usuario.get_username(), request.user.get_username(),
    )
    messages.success(request, f'Link enviado para {usuario.email}.')
    return redirect('usuarios:gestao_detalhe', usuario_id=usuario.pk)


@exige_gestor
@require_POST
def remover_dois_fatores(request, usuario_id):
    """Única saída para quem perdeu o app autenticador.

    Sem isto a pessoa fica trancada fora da conta para sempre, porque o
    login passa a exigir um código que ela não consegue mais gerar.
    """
    usuario = get_object_or_404(_consulta_com_relacoes(), pk=usuario_id)
    dispositivo = getattr(usuario, 'dispositivo_totp', None)

    if dispositivo is None:
        messages.error(request, 'Esta conta não tem 2FA configurado.')
    else:
        dispositivo.delete()
        # Removido do log em nivel de aviso: reduz a protecao da conta,
        # entao precisa aparecer numa leitura rapida do arquivo.
        logger.warning(
            '2FA removido por administrador, username=%s, removido_por=%s',
            usuario.get_username(), request.user.get_username(),
        )
        messages.success(
            request, f'2FA de {usuario.get_username()} removido. '
                     'A pessoa pode cadastrar um aparelho novo.')

    return redirect('usuarios:gestao_detalhe', usuario_id=usuario.pk)
