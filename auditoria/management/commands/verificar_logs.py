from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from auditoria.integridade import verificar_arquivo


class Command(BaseCommand):
    help = 'Verifica se o log de segurança foi alterado (requisito 5.3).'

    def handle(self, *args, **options):
        caminho = settings.LOG_DIR / 'seguranca.log'
        resultado = verificar_arquivo(caminho, settings.CHAVE_INTEGRIDADE_LOGS)

        if resultado.integro:
            self.stdout.write(self.style.SUCCESS(
                f'Log íntegro: {resultado.total_linhas} linhas verificadas.'
            ))
            # Guardar esse valor fora do servidor permite detectar depois
            # se linhas do final do arquivo foram apagadas.
            self.stdout.write(f'Último MAC da cadeia: {resultado.ultimo_mac}')
            return

        # CommandError faz o comando terminar com código de erro, útil pra
        # automatizar a verificação.
        raise CommandError(
            f'Log ALTERADO na linha {resultado.linha_com_problema}: {resultado.motivo}'
        )
