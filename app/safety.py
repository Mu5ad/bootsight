"""Frontera de seguridad de BootSight.

El modelo propone comandos; este módulo decide cuáles se pueden ejecutar sin supervisión.
Regla: por defecto, solo lectura. Cualquier escritura se bloquea salvo que el operador
la marque explícitamente en la interfaz y la política lo permita.
"""

from __future__ import annotations

import re
import shlex

# Prefijos permitidos en modo diagnóstico (solo lectura).
READ_ONLY_PREFIXES: tuple[str, ...] = (
    "systeminfo",
    "wmic diskdrive get",
    "wmic logicaldisk get",
    "wmic memorychip get",
    "chkdsk /scan",
    "sfc /verifyonly",
    "dism /online /cleanup-image /checkhealth",
    "bootrec /scanos",
    "diskpart /s",
    "smartctl -a",
    "smartctl -x",
    "lspci",
    "lsblk",
    "blkid",
    "df -h",
    "dmesg",
    "journalctl -b",
    "fsck -n",
    "cat /proc/",
    "cat /sys/",
    "nvme list",
    "nvme smart-log",
    "dmidecode",
    "memtest",
    "dir ",
    "ls ",
)

# Cadenas que nunca se ejecutan, ni con confirmación: destruyen datos.
FORBIDDEN = (
    "format ",
    "diskpart clean",
    "clean all",
    "rm -rf /",
    "mkfs",
    "dd if=",
    "bcdedit /delete",
    "bootrec /fixmbr",  # reescribe el MBR: nunca automático
    "bootsect",
    "shutdown",
    "cipher /w",
    "chkdsk /f",
    "chkdsk /r",
)

SHELLS = {"cmd", "powershell", "bash", "firmware"}


class UnsafeCommand(ValueError):
    pass


def normaliza(command: str) -> str:
    return re.sub(r"\s+", " ", command.strip().lower())


def es_lectura(command: str) -> bool:
    """True solo si el comando empieza por un prefijo de la allowlist y no cae en FORBIDDEN."""
    c = normaliza(command)
    if any(f in c for f in FORBIDDEN):
        return False
    return any(c.startswith(p) for p in READ_ONLY_PREFIXES)


def valida(command: str, shell: str, declarado_read_only: bool) -> None:
    """Lanza UnsafeCommand si el comando no se puede ejecutar tal cual se ha propuesto."""
    if shell not in SHELLS:
        raise UnsafeCommand(f"shell no soportado: {shell}")
    if "&&" in command or ";" in command or "|" in command or "$(" in command or "`" in command:
        raise UnsafeCommand("composición de comandos no permitida")
    if not declarado_read_only:
        raise UnsafeCommand("el modelo ha marcado el comando como no read-only")
    if not es_lectura(command):
        raise UnsafeCommand(f"comando fuera de la allowlist: {command[:80]}")


def argv(command: str, shell: str) -> list[str]:
    """Convierte el comando validado en argv. No usa shell=True nunca."""
    if shell in ("cmd", "powershell"):
        return ["cmd", "/c", command] if shell == "cmd" else ["powershell", "-NoProfile", "-Command", command]
    return shlex.split(command)


def resumen_politica() -> dict:
    return {
        "read_only_prefixes": list(READ_ONLY_PREFIXES),
        "forbidden": list(FORBIDDEN),
        "composicion": False,
        "escrituras_automaticas": False,
    }
