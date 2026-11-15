"""Passa o RA a ser guardado cifrado (requisito 3.4).

Cria os campos novos, cifra o RA de quem já existe e só então remove a
coluna antiga. A volta também funciona: decifra para a coluna de texto.
"""
from django.db import migrations, models

from alunos import protecao


def cifrar_existentes(apps, schema_editor):
    Aluno = apps.get_model('alunos', 'Aluno')
    for aluno in Aluno.objects.all():
        aluno.ra_cifrado = protecao.cifrar(aluno.ra)
        aluno.ra_indice = protecao.indice(aluno.ra)
        aluno.save(update_fields=['ra_cifrado', 'ra_indice'])


def decifrar_existentes(apps, schema_editor):
    Aluno = apps.get_model('alunos', 'Aluno')
    for aluno in Aluno.objects.all():
        aluno.ra = protecao.decifrar(aluno.ra_cifrado)
        aluno.save(update_fields=['ra'])


class Migration(migrations.Migration):

    dependencies = [
        ('alunos', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='aluno',
            name='ra_cifrado',
            field=models.BinaryField(null=True, verbose_name='RA cifrado'),
        ),
        migrations.AddField(
            model_name='aluno',
            name='ra_indice',
            field=models.CharField(
                editable=False, max_length=64, null=True,
                verbose_name='índice do RA'),
        ),
        migrations.AlterField(
            model_name='aluno',
            name='ra',
            field=models.CharField(
                max_length=20, null=True, unique=True, verbose_name='RA'),
        ),
        migrations.RunPython(cifrar_existentes, decifrar_existentes),
        migrations.RemoveField(
            model_name='aluno',
            name='ra',
        ),
        migrations.AlterField(
            model_name='aluno',
            name='ra_cifrado',
            field=models.BinaryField(verbose_name='RA cifrado'),
        ),
        migrations.AlterField(
            model_name='aluno',
            name='ra_indice',
            field=models.CharField(
                editable=False, max_length=64, unique=True,
                verbose_name='índice do RA'),
        ),
    ]
