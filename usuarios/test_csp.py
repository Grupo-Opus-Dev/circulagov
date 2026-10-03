import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

Usuario = get_user_model()

RAIZ = Path(settings.BASE_DIR)


def _tokens_de_classe():
    """Classes usadas nos templates e nas strings CLASSE_* do Python."""
    tokens = set()
    for caminho in (RAIZ / 'templates').rglob('*.html'):
        texto = caminho.read_text(encoding='utf-8')
        for achado in re.finditer(r'class="([^"]*)"', texto):
            valor = re.sub(r'\{%.*?%\}|\{\{.*?\}\}', ' ', achado.group(1))
            tokens.update(valor.split())
    for caminho in RAIZ.rglob('*.py'):
        partes = caminho.relative_to(RAIZ).parts
        if partes[0] in ('venv', 'staticfiles') or 'migrations' in partes:
            continue
        if caminho.name.startswith('test'):
            continue
        texto = caminho.read_text(encoding='utf-8')
        padrao = r"(?:CLASSE_[A-Z_]+|attrs\['class'\])\s*=\s*\(?\s*((?:'[^']*'\s*)+)"
        for achado in re.finditer(padrao, texto):
            for pedaco in re.findall(r"'([^']*)'", achado.group(1)):
                tokens.update(pedaco.split())
    return tokens


def _seletor(token):
    """Como o Tailwind escreve a classe no CSS: com barra antes dos
    caracteres que o CSS nao aceita soltos."""
    return '.' + re.sub(r'([^A-Za-z0-9_-])', lambda m: '\\' + m.group(1), token)


class TesteCssDoTailwindVersionado(TestCase):
    maxDiff = None
    """O CSS do Tailwind e gerado uma vez e fica em static/css/tailwind.css.
    Sem estes testes, uma classe nova num template ficaria sem estilo e
    ninguem perceberia."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = (RAIZ / 'static' / 'css' / 'tailwind.css').read_text(
            encoding='utf-8')

    def test_toda_classe_usada_nos_templates_existe_no_css(self):
        faltando = sorted(
            token for token in _tokens_de_classe()
            if _seletor(token) not in self.css)
        self.assertEqual(
            faltando, [],
            'Classes sem regra em static/css/tailwind.css. Gere o CSS de novo '
            'com as classes novas (ver docs/DEPLOY.md).')

    def test_o_css_nao_depende_do_cdn(self):
        self.assertNotIn('cdn.tailwindcss.com', self.css)


class TestePoliticaDeConteudo(TestCase):
    """Content-Security-Policy: o navegador so executa script e estilo do
    proprio site. O teste de HTML abaixo garante que nenhuma tela depende
    de codigo escrito dentro da pagina."""

    PADROES_INLINE = [
        (r'<script(?![^>]*\bsrc=)[^>]*>', 'script dentro do HTML'),
        (r'<style\b', 'bloco <style>'),
        (r'\son[a-z]+\s*=', 'manipulador de evento (onclick e semelhantes)'),
        (r'\sstyle\s*=', 'atributo style'),
        (r'javascript:', 'URL javascript:'),
    ]

    def setUp(self):
        senha = 'SenhaDeTeste123'
        self.gestor = Usuario.objects.create_user(
            username='gestor_csp', password=senha, is_staff=True,
            is_superuser=True)
        self.outro = Usuario.objects.create_user(
            username='outro_csp', password=senha)

    def test_toda_resposta_tem_o_cabecalho(self):
        resposta = self.client.get(reverse('login'))
        politica = resposta.headers['Content-Security-Policy']
        self.assertIn("script-src 'self'", politica)
        self.assertIn("frame-ancestors 'none'", politica)
        self.assertIn("object-src 'none'", politica)

    def test_politica_nao_libera_codigo_inline_nem_cdn(self):
        politica = self.client.get(reverse('login')).headers[
            'Content-Security-Policy']
        self.assertNotIn('unsafe-inline', politica)
        self.assertNotIn('unsafe-eval', politica)
        self.assertNotIn('cdn.tailwindcss.com', politica)

    def test_cabecalho_vem_tambem_em_erro_e_redirecionamento(self):
        for rota in ('/rota-que-nao-existe/', reverse('usuarios:gestao_lista')):
            with self.subTest(rota=rota):
                resposta = self.client.get(rota)
                self.assertIn('Content-Security-Policy', resposta.headers)

    def _telas(self):
        return [
            reverse('login'),
            reverse('recuperacao_senha:solicitar'),
            reverse('usuarios:inicio'),
            reverse('usuarios:gestao_lista'),
            reverse('usuarios:gestao_novo'),
            reverse('usuarios:gestao_detalhe', args=[self.outro.id]),
            reverse('usuarios:gestao_editar', args=[self.outro.id]),
            reverse('usuarios:gestao_definir_senha', args=[self.outro.id]),
            reverse('auditoria:eventos'),
            reverse('auditoria:integridade'),
            reverse('dois_fatores:cadastrar'),
            reverse('consentimento:gerenciar'),
            '/admin/',
            '/admin/usuarios/usuario/',
            f'/admin/usuarios/usuario/{self.outro.id}/change/',
            '/admin/usuarios/usuario/add/',
        ]

    def test_nenhuma_tela_depende_de_codigo_dentro_do_html(self):
        self.client.force_login(self.gestor)
        for rota in self._telas():
            resposta = self.client.get(rota)
            self.assertEqual(resposta.status_code, 200, rota)
            html = resposta.content.decode('utf-8')
            for padrao, descricao in self.PADROES_INLINE:
                with self.subTest(rota=rota, problema=descricao):
                    self.assertIsNone(re.search(padrao, html), (
                        f'{descricao} em {rota}: a política de conteúdo '
                        f'bloquearia isso.'))

    def test_nenhum_template_carrega_script_de_terceiro(self):
        for caminho in (RAIZ / 'templates').rglob('*.html'):
            texto = caminho.read_text(encoding='utf-8')
            for url in re.findall(r'<script[^>]*\ssrc="([^"]+)"', texto):
                with self.subTest(template=caminho.name, url=url):
                    self.assertFalse(
                        url.startswith(('http:', 'https:', '//')),
                        'Script externo precisa estar na política e, de '
                        'preferência, em static/.')
