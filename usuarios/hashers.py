from django.contrib.auth.hashers import Argon2PasswordHasher


class Argon2PasswordHasherCirculaGov(Argon2PasswordHasher):
    """
    Parâmetros de custo do Argon2id usados no CirculaGov.

    Valores alinhados à recomendação mínima do OWASP Password Storage
    Cheat Sheet (2024) para Argon2id: memory_cost=19 MiB, time_cost=2,
    parallelism=1.

    Justificativa: Argon2 é resistente a ataques com GPU/hardware
    especializado por exigir memória (não só tempo de CPU) para calcular
    o hash — por isso memory_cost é o parâmetro mais importante contra
    força bruta. Os valores da OWASP equilibram essa resistência com um
    tempo de resposta de login aceitável (poucas centenas de ms), o que
    importa aqui porque o sistema roda em notebooks comuns durante o
    desenvolvimento e a apresentação, não em servidor dedicado.
    """

    time_cost = 2
    memory_cost = 19 * 1024  # 19 MiB, em KiB
    parallelism = 1
