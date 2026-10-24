from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils import timezone

from core.scoping import alcance_establecimiento, filtrar_pacientes

from .models import (
    Agenda,
    DatosClinicosSolicitud,
    Especialidad,
    Establecimiento,
    Paciente,
    PreferenciaDisponibilidad,
    Profesional,
    Solicitud,
)


def aplicar_estilos(form):
    for nombre, campo in form.fields.items():
        widget = campo.widget
        clase = "campo"
        if isinstance(widget, forms.CheckboxInput):
            clase = "checkbox"
        elif isinstance(widget, forms.Select):
            clase = "campo select"
        elif isinstance(widget, forms.Textarea):
            clase = "campo textarea"
        widget.attrs["class"] = f"{widget.attrs.get('class', '')} {clase}".strip()
        if campo.required:
            widget.attrs["required"] = "required"
    return form


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Correo electrónico",
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Contraseña",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_estilos(self)


class PacienteForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = [
            "tipo_documento",
            "numero_documento",
            "nombres",
            "apellidos",
            "fecha_nacimiento",
            "telefono",
            "email",
            "canal_preferido",
            "consentimiento_notificaciones",
            "establecimiento_referencia",
            "estado_contacto",
        ]
        widgets = {"fecha_nacimiento": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_estilos(self)
        self.fields["numero_documento"].help_text = "Usa un documento ficticio en la demostración."
        self.fields["telefono"].help_text = "Formato de ejemplo: +56 9 0000 0000."
        alcance = alcance_establecimiento(user) if user else None
        if alcance:
            self.fields["establecimiento_referencia"].queryset = Establecimiento.objects.filter(
                pk=alcance.pk
            )
            if not self.instance.pk:
                self.fields["establecimiento_referencia"].initial = alcance.pk

    def clean_numero_documento(self):
        valor = self.cleaned_data["numero_documento"].strip()
        if not valor:
            raise forms.ValidationError("El documento es obligatorio.")
        return valor


class SolicitudForm(forms.ModelForm):
    class Meta:
        model = Solicitud
        fields = [
            "paciente",
            "especialidad",
            "establecimiento_origen",
            "establecimiento_destino",
            "origen",
            "fecha_ingreso",
            "referencia_externa",
            "observaciones",
        ]
        widgets = {
            "fecha_ingreso": forms.DateInput(attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_estilos(self)
        self.fields["fecha_ingreso"].initial = timezone.localdate()
        self.fields["referencia_externa"].help_text = "Opcional. No uses identificadores reales de un sistema externo."
        pacientes = Paciente.objects.filter(activo=True).order_by("apellidos", "nombres")
        if user:
            pacientes = filtrar_pacientes(pacientes, user)
        self.fields["paciente"].queryset = pacientes
        alcance = alcance_establecimiento(user) if user else None
        if alcance:
            self.fields["establecimiento_origen"].queryset = Establecimiento.objects.filter(
                pk=alcance.pk
            )
            self.fields["establecimiento_destino"].queryset = Establecimiento.objects.filter(
                pk=alcance.pk
            )
            self.fields["establecimiento_origen"].initial = alcance.pk
            self.fields["establecimiento_destino"].initial = alcance.pk
        self.fields["establecimiento_destino"].help_text = "Puede quedar vacío si la red lo definirá después."


class SolicitudPacienteForm(forms.ModelForm):
    class Meta:
        model = Solicitud
        fields = ["especialidad", "observaciones"]
        labels = {
            "especialidad": "Especialidad",
            "observaciones": "Motivo o comentario (opcional)",
        }
        widgets = {"observaciones": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_estilos(self)
        self.fields["especialidad"].queryset = Especialidad.objects.filter(activa=True).order_by(
            "nombre"
        )
        self.fields["especialidad"].empty_label = "Selecciona una especialidad"
        self.fields["especialidad"].help_text = (
            "Si no hay horas disponibles, la solicitud quedará en lista de espera."
        )
        self.fields["observaciones"].help_text = (
            "No incluyas diagnósticos ni datos clínicos sensibles."
        )


class DatosClinicosForm(forms.ModelForm):
    class Meta:
        model = DatosClinicosSolicitud
        fields = ["motivo_derivacion", "diagnostico", "notas"]
        widgets = {
            "motivo_derivacion": forms.Textarea(attrs={"rows": 3}),
            "notas": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_estilos(self)
        self.fields["diagnostico"].help_text = "Dato ficticio en la demostración. Acceso restringido."


class AgendaForm(forms.ModelForm):
    class Meta:
        model = Agenda
        fields = [
            "profesional",
            "establecimiento",
            "especialidad",
            "fecha_inicio",
            "fecha_fin",
            "duracion_min",
        ]
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_estilos(self)
        profesionales = Profesional.objects.filter(activo=True).select_related(
            "especialidad", "establecimiento"
        )
        alcance = alcance_establecimiento(user) if user else None
        if alcance:
            profesionales = profesionales.filter(establecimiento=alcance)
            self.fields["establecimiento"].queryset = Establecimiento.objects.filter(pk=alcance.pk)
            self.fields["establecimiento"].initial = alcance.pk
        self.fields["profesional"].queryset = profesionales
        self.fields["duracion_min"].initial = 30

    def clean(self):
        datos = super().clean()
        inicio = datos.get("fecha_inicio")
        fin = datos.get("fecha_fin")
        if inicio and fin and inicio > fin:
            raise forms.ValidationError("La fecha de inicio no puede ser posterior a la fecha de término.")
        profesional = datos.get("profesional")
        especialidad = datos.get("especialidad")
        establecimiento = datos.get("establecimiento")
        if profesional and especialidad and profesional.especialidad_id != especialidad.id:
            raise forms.ValidationError("La especialidad de la agenda no coincide con la del profesional.")
        if profesional and establecimiento and profesional.establecimiento_id != establecimiento.id:
            raise forms.ValidationError("El establecimiento de la agenda no coincide con el del profesional.")
        return datos


class GenerarHorasForm(forms.Form):
    DIAS = [
        (0, "Lunes"),
        (1, "Martes"),
        (2, "Miércoles"),
        (3, "Jueves"),
        (4, "Viernes"),
        (5, "Sábado"),
    ]
    dias_semana = forms.MultipleChoiceField(
        choices=DIAS,
        widget=forms.CheckboxSelectMultiple,
        label="Días de atención",
        initial=[0, 1, 2, 3, 4],
    )
    hora_inicio = forms.TimeField(
        label="Hora de inicio",
        widget=forms.TimeInput(attrs={"type": "time"}),
        initial="08:00",
    )
    hora_fin = forms.TimeField(
        label="Hora de término",
        widget=forms.TimeInput(attrs={"type": "time"}),
        initial="12:00",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_estilos(self)

    def clean(self):
        datos = super().clean()
        inicio = datos.get("hora_inicio")
        fin = datos.get("hora_fin")
        if inicio and fin and inicio >= fin:
            raise forms.ValidationError("La hora de inicio debe ser anterior a la hora de término.")
        if not datos.get("dias_semana"):
            raise forms.ValidationError("Selecciona al menos un día.")
        return datos


class PreferenciaForm(forms.ModelForm):
    class Meta:
        model = PreferenciaDisponibilidad
        fields = ["dia_semana", "hora_desde", "hora_hasta", "es_restriccion"]
        widgets = {
            "hora_desde": forms.TimeInput(attrs={"type": "time"}),
            "hora_hasta": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_estilos(self)


class MotivoForm(forms.Form):
    motivo = forms.CharField(
        label="Motivo",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Explica brevemente la decisión."}),
        required=True,
        max_length=500,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_estilos(self)


class PacientePerfilForm(forms.ModelForm):
    class Meta:
        model = Paciente
        fields = ["telefono", "email", "canal_preferido", "consentimiento_notificaciones"]
        widgets = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_estilos(self)
