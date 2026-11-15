"""Arquiva o log de segurança para a rotação da chave (requisito 5.3).

Usado por deploy/rotacionar-chave-do-log.sh, com o container web parado.
Confere o log com a chave atual, emite uma âncora de fechamento e renomeia
seguranca.log e ancoras.log com a data. Na próxima subida, a aplicação
começa uma cadeia nova, assinada com a chave nova.
"""
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from auditoria.ancoras import arquivo_de_ancoras, verificar_com_ancoras
from auditoria.integridade import gerar_ancora


class Command(BaseCommand):
    help = ('Arquiva o log de segurança e as âncoras com a data, depois de '
            'conferir a integridade e emitir uma âncora de fechamento.')

    def add_arguments(self, parser):
        parser.add_argument(
            '--carimbo', default=None,
            help='Sufixo dos arquivos arquivados (padrão: data e hora UTC).')
        parser.add_argument(
            '--email', action='append', default=[],
            help='Envia a âncora de fechamento para este endereço.')

    def handle(self, *args, **options):
        log = settings.LOG_DIR / 'seguranca.log'
        ancoras = arquivo_de_ancoras()
        if not log.exists():
            raise CommandError('Não há log de segurança para arquivar.')

        resultado = verificar_com_ancoras()
        if not resultado.integro:
            # Arquivar um log adulterado esconderia o problema atrás da
            # chave nova. Primeiro se investiga.
            raise CommandError(
                f'O log não está íntegro, nada foi arquivado: '
                f'{resultado.motivo}')

        carimbo = options['carimbo'] or timezone.now().strftime('%Y%m%d-%H%M%S')
        destino_log = log.with_name(f'seguranca-{carimbo}.log')
        destino_ancoras = ancoras.with_name(f'ancoras-{carimbo}.log')
        if destino_log.exists() or destino_ancoras.exists():
            raise CommandError(f'Já existe um arquivo com o carimbo {carimbo}.')

        if resultado.total_linhas:
            # A âncora de fechamento registra o tamanho final do arquivo:
            # cortar o fim do log arquivado depois também é detectado.
            ancora = gerar_ancora(
                settings.CHAVE_INTEGRIDADE_LOGS, resultado.total_linhas,
                resultado.ultimo_mac,
                timezone.now().isoformat(timespec='seconds'))
            with ancoras.open('a', encoding='utf-8') as arquivo:
                arquivo.write(ancora + '\n')
            self.stdout.write(ancora)
            for destino in options['email']:
                send_mail(
                    subject='CirculaGov: âncora de fechamento do log',
                    message=('Âncora de fechamento do log arquivado como '
                             f'{destino_log.name}. Guarde esta linha.\n\n'
                             + ancora + '\n'),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[destino])

        log.rename(destino_log)
        if ancoras.exists():
            ancoras.rename(destino_ancoras)

        self.stdout.write(self.style.SUCCESS(
            f'Log arquivado em {destino_log.name} ({resultado.total_linhas} '
            f'linhas) e âncoras em {destino_ancoras.name}.'))
