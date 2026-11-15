"""Rotação da chave do log (requisito 5.3): arquivar_log e a verificação
de um log arquivado com a chave antiga."""
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from .tests import CHAVE_TESTE, OUTRA_CHAVE, gravar_eventos


class RotacaoDaChaveDoLogTests(SimpleTestCase):

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.dir = Path(self.pasta.name)
        self.log = self.dir / 'seguranca.log'
        self.override = override_settings(
            LOG_DIR=self.dir, CHAVE_INTEGRIDADE_LOGS=CHAVE_TESTE)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        self.pasta.cleanup()

    def _arquivar(self, carimbo='20261115-120000'):
        call_command('arquivar_log', '--carimbo', carimbo, stdout=StringIO())
        return (self.dir / f'seguranca-{carimbo}.log',
                self.dir / f'ancoras-{carimbo}.log')

    def _chave_em_arquivo(self, chave):
        caminho = self.dir / 'chave.txt'
        caminho.write_text(chave + '\n', encoding='utf-8')
        return caminho

    def test_arquiva_log_e_ancoras_com_ancora_de_fechamento(self):
        gravar_eventos(self.log, ['um', 'dois', 'tres'])

        log_antigo, ancoras_antigas = self._arquivar()

        self.assertFalse(self.log.exists())
        self.assertTrue(log_antigo.exists())
        texto = ancoras_antigas.read_text(encoding='utf-8')
        self.assertIn('linhas=3', texto)

    def test_log_arquivado_continua_verificavel_com_a_chave_antiga(self):
        gravar_eventos(self.log, ['um', 'dois'])
        log_antigo, ancoras_antigas = self._arquivar()
        chave = self._chave_em_arquivo(CHAVE_TESTE)

        # Depois da rotação, a aplicação usa outra chave.
        with override_settings(CHAVE_INTEGRIDADE_LOGS=OUTRA_CHAVE):
            gravar_eventos(self.log, ['novo'], chave=OUTRA_CHAVE)
            saida = StringIO()
            call_command(
                'verificar_logs', '--arquivo', str(log_antigo),
                '--ancoras', str(ancoras_antigas),
                '--chave-arquivo', str(chave), stdout=saida)
            self.assertIn('2 linhas verificadas', saida.getvalue())
            self.assertIn('1 âncora(s) conferida(s)', saida.getvalue())

            # E o log novo é verificado com a chave nova, sem misturar.
            saida = StringIO()
            call_command('verificar_logs', stdout=saida)
            self.assertIn('1 linhas verificadas', saida.getvalue())

    def test_chave_pela_entrada_padrao(self):
        gravar_eventos(self.log, ['um'])
        log_antigo, _ = self._arquivar()

        with override_settings(CHAVE_INTEGRIDADE_LOGS=OUTRA_CHAVE), \
                mock.patch('sys.stdin', StringIO(CHAVE_TESTE + '\n')):
            saida = StringIO()
            call_command(
                'verificar_logs', '--arquivo', str(log_antigo),
                '--chave-arquivo', '-', stdout=saida)
        self.assertIn('1 linhas verificadas', saida.getvalue())

    def test_log_arquivado_com_a_chave_errada_reprova(self):
        gravar_eventos(self.log, ['um'])
        log_antigo, _ = self._arquivar()
        chave = self._chave_em_arquivo(OUTRA_CHAVE)

        with self.assertRaises(CommandError):
            call_command(
                'verificar_logs', '--arquivo', str(log_antigo),
                '--chave-arquivo', str(chave), stdout=StringIO())

    def test_corte_do_final_do_log_arquivado_e_detectado(self):
        gravar_eventos(self.log, ['um', 'dois', 'tres'])
        log_antigo, ancoras_antigas = self._arquivar()
        linhas = log_antigo.read_text(encoding='utf-8').splitlines(True)
        log_antigo.write_text(''.join(linhas[:2]), encoding='utf-8')
        chave = self._chave_em_arquivo(CHAVE_TESTE)

        with self.assertRaises(CommandError):
            call_command(
                'verificar_logs', '--arquivo', str(log_antigo),
                '--ancoras', str(ancoras_antigas),
                '--chave-arquivo', str(chave), stdout=StringIO())

    def test_nao_arquiva_log_adulterado(self):
        gravar_eventos(self.log, ['um', 'dois'])
        texto = self.log.read_text(encoding='utf-8')
        self.log.write_text(texto.replace('um', 'UM'), encoding='utf-8')

        with self.assertRaises(CommandError):
            self._arquivar()
        self.assertTrue(self.log.exists())

    def test_nao_sobrescreve_arquivo_com_o_mesmo_carimbo(self):
        gravar_eventos(self.log, ['um'])
        self._arquivar()
        gravar_eventos(self.log, ['dois'])

        with self.assertRaises(CommandError):
            self._arquivar()

    def test_chave_invalida_e_recusada(self):
        gravar_eventos(self.log, ['um'])
        chave = self._chave_em_arquivo('curta')

        with self.assertRaises(CommandError):
            call_command(
                'verificar_logs', '--arquivo', str(self.log),
                '--chave-arquivo', str(chave), stdout=StringIO())
