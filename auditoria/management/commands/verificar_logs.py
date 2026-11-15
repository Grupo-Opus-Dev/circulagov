import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from auditoria.ancoras import verificar_com_ancoras
from auditoria.integridade import decodificar_chave


class Command(BaseCommand):
    help = 'Verifica se o log de segurança foi alterado (requisito 5.3).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ancoras', action='append', default=[], metavar='ARQUIVO',
            help='Arquivo com âncoras guardadas fora do servidor (pode '
                 'repetir). As de logs/ancoras.log entram sempre que o '
                 'arquivo verificado é o log atual.')
        parser.add_argument(
            '--arquivo', metavar='ARQUIVO',
            help='Verifica este arquivo em vez do log atual, por exemplo um '
                 'log arquivado na rotação da chave.')
        parser.add_argument(
            '--chave-arquivo', metavar='ARQUIVO',
            help='Arquivo com a chave (base64) que assinou o log, quando ela '
                 'não é a atual. Com "-", lê da entrada padrão. A chave '
                 'não vai na linha de comando para não aparecer na lista '
                 'de processos nem no histórico.')

    def handle(self, *args, **options):
        chave = None
        if options['chave_arquivo']:
            try:
                if options['chave_arquivo'] == '-':
                    chave = sys.stdin.read().strip()
                else:
                    chave = Path(options['chave_arquivo']).read_text(
                        encoding='utf-8').strip()
                decodificar_chave(chave)
            except (OSError, ValueError) as erro:
                raise CommandError(f'Chave inválida: {erro}')

        caminho_do_log = None
        if options['arquivo']:
            caminho_do_log = Path(options['arquivo'])
            if not caminho_do_log.exists():
                raise CommandError(f'Arquivo não encontrado: {caminho_do_log}')

        resultado = verificar_com_ancoras(
            [Path(caminho) for caminho in options['ancoras']],
            caminho_do_log=caminho_do_log, chave=chave)

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
