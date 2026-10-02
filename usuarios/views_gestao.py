"""Área de gestão de usuários, com a interface da própria aplicação.

Existe porque o admin do Django mostra os campos genéricos dele e não o
que importa neste sistema: quem tem 2FA ativo, quem tem aluno vinculado,
quem consentiu o quê. O admin continua disponível como recurso de
emergência.

Tudo aqui exige is_staff, a mesma marcação que protege a tela de
integridade do log.
"""

import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import FormularioNovoUsuario

Usuario = get_user_model()

logger = logging.getLogger('seguranca.gestao')


@staff_member_required
def lista_usuarios(request):
    busca = request.GET.get('busca', '').strip()

    # select_related nas duas relações um-para-um evita uma consulta por
    # linha da tabela só para saber se há aluno e 2FA.
    usuarios = Usuario.objects.select_related('aluno', 'dispositivo_totp')

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


@staff_member_required
def detalhe_usuario(request, usuario_id):
    usuario = get_object_or_404(
        Usuario.objects.select_related('aluno', 'dispositivo_totp'),
        pk=usuario_id,
    )
    return render(request, 'usuarios/gestao/detalhe.html', {
        'usuario_exibido': usuario,
        'consentimentos': usuario.consentimentos.order_by('-aceito_em'),
    })


@staff_member_required
def novo_usuario(request):
    if request.method == 'POST':
        formulario = FormularioNovoUsuario(request.POST)
        if formulario.is_valid():
            criado = formulario.save()
            # Criar conta é mudança de quem tem acesso ao sistema, então
            # entra no log de segurança junto com quem fez.
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
