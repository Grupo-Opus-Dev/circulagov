import re
from collections import Counter, defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

PADRAO_LINHA = re.compile(
    r'^(?P<data>\S+ \S+) (?P<nivel>\w+) (?P<logger>[\w.]+) (?P<mensagem>.+?)(?: \| mac=.+)?$'
)
PADRAO_USERNAME = re.compile(r'username=(?P<username>\S+)')


class Command(BaseCommand):
    help = (
        'Analisa o log de segurança e resume tentativas de login com falha '
        'por usuário, bloqueios por força bruta e eventos de 2FA (requisito 5.4).'
    )

    def handle(self, *args, **options):
        caminho = settings.LOG_DIR / 'seguranca.log'

        try:
            linhas = caminho.read_text(encoding='utf-8').splitlines()
        except FileNotFoundError:
            raise CommandError(f'Arquivo de log não encontrado: {caminho}')

        falhas_por_usuario = Counter()
        bloqueios_por_usuario = Counter()
        eventos_2fa = defaultdict(Counter)

        for linha in linhas:
            correspondencia = PADRAO_LINHA.match(linha)
            if not correspondencia:
                continue

            logger = correspondencia.group('logger')
            mensagem = correspondencia.group('mensagem')

            usuario_encontrado = PADRAO_USERNAME.search(mensagem)
            username = usuario_encontrado.group(
                'username') if usuario_encontrado else 'desconhecido'

            if logger == 'seguranca.autenticacao':
                if 'tentativa de login com falha' in mensagem:
                    falhas_por_usuario[username] += 1
                elif 'bloqueio por forca bruta' in mensagem:
                    bloqueios_por_usuario[username] += 1

            elif logger == 'seguranca.dois_fatores':
                if 'codigo 2FA correto' in mensagem:
                    eventos_2fa[username]['codigo_correto'] += 1
                elif 'codigo 2FA incorreto' in mensagem:
                    eventos_2fa[username]['codigo_incorreto'] += 1
                elif '2FA ativado' in mensagem:
                    eventos_2fa[username]['ativacoes'] += 1

        self._exibir_resumo(falhas_por_usuario,
                            bloqueios_por_usuario, eventos_2fa)

    def _exibir_resumo(self, falhas_por_usuario, bloqueios_por_usuario, eventos_2fa):
        self.stdout.write(self.style.SUCCESS(
            '=== Tentativas de login com falha, por usuário ==='))
        if falhas_por_usuario:
            for username, total in falhas_por_usuario.most_common():
                self.stdout.write(f'  {username}: {total} tentativa(s)')
        else:
            self.stdout.write('  Nenhuma falha registrada.')

        self.stdout.write(self.style.SUCCESS(
            '\n=== Bloqueios por força bruta ==='))
        if bloqueios_por_usuario:
            for username, total in bloqueios_por_usuario.most_common():
                self.stdout.write(f'  {username}: {total} bloqueio(s)')
        else:
            self.stdout.write('  Nenhum bloqueio registrado.')

        self.stdout.write(self.style.SUCCESS(
            '\n=== Eventos de 2FA, por usuário ==='))
        if eventos_2fa:
            for username, contadores in eventos_2fa.items():
                self.stdout.write(
                    f'  {username}: {contadores["ativacoes"]} ativação(ões), '
                    f'{contadores["codigo_correto"]} código(s) correto(s), '
                    f'{contadores["codigo_incorreto"]} código(s) incorreto(s)'
                )
        else:
            self.stdout.write('  Nenhum evento de 2FA registrado.')
