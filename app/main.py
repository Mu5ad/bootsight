"""BootSight — servidor. Sirve la API y el frontend en el mismo proceso."""

from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import meta_client, safety
from .schemas import DiagnosisRequest, DiagnosisResponse, RepairPlan, RepairStep, Diagnosis

RAIZ = Path(__file__).resolve().parent.parent
WEB = RAIZ / "web"

app = FastAPI(title="BootSight", version="0.1.0")
app.mount("/static", StaticFiles(directory=WEB), name="static")
if (RAIZ / "samples").is_dir():
    app.mount("/samples", StaticFiles(directory=RAIZ / "samples"), name="samples")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "model": meta_client.MODELO,
        "mock": meta_client.MOCK or not meta_client.disponible(),
        "base_url": meta_client.BASE_URL,
    }


@app.get("/api/policy")
def policy():
    return safety.resumen_politica()


@app.post("/api/diagnose", response_model=DiagnosisResponse)
def diagnose(peticion: DiagnosisRequest):
    inicio = time.time()
    try:
        diag_raw, plan_raw, mock = meta_client.diagnostica(peticion.image_b64, peticion.notes, peticion.locale)
    except Exception as e:  # el modelo nunca debe tumbar el servicio
        raise HTTPException(status_code=502, detail=f"fallo del modelo: {e}") from e

    try:
        diag = Diagnosis.model_validate(diag_raw)
        plan = RepairPlan.model_validate(plan_raw)
    except ValidationError as e:
        raise HTTPException(status_code=502, detail=f"respuesta fuera de esquema: {e.errors()[:3]}") from e

    plan = _sanea_plan(plan)
    evidencia = diag.evidence[0].text if diag.evidence else ""
    seg = meta_client.segmenta(peticion.image_b64, evidencia)

    return DiagnosisResponse(
        diagnosis=diag,
        plan=plan,
        segmentation={"label": seg["label"], "raw": seg["raw"]} if seg else None,
        model=meta_client.MODELO,
        elapsed_ms=int((time.time() - inicio) * 1000),
        mock=mock,
    )


def _sanea_plan(plan: RepairPlan) -> RepairPlan:
    """Marca como destructivos los pasos cuya shell o comando no pasan la política."""
    limpio: list[RepairStep] = []
    for paso in plan.steps:
        if paso.command is None:
            limpio.append(paso)
            continue
        try:
            safety.valida(paso.command.command, paso.command.shell, paso.command.read_only)
            limpio.append(paso)
        except safety.UnsafeCommand:
            limpio.append(paso.model_copy(update={"destructive": True, "command": paso.command.model_copy(update={"read_only": False})}))
    return plan.model_copy(update={"steps": limpio})


@app.post("/api/run")
def run(body: dict):
    """Ejecuta un comando SOLO si pasa la allowlist. En esta versión, simulacro si no hay ejecutor local."""
    command = (body.get("command") or "").strip()
    shell = body.get("shell") or "bash"
    read_only = bool(body.get("read_only", True))
    try:
        safety.valida(command, shell, read_only)
    except safety.UnsafeCommand as e:
        raise HTTPException(status_code=403, detail=str(e)) from e

    if os.environ.get("BOOTSIGHT_EXEC", "0") != "1":
        return {
            "executed": False,
            "reason": "ejecución local desactivada (BOOTSIGHT_EXEC=0). Comando validado y listo.",
            "argv": safety.argv(command, shell),
        }

    import subprocess

    try:
        p = subprocess.run(safety.argv(command, shell), capture_output=True, text=True, timeout=60)
        return {"executed": True, "rc": p.returncode, "stdout": p.stdout[-8000:], "stderr": p.stderr[-2000:]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
