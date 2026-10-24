from django import template

register = template.Library()

LABELS = {
    "INGRESADA": "Ingresada",
    "PENDIENTE_REVISION": "Pendiente de revisión",
    "VALIDADA": "Validada",
    "EN_LISTA_ESPERA": "En lista de espera",
    "OFERTA_PENDIENTE": "Oferta pendiente",
    "AGENDADA": "Agendada",
    "ATENDIDA": "Atendida",
    "RECHAZADA": "Rechazada",
    "CANCELADA": "Cancelada",
    "CERRADA": "Cerrada",
    "PENDIENTE": "Pendiente",
    "ACEPTADA": "Aceptada",
    "VENCIDA": "Vencida",
    "CONFIRMADA": "Confirmada",
    "NO_ASISTIO": "No asistió",
    "CANCELADA_PACIENTE": "Cancelada por paciente",
    "CANCELADA_ESTABLECIMIENTO": "Cancelada por establecimiento",
    "REAGENDAMIENTO_PENDIENTE": "Reagendamiento pendiente",
    "REAGENDADA": "Reagendada",
    "APROBADA": "Aprobada",
    "FALLIDA": "Fallida",
    "BORRADOR": "Borrador",
    "PUBLICADA": "Publicada",
    "SUSPENDIDA": "Suspendida",
    "ABIERTA": "Abierta",
    "EN_REVISION": "En revisión",
    "SIMULADO": "Simulado",
    "ENVIADO": "Enviado",
    "FALLIDO": "Fallido",
    "DESCARTADO": "Descartado",
    "LEIDO": "Leído",
    "COMPLETADO": "Completado",
    "PROCESANDO": "Procesando",
}

BADGES = {
    # Solicitud
    "INGRESADA": "badge--gray",
    "PENDIENTE_REVISION": "badge--amber",
    "VALIDADA": "badge--teal",
    "EN_LISTA_ESPERA": "badge--blue",
    "OFERTA_PENDIENTE": "badge--amber",
    "AGENDADA": "badge--green",
    "ATENDIDA": "badge--green",
    "RECHAZADA": "badge--red",
    "CANCELADA": "badge--red",
    "CERRADA": "badge--gray",
    # Oferta
    "PENDIENTE": "badge--amber",
    "ACEPTADA": "badge--green",
    "VENCIDA": "badge--red",
    # Cita
    "CONFIRMADA": "badge--green",
    "NO_ASISTIO": "badge--red",
    "CANCELADA_PACIENTE": "badge--gray",
    "CANCELADA_ESTABLECIMIENTO": "badge--red",
    "REAGENDAMIENTO_PENDIENTE": "badge--amber",
    "REAGENDADA": "badge--blue",
    # Propuesta
    "APROBADA": "badge--green",
    "FALLIDA": "badge--red",
    # Agenda
    "BORRADOR": "badge--gray",
    "PUBLICADA": "badge--green",
    "SUSPENDIDA": "badge--red",
    # Alerta / mensaje / evento
    "ABIERTA": "badge--amber",
    "EN_REVISION": "badge--blue",
    "SIMULADO": "badge--teal",
    "ENVIADO": "badge--green",
    "FALLIDO": "badge--red",
    "DESCARTADO": "badge--gray",
    "LEIDO": "badge--green",
    "COMPLETADO": "badge--green",
    "PROCESANDO": "badge--blue",
}


@register.filter
def badge_class(estado):
    return BADGES.get(str(estado), "badge--gray")


@register.filter
def estado_label(estado):
    return LABELS.get(str(estado), str(estado))


@register.filter
def add_class(field, clase):
    existente = field.field.widget.attrs.get("class", "")
    field.field.widget.attrs["class"] = f"{existente} {clase}".strip()
    return field


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    request = context.get("request")
    if request is None:
        return ""
    datos = request.GET.copy()
    for clave, valor in kwargs.items():
        if valor is None or valor == "":
            datos.pop(clave, None)
        else:
            datos[clave] = valor
    return datos.urlencode()
