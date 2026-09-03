import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

# Tempo de validade do token, em minutos (requisito 2.3).
MINUTOS_VALIDADE_TOKEN = 30


class TokenRecuperacaoSenha(models.Model):
    """Token de uso único para o fluxo de recuperação de senha.

    Guardamos só o hash do token, nunca o valor bruto. Assim, quem tiver
    acesso ao banco não consegue resetar a senha de ninguém sozinho.
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tokens_recuperacao_senha',
    )
    token_hash = models.CharField(max_length=64, unique=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    usado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'token de recuperação de senha'
        verbose_name_plural = 'tokens de recuperação de senha'

    def __str__(self):
        return f'Token de {self.usuario} (criado em {self.criado_em:%d/%m/%Y %H:%M})'

    @staticmethod
    def _hash(valor_bruto):
        return hashlib.sha256(valor_bruto.encode()).hexdigest()

    @classmethod
    def gerar(cls, usuario):
        """Cria um token novo e devolve (registro, valor_bruto).

        O valor_bruto só existe em memória nesta chamada. É o que vai no
        link enviado por e-mail. Depois disso, ninguém recupera o valor
        original a partir do banco, só valida se um valor bate com o hash.

        secrets.token_urlsafe usa o CSPRNG do sistema operacional, por
        isso não é previsível como um contador sequencial seria.
        """
        valor_bruto = secrets.token_urlsafe(32)
        registro = cls.objects.create(
            usuario=usuario,
            token_hash=cls._hash(valor_bruto),
            expira_em=timezone.now() + timezone.timedelta(minutes=MINUTOS_VALIDADE_TOKEN),
        )
        return registro, valor_bruto

    @classmethod
    def validar(cls, valor_bruto):
        """Devolve o token válido, ou None se não existir, já tiver
        sido usado ou estiver expirado.

        De propósito não diferenciamos esses três casos pra quem chama
        essa função. A mensagem de erro deve ser sempre genérica
        (requisito 2.5), pra não dar pista a quem tentar adivinhar ou
        reaproveitar um token de outra pessoa.
        """
        try:
            registro = cls.objects.get(token_hash=cls._hash(valor_bruto))
        except cls.DoesNotExist:
            return None

        if registro.usado_em is not None:
            return None

        if timezone.now() > registro.expira_em:
            return None

        return registro

    def marcar_usado(self):
        """Invalida o token (requisito 2.4). Chamar só depois que a
        senha nova já foi salva com sucesso."""
        self.usado_em = timezone.now()
        self.save(update_fields=['usado_em'])
