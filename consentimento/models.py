from django.conf import settings
from django.db import models
from django.utils import timezone

# Versao atual dos termos. Se o texto mudar, sobe esse numero, e todo
# consentimento antigo fica associado a versao velha (requisito 4.7).
VERSAO_TERMOS_ATUAL = '1.0'


class Finalidade(models.TextChoices):
    """Cada finalidade e um motivo especifico pelo qual usamos um dado
    pessoal (requisito 4.2). Nao existe um consentimento generico "aceito
    tudo": cada finalidade e aceita ou recusada separadamente.
    """

    CADASTRO = 'cadastro', 'Cadastro e autenticação na plataforma'
    COMUNICACOES = 'comunicacoes', 'Comunicações por e-mail sobre empréstimos'


class Consentimento(models.Model):
    """Registro de consentimento de um usuário para uma finalidade
    específica (requisitos 4.4 e 4.5).

    Cada linha é um consentimento para UMA finalidade. Se o usuário
    aceita duas finalidades, são duas linhas. Isso evita o problema de
    "aceitar tudo de uma vez", que não deixa claro pra que cada dado é
    usado.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='consentimentos',
    )
    finalidade = models.CharField(max_length=20, choices=Finalidade.choices)
    versao_termos = models.CharField(max_length=10, default=VERSAO_TERMOS_ATUAL)
    aceito_em = models.DateTimeField(auto_now_add=True)
    revogado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'consentimento'
        verbose_name_plural = 'consentimentos'
        # Um usuario tem no maximo um consentimento ATIVO por finalidade.
        # Revogar e depois aceitar de novo cria uma linha nova, mantendo
        # o historico completo em vez de sobrescrever.
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'finalidade'],
                condition=models.Q(revogado_em__isnull=True),
                name='um_consentimento_ativo_por_finalidade',
            )
        ]

    def __str__(self):
        estado = 'revogado' if self.revogado_em else 'ativo'
        return f'{self.usuario} — {self.get_finalidade_display()} ({estado})'

    @property
    def ativo(self):
        return self.revogado_em is None

    def revogar(self):
        """Requisito 4.6, usado pela issue do Vitor. Fica aqui porque é
        uma operação simples do próprio model, não precisa de view nova
        além da que ele for construir."""
        self.revogado_em = timezone.now()
        self.save(update_fields=['revogado_em'])
