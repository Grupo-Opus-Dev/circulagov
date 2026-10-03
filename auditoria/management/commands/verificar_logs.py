from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from auditoria.ancoras import verificar_com_ancoras


class Command(BaseCommand):
    help = 'Verifica se o log de segurança foi alterado (requisito 5.3).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ancoras', action='append', default=[], metavar='ARQUIVO',
            help='Arquivo com âncoras guardadas fora do servidor (pode '
                 'repetir). As de logs/ancoras.log sempre entram.')

    def handle(self, *args, **options):
        resultado = verificar_com_ancoras(
            [Path(caminho) for caminho in options['ancoras']])

        if not resultado.integro:
            # CommandError faz o comando terminar com código de erro, útil
            # pra automatizar a verificação.
            if resultado.linha_com_problema:
                raise CommandError(
                    f'Log ALTERADO na linha {resultado.linha_com_problema}: '
                    f'{resultado.motivo}')
            raise CommandError(f'Log ALTERADO: {resultado.motivo}')

        self.stdout.write(self.style.SUCCESS(
            f'Log íntegro: {resultado.total_linhas} linhas verificadas.'))
        self.stdout.write(f'Último MAC da cadeia: {resultado.ultimo_mac}')
        if resultado.ancoras_conferidas:
            self.stdout.write(self.style.SUCCESS(
                f'{resultado.ancoras_conferidas} âncora(s) conferida(s): o '
                f'final do log não foi cortado desde a mais recente.'))
        else:
            self.stdout.write(self.style.WARNING(
                'Nenhuma âncora conferida: apagar as últimas linhas do log, '
                'ou o arquivo inteiro, não seria detectado. Veja '
                'emitir_ancora.'))
