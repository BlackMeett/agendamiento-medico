from django.conf import settings
from django.db import models


class PerfilUsuario(models.Model):
    class Rol(models.TextChoices):
        ADMIN = "ADMIN", "Administrador del sistema"
        SOME = "SOME", "Personal administrativo SOME"
        ADMISION = "ADMISION", "Admisión y derivación"
        PROFESIONAL = "PROFESIONAL", "Profesional de salud"
        MEDICO = "MEDICO", "Médico especialista"
        PACIENTE = "PACIENTE", "Paciente"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil",
    )
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.ADMISION)
    establecimiento = models.ForeignKey(
        "gestion.Establecimiento",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="usuarios",
        help_text="Alcance de datos. Vacío significa alcance global para administración.",
    )
    telefono = models.CharField(max_length=30, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "perfil de usuario"
        verbose_name_plural = "perfiles de usuario"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} · {self.get_rol_display()}"

    @property
    def es_funcionario(self):
        return self.rol != self.Rol.PACIENTE

    @property
    def es_admin(self):
        return self.rol == self.Rol.ADMIN or self.user.is_superuser

    @property
    def puede_ver_clinico(self):
        return self.rol in {self.Rol.PROFESIONAL, self.Rol.MEDICO} or self.user.is_superuser

    @property
    def puede_aprobar_reagendamiento(self):
        return self.rol in {self.Rol.ADMIN, self.Rol.SOME, self.Rol.ADMISION} or self.user.is_superuser

    @property
    def puede_gestionar_agendas(self):
        return self.rol in {self.Rol.ADMIN, self.Rol.SOME, self.Rol.MEDICO} or self.user.is_superuser

    @property
    def puede_gestionar_pacientes(self):
        return self.rol in {self.Rol.ADMIN, self.Rol.SOME, self.Rol.ADMISION} or self.user.is_superuser
