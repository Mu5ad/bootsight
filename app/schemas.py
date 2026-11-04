"""Contratos de datos de BootSight. Todo lo que devuelve el modelo se valida aquí."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class BootPhase(str, Enum):
    POWER = "power"
    POST = "post"
    BOOTLOADER = "bootloader"
    KERNEL = "kernel"
    DRIVER = "driver"
    OS_INIT = "os_init"
    DESKTOP = "desktop"
    UNKNOWN = "unknown"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Evidence(BaseModel):
    """Un dato literal que el modelo ha leído en la pantalla."""

    text: str = Field(..., min_length=1, max_length=300)
    meaning: str = Field(..., min_length=1, max_length=400)
    where: str = Field("", max_length=120, description="Zona de la imagen donde aparece")


class Diagnosis(BaseModel):
    machine_state: str = Field(..., max_length=200, description="Qué está pasando, en una frase")
    boot_phase: BootPhase = BootPhase.UNKNOWN
    confidence: Confidence = Confidence.LOW
    evidence: list[Evidence] = Field(default_factory=list, max_length=8)
    likely_causes: list[str] = Field(default_factory=list, max_length=5)
    cannot_see: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Qué información falta en la foto y cambiaría el diagnóstico",
    )
    escalate: bool = Field(False, description="True si hace falta criterio humano antes de tocar nada")

    @field_validator("evidence")
    @classmethod
    def _evidence_no_vacia(cls, v: list[Evidence]) -> list[Evidence]:
        return v or []


class Command(BaseModel):
    """Un comando propuesto. `read_only` es una promesa, no una sugerencia."""

    shell: Literal["cmd", "powershell", "bash", "firmware"] = "cmd"
    command: str = Field(..., min_length=1, max_length=400)
    read_only: bool = True
    expected_output: str = Field("", max_length=300)
    if_not_this: str = Field("", max_length=300, description="Qué significa si la salida no es la esperada")


class RepairStep(BaseModel):
    order: int = Field(..., ge=1, le=20)
    title: str = Field(..., max_length=120)
    rationale: str = Field(..., max_length=500)
    command: Command | None = None
    destructive: bool = False


class RepairPlan(BaseModel):
    summary: str = Field(..., max_length=400)
    steps: list[RepairStep] = Field(default_factory=list, max_length=12)
    stop_if: list[str] = Field(default_factory=list, max_length=6)


class Segmentation(BaseModel):
    label: str = ""
    box: list[float] = Field(default_factory=list, description="[x0, y0, x1, y1] normalizado 0-1")
    mask_url: str = ""


class DiagnosisRequest(BaseModel):
    image_b64: str = Field(..., min_length=32)
    notes: str = Field("", max_length=2000, description="Lo que el técnico ha visto u oído")
    locale: str = "es"


class DiagnosisResponse(BaseModel):
    diagnosis: Diagnosis
    plan: RepairPlan
    segmentation: Segmentation | None = None
    model: str
    elapsed_ms: int
    mock: bool = False
