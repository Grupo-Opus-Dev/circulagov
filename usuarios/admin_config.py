from django.contrib.admin.apps import AdminConfig


class AdminCirculaGovConfig(AdminConfig):
    """Troca o site de administração padrão por um que usa o login da
    aplicação. É o jeito documentado do Django de substituir o admin.site,
    e mantém o nome e o rótulo do app de admin, então nada muda no banco.

    Fica num módulo próprio, e não em apps.py, porque o Django recusa um
    apps.py com mais de uma classe de configuração.
    """
    default_site = 'usuarios.admin_site.AdminSiteCirculaGov'
