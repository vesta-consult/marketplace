"""Tests des A2A-Clients 1.1.0 (synthetische Daten, kein Netz)."""
from __future__ import annotations

import json
import pathlib
import sys

import httpx
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import vesta_foerder_client as c  # noqa: E402

EMPF = {
    "profil": {"zielgruppe": "privatperson", "bundesland": "by"},
    "eligible": [{"id": "test-a", "name": "Testprogramm A"}],
    "kumulierung": [],
    "anzahl": {"eligible": 1, "geprueft": 3},
    "ausgeschlossen": [],
    "discovery_hinweise": [],
    "haftungsausschluss": {"version": "test", "text": "Testhaftung."},
}
HTML = "<!doctype html><title>Förder-Check</title><p>Dashboard</p>"


def _antwort() -> dict:
    return {
        "task": {
            "status": {"state": "TASK_STATE_COMPLETED",
                       "message": {"parts": [{"text": "Förder-Check abgeschlossen."}]}},
            "artifacts": [{"parts": [{"data": EMPF}, {"text": HTML}]}],
        }
    }


def _args(*extra: str):
    return c.build_parser().parse_args(["empfehlung", "--zielgruppe", "privatperson", *extra])


@pytest.fixture
def umgebung(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("VESTA_CUSTOMER_TOKEN", "vesta-frame-test")
    monkeypatch.setenv("VESTA_A2A_URL", "https://a2a.test/customer")
    return tmp_path


def test_baue_profil_zahlen():
    p = c.baue_profil(_args("--investitionssumme", "150000", "--anzahl-we", "6",
                            "--gegenstand", "sanierung, heizung", "--bundesland", "by"))
    assert p["investitionssumme_eur"] == 150000.0
    assert p["anzahl_we"] == 6
    assert p["gegenstand"] == ["sanierung", "heizung"]


def test_baue_profil_ohne_zahlen_ohne_felder():
    p = c.baue_profil(_args())
    assert "investitionssumme_eur" not in p and "anzahl_we" not in p


def test_projekt_neu_und_wieder(tmp_path):
    a = c.lade_oder_lege_projekt(tmp_path, None)
    b = c.lade_oder_lege_projekt(tmp_path, None)
    assert a["projekt_id"] == b["projekt_id"]
    assert a["name"] == tmp_path.name
    assert (tmp_path / ".vesta" / "foerder-check.json").exists()
    neu = c.lade_oder_lege_projekt(tmp_path, "Musterhaus")
    assert neu["projekt_id"] == a["projekt_id"] and neu["name"] == "Musterhaus"


def test_message_mit_szene_und_projekt():
    m = c._build_a2a_message({"zielgruppe": "privatperson"}, szene={"format": "vesta-szene/1"},
                             projekt={"id": "abc", "name": "X"})
    data = m["message"]["parts"][0]["data"]
    assert data["skill"] == "customer.foerder_check"
    assert data["szene"]["format"] == "vesta-szene/1"
    assert data["projekt"] == {"id": "abc", "name": "X"}
    ohne = c._build_a2a_message({"zielgruppe": "privatperson"})["message"]["parts"][0]["data"]
    assert "szene" not in ohne and "projekt" not in ohne


def test_szene_zu_gross_nicht_gesendet(tmp_path, capsys):
    pfad = tmp_path / "szene.json"
    pfad.write_text(json.dumps({"format": "vesta-szene/1", "bin_gz_b64": "A" * 8_000_001}))
    assert c.lade_szene(pfad) is None
    assert "zu groß" in capsys.readouterr().err


def test_dashboard_geschrieben(umgebung):
    gesendet = {}

    def handler(request: httpx.Request) -> httpx.Response:
        gesendet["body"] = json.loads(request.content)
        gesendet["url"] = str(request.url)
        return httpx.Response(200, json=_antwort())

    rc = c.cmd_empfehlung(_args("--projektname", "Musterhaus"), transport=httpx.MockTransport(handler))
    assert rc == 0
    ziel = umgebung / "foerder-check-dashboard.html"
    assert ziel.read_text(encoding="utf-8") == HTML
    projekt = json.loads((umgebung / ".vesta" / "foerder-check.json").read_text())
    assert projekt["name"] == "Musterhaus"
    assert len(projekt["laeufe"]) == 1
    assert projekt["laeufe"][0]["n_eligible"] == 1
    assert projekt["laeufe"][0]["mit_3d"] is False
    data = gesendet["body"]["message"]["parts"][0]["data"]
    assert data["projekt"]["id"] == projekt["projekt_id"]
    assert gesendet["url"] == "https://a2a.test/customer/a2a/message:send"


def test_report_alias(umgebung):
    rc = c.cmd_empfehlung(_args("--report", "anders.html"),
                          transport=httpx.MockTransport(lambda r: httpx.Response(200, json=_antwort())))
    assert rc == 0 and (umgebung / "anders.html").exists()


def test_default_url():
    assert c.DEFAULT_A2A_URL == "https://agents.vesta-consult.de/customer"
