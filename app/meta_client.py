"""Cliente de Meta Model API (OpenAI-compatible) con modo mock determinista.

El modo mock no llama a la red: devuelve un diagnóstico plausible construido a partir de
las notas del técnico. Sirve para que el flujo completo sea demostrable sin clave y para
que los tests corran en CI.
"""

from __future__ import annotations

import base64
import json
import os
import time

MODELO = os.environ.get("BOOTSIGHT_MODEL", "muse-spark-1.3")
BASE_URL = os.environ.get("BOOTSIGHT_BASE_URL", "https://api.meta.ai/v1")
MOCK = os.environ.get("BOOTSIGHT_MOCK", "0") == "1"

SISTEMA = """Eres BootSight, copiloto de un técnico de campo frente a un PC que no arranca.
Recibes una foto de la pantalla y notas del técnico.

Reglas duras:
- Solo describes lo que se ve. Si un dato no está en la imagen, va en `cannot_see`.
- No inventes códigos de error ni marcas.
- Antes de proponer pasos destructivos, agota el diagnóstico de lectura.
- Cada comando debe empezar por uno de estos prefijos de solo lectura:
""" + ", ".join([
    "systeminfo", "wmic diskdrive get", "chkdsk /scan", "sfc /verifyonly",
    "bootrec /scanos", "smartctl -a", "lspci", "lsblk", "dmesg", "journalctl -b", "fsck -n", "nvme smart-log",
]) + """
- Si no puedes leer la pantalla con seguridad, dilo: confidence=low y escalate=true.
Devuelve el JSON del esquema, sin texto adicional."""


def disponible() -> bool:
    return bool(os.environ.get("MODEL_API_KEY"))


def _mock(notes: str, locale: str) -> dict:
    nota = (notes or "").lower()
    if "disk" in nota or "disco" in nota or "sata" in nota:
        fase, causa = "bootloader", "disco no detectado o cable SATA suelto"
        evidencia = "No bootable device"
    elif "blue" in nota or "azul" in nota or "bsod" in nota:
        fase, causa = "kernel", "fallo de controlador tras una actualización"
        evidencia = "STOP: 0x0000007B INACCESSIBLE_BOOT_DEVICE"
    elif "panic" in nota or "kernel" in nota:
        fase, causa = "kernel", "panic por módulo de almacenamiento"
        evidencia = "Kernel panic - not syncing: VFS: Unable to mount root fs"
    else:
        fase, causa = "post", "fallo de POST no identificado"
        evidencia = "No se ha podido leer un código de error legible"

    return {
        "diagnosis": {
            "machine_state": f"Equipo detenido en fase {fase} por {causa}",
            "boot_phase": fase,
            "confidence": "low" if fase == "post" else "medium",
            "evidence": [{"text": evidencia, "meaning": causa, "where": "centro de la pantalla"}],
            "likely_causes": [causa],
            "cannot_see": ["estado del LED de la placa", "ruido del disco"],
            "escalate": fase == "post",
        },
        "plan": {
            "summary": "Confirmar el estado del almacenamiento antes de tocar el arranque.",
            "steps": [
                {
                    "order": 1,
                    "title": "Ver si la BIOS enumera el disco",
                    "rationale": "Si el disco no aparece aquí, el problema es físico o de cable, no de software.",
                    "command": {
                        "shell": "bash",
                        "command": "lsblk",
                        "read_only": True,
                        "expected_output": "una entrada con el disco y sus particiones",
                        "if_not_this": "sin disco listado: revisar cable y alimentación antes de seguir",
                    },
                    "destructive": False,
                },
                {
                    "order": 2,
                    "title": "Leer el estado SMART",
                    "rationale": "Descarta un disco moribundo antes de invertir tiempo en el arranque.",
                    "command": {
                        "shell": "bash",
                        "command": "smartctl -a",
                        "read_only": True,
                        "expected_output": "PASSED en overall-health",
                        "if_not_this": "FAILED: clonar antes de cualquier otra cosa",
                    },
                    "destructive": False,
                },
            ],
            "stop_if": ["el disco no aparece en la BIOS", "SMART devuelve FAILED"],
        },
    }


def _parse_json(texto: str) -> dict:
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.split("```")[1]
        if texto.startswith("json"):
            texto = texto[4:]
    return json.loads(texto)


def diagnostica(image_b64: str, notes: str, locale: str = "es") -> tuple[dict, dict, bool]:
    """Devuelve (diagnostico, plan, mock_usado)."""
    if MOCK or not disponible():
        return _mock(notes, locale)["diagnosis"], _mock(notes, locale)["plan"], True

    from openai import OpenAI  # import perezoso: el modo mock no necesita el SDK

    client = OpenAI(api_key=os.environ["MODEL_API_KEY"], base_url=BASE_URL)
    usuario = [
        {"type": "input_text", "text": f"Notas del técnico: {notes or '(sin notas)'}\nIdioma de salida: {locale}"},
        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_b64}"},
    ]
    r = client.responses.create(
        model=MODELO,
        reasoning={"effort": "medium"},
        input=[{"role": "system", "content": SISTEMA}, {"role": "user", "content": usuario}],
        text={"format": {"type": "json_object"}},
    )
    datos = _parse_json(r.output_text)
    return datos["diagnosis"], datos["plan"], False


def segmenta(image_b64: str, label: str) -> dict | None:
    """Pide a SAM 3.1 la caja del elemento que lleva el error. Opcional: si falla, no rompe el flujo."""
    if MOCK or not disponible() or not label:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.environ["MODEL_API_KEY"], base_url=BASE_URL)
        r = client.responses.create(
            model="sam-3.1",
            input=[{"role": "user", "content": [
                {"type": "input_text", "text": label[:80]},
                {"type": "input_image", "image_url": f"data:image/jpeg;base64,{image_b64}"},
            ]}],
        )
        return {"label": label, "raw": (r.output_text or "")[:4000]}
    except Exception:
        return None
