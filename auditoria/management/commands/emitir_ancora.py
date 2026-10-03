from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from auditoria.ancoras import arquivo_de_ancoras, verificar_com_ancoras
from auditoria.integridade import gerar_ancora


class Command(BaseCommand):
    help = (
        'Emite uma âncora do log de segurança: o número de linhas e a '
        'assinatura da última, assinados com a chave do log. Guardada fora '
        'do servidor, permite descobrir depois se o final do log foi apagado.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--email', action='append', default=[],
            help='Envia a âncora para este endereço (pode repetir). É assim '
                 'que ela sai do servidor.')

    def handle(self, *args, **options):
        resultado = verificar_com_ancoras()
        if not resultado.integro:
            # Ancorar um log já adulterado carimbaria o estrago como válido.
            raise CommandError(
                f'O log não está íntegro, nenhuma âncora foi emitida: '
                f'{resultado.motivo}')
        if resultado.total_linhas == 0:
            raise CommandError('O log está vazio, não há o que ancorar.')

        agora = timezone.now().isoformat(timespec='seconds')
        ancora = gerar_ancora(
            settings.CHAVE_INTEGRIDADE_LOGS, resultado.total_linhas,
            resultado.ultimo_mac, agora)

        caminho = arquivo_de_ancoras()
        with caminho.open('a', encoding='utf-8') as arquivo:
            arquivo.write(ancora + '\n')

        self.stdout.write(ancora)
        self.stdout.write(self.style.SUCCESS(
            f'Âncora gravada em {caminho.name} ({resultado.total_linhas} '
            f'linhas). Essa cópia fica no mesmo servidor do log: guarde a '
            f'linha acima também em outro lugar.'))

        for destino in options['email']:
            send_mail(
                subject='CirculaGov: âncora do log de segurança',
                message=(
                    'Guarde esta linha. Ela permite conferir depois se o '
                    'final do log foi apagado (python manage.py '
                    'verificar_logs --ancoras ARQUIVO).\n\n' + ancora + '\n'),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[destino])
            self.stdout.write(f'Âncora enviada para {destino}.')
