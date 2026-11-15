"""Apaga o que a política de retenção manda apagar (requisito 4.3).

Tokens de recuperação de senha: valem 30 minutos e depois não servem para
nada, mas ficavam na tabela até a conta ser excluída. Contadores de
tentativas vencidos: já são limpos aos poucos pelo próprio login, e aqui
saem todos de uma vez. Sessões vencidas: o Django não apaga sozinho, e
cada uma guarda o id da conta.

O log de segurança fica de fora de propósito. Cada linha é assinada e
encadeada com a anterior (auditoria/integridade.py): apagar ou reescrever
uma linha, mesmo para tirar um nome de usuário, quebra a cadeia e é
exatamente o que a verificação existe para acusar. O log sai inteiro, na
rotação (ver docs/INTEGRIDADE_LOGS.md).
"""
import logging
import time
from datetime import timedelta

from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from recuperacao_senha.models import TokenRecuperacaoSenha
from usuarios.models import ContadorDeTentativas

logger = logging.getLogger('seguranca.retencao')

# Dias que um token vencido ainda fica guardado, para dar tempo de
# investigar um pedido de recuperação suspeito.
DIAS_DE_RETENCAO_DOS_TOKENS = 7


class Command(BaseCommand):
    help = ('Apaga tokens de recuperação de senha, contadores de '
            'tentativas e sessões vencidos, conforme a política de retenção.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Só mostra o que seria apagado, sem apagar nada.')
        parser.add_argument(
            '--dias', type=int, default=DIAS_DE_RETENCAO_DOS_TOKENS,
            help='Apaga tokens vencidos há mais que estes dias '
                 f'(padrão: {DIAS_DE_RETENCAO_DOS_TOKENS}).')

    def handle(self, *args, **options):
        dias = options['dias']
        if dias < 0:
            raise CommandError('--dias não pode ser negativo.')

        limite = timezone.now() - timedelta(days=dias)
        tokens = TokenRecuperacaoSenha.objects.filter(expira_em__lt=limite)
        contadores = ContadorDeTentativas.objects.filter(
            expira_em__lt=time.time())
        sessoes = Session.objects.filter(expire_date__lt=timezone.now())

        qtd_tokens = tokens.count()
        qtd_contadores = contadores.count()
        qtd_sessoes = sessoes.count()

        if options['dry_run']:
            self.stdout.write(
                f'Seriam apagados {qtd_tokens} token(s) de recuperação '
                f'vencidos há mais de {dias} dia(s), {qtd_contadores} '
                f'contador(es) de tentativas e {qtd_sessoes} sessão(ões) '
                f'vencidos. Nada foi apagado.')
            return

        tokens.delete()
        contadores.delete()
        sessoes.delete()
        logger.info(
            'expurgo por politica de retencao, tokens=%d, contadores=%d, '
            'sessoes=%d, dias=%d', qtd_tokens, qtd_contadores, qtd_sessoes,
            dias)
        self.stdout.write(self.style.SUCCESS(
            f'Apagados {qtd_tokens} token(s) de recuperação, '
            f'{qtd_contadores} contador(es) de tentativas e {qtd_sessoes} '
            f'sessão(ões) vencidas.'))
