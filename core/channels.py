from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResultadoEnvio:
    estado: str
    proveedor_id: str = ""
