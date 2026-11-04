import base64
import os

os.environ["BOOTSIGHT_MOCK"] = "1"

from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)
IMG = base64.b64encode(b"foto-de-prueba-no-real").decode()


def test_health():
    r = cliente.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["mock"] is True


def test_politica_declara_solo_lectura():
    r = cliente.get("/api/policy")
    p = r.json()
    assert p["escrituras_automaticas"] is False
    assert "format " in p["forbidden"]


def test_diagnostico_completo_mock():
    r = cliente.post("/api/diagnose", json={"image_b64": IMG, "notes": "no bootable device, disco sata", "locale": "es"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["mock"] is True
    assert d["diagnosis"]["boot_phase"] in {"bootloader", "kernel", "post", "unknown"}
    assert d["plan"]["steps"], "el plan no puede venir vacío"
    assert d["plan"]["steps"][0]["order"] == 1


def test_comando_peligroso_se_bloquea():
    r = cliente.post("/api/run", json={"command": "format c: /y", "shell": "cmd", "read_only": True})
    assert r.status_code == 403


def test_composicion_de_comandos_se_bloquea():
    r = cliente.post("/api/run", json={"command": "lsblk && rm -rf /", "shell": "bash", "read_only": True})
    assert r.status_code == 403


def test_comando_lectura_valida():
    r = cliente.post("/api/run", json={"command": "lsblk", "shell": "bash", "read_only": True})
    assert r.status_code == 200
    assert r.json()["executed"] is False
    assert r.json()["argv"][0] == "lsblk"


def test_imagen_vacia_rechazada():
    r = cliente.post("/api/diagnose", json={"image_b64": "x", "notes": ""})
    assert r.status_code == 422
