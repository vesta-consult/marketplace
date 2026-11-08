"""CLI modell3d.py: Formate, Exit-Codes und LoD2-Ablauf ohne Netz."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

import lod2_laden
import modell3d
from szene_pruefen import pruefe_format

DATEN = Path(__file__).parent / "daten"
BOX10 = DATEN / "box_citygml10.gml"
BEISPIEL_IFC = (
    Path(__file__).resolve().parents[2]
    / "vesta-quick-check"
    / "examples"
    / "beispiel.ifc"
)


def _letzte_zeile(capsys) -> dict:
    zeilen = [z for z in capsys.readouterr().out.splitlines() if z.strip()]
    return json.loads(zeilen[-1])


@pytest.fixture
def ohne_netz(tmp_path, monkeypatch):
    """Cache in tmp, jeder echte Netzaufruf schlägt fehl."""
    monkeypatch.setattr(lod2_laden, "cache_ordner", lambda: tmp_path / "cache")

    def kein_netz(*a, **k):
        raise AssertionError("Netz im Test")

    for name in ("geocode", "groesse", "lade", "sh_url_aus_index"):
        monkeypatch.setattr(lod2_laden, name, kein_netz)
    return monkeypatch


def test_cli_format_6(tmp_path, capsys):
    obj = tmp_path / "haus.obj"
    obj.write_text("v 0 0 0\n")
    assert modell3d.main(["--modell", str(obj), "--out", str(tmp_path / "s.json")]) == 6
    assert not (tmp_path / "s.json").exists()


def test_cli_modell_fehlt_2(tmp_path):
    assert (
        modell3d.main(
            [
                "--modell",
                str(tmp_path / "gibtsnicht.gml"),
                "--out",
                str(tmp_path / "s.json"),
            ]
        )
        == 2
    )


def test_cli_modell_citygml(tmp_path, capsys):
    out = tmp_path / "unter" / "szene.json"
    assert modell3d.main(["--modell", str(BOX10), "--out", str(out)]) == 0
    letzte = _letzte_zeile(capsys)
    assert letzte["szene"] == str(out)
    assert letzte["bundesland"] is None
    assert letzte["ziel"] is False  # zwei Gebäude ohne Punkt
    assert letzte["groesse_mb"] >= 0
    sz = json.loads(out.read_text())
    pruefe_format(sz)
    assert sz["herkunft"]["art"] == "citygml"
    assert sz["herkunft"]["datei"] == "box_citygml10.gml"
    assert sz["origin"] is not None  # CRS aus srsName erkannt


def test_cli_modell_zip(tmp_path, capsys):
    z = tmp_path / "modell.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.write(BOX10, "unterordner/box.gml")
        zf.writestr("liesmich.txt", "x")
    assert modell3d.main(["--modell", str(z), "--out", str(tmp_path / "s.json")]) == 0
    assert _letzte_zeile(capsys)["ziel"] is False


def test_cli_modell_zip_ohne_gml_6(tmp_path):
    z = tmp_path / "leer.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("haus.obj", "v 0 0 0")
    assert modell3d.main(["--modell", str(z), "--out", str(tmp_path / "s.json")]) == 6


def test_cli_modell_ifc(tmp_path, capsys):
    pytest.importorskip("ifcopenshell")
    out = tmp_path / "s.json"
    assert modell3d.main(["--modell", str(BEISPIEL_IFC), "--out", str(out)]) == 0
    assert _letzte_zeile(capsys)["ziel"] is True
    assert json.loads(out.read_text())["herkunft"]["art"] == "ifc"


def test_cli_adresse_unklar_3(tmp_path, capsys, ohne_netz):
    kandidaten = [
        lod2_laden.Treffer(48.1, 11.5, "by", "Musterweg 1, Musterstadt"),
        lod2_laden.Treffer(48.2, 11.5, "by", "Musterweg 1, Beispielort"),
    ]
    ohne_netz.setattr(lod2_laden, "geocode", lambda adresse, client: kandidaten)
    rc = modell3d.main(["--adresse", "Musterweg 1", "--out", str(tmp_path / "s.json")])
    assert rc == 3
    aus = _letzte_zeile(capsys)
    assert [k["anzeige"] for k in aus["kandidaten"]] == [k.anzeige for k in kandidaten]


def test_cli_adresse_leer_3(tmp_path, capsys, ohne_netz):
    ohne_netz.setattr(lod2_laden, "geocode", lambda adresse, client: [])
    assert (
        modell3d.main(["--adresse", "Musterweg 1", "--out", str(tmp_path / "s.json")])
        == 3
    )
    assert _letzte_zeile(capsys) == {"kandidaten": []}


def test_cli_hinweisland_5(tmp_path, capsys, ohne_netz):
    t = lod2_laden.Treffer(53.5, 10.0, "hh", "Musterweg 1, Musterstadt")
    ohne_netz.setattr(lod2_laden, "geocode", lambda adresse, client: [t])
    assert (
        modell3d.main(["--adresse", "Musterweg 1", "--out", str(tmp_path / "s.json")])
        == 5
    )
    assert "Hamburg" in _letzte_zeile(capsys)["hinweis"]


def test_cli_bundesland_ueberschreibt_treffer(tmp_path, capsys, ohne_netz):
    t = lod2_laden.Treffer(48.1, 11.5, "by", "Musterweg 1, Musterstadt")
    ohne_netz.setattr(lod2_laden, "geocode", lambda adresse, client: [t])
    rc = modell3d.main(
        [
            "--adresse",
            "Musterweg 1",
            "--bundesland",
            "th",
            "--out",
            str(tmp_path / "s.json"),
        ]
    )
    assert rc == 5


def test_cli_lat_lon_braucht_bundesland_2(tmp_path, ohne_netz):
    assert (
        modell3d.main(
            ["--lat", "48.1", "--lon", "11.5", "--out", str(tmp_path / "s.json")]
        )
        == 2
    )


def test_cli_zu_gross_4(tmp_path, capsys, ohne_netz):
    ohne_netz.setattr(lod2_laden, "groesse", lambda url, client: 120_000_000)
    rc = modell3d.main(
        [
            "--lat",
            "48.1",
            "--lon",
            "11.5",
            "--bundesland",
            "by",
            "--radius",
            "250",
            "--out",
            str(tmp_path / "s.json"),
        ]
    )
    assert rc == 4
    aus = _letzte_zeile(capsys)
    assert aus["groesse_mb"] >= 200


def _punkt_wgs84(e, n):
    from pyproj import Transformer

    lon, lat = Transformer.from_crs(
        "EPSG:25832", "EPSG:4326", always_xy=True
    ).transform(e, n)
    return lat, lon


def test_cli_lod2_ablauf(tmp_path, capsys, ohne_netz):
    """Adresse → Kacheln → Größe → Laden → Szene, mit fehlenden Nachbarkacheln (404)."""
    lat, lon = _punkt_wgs84(500005.0, 5400005.0)
    t = lod2_laden.Treffer(lat, lon, "by", "Musterweg 1, Musterstadt")
    geladen: list[str] = []

    def groesse(url, client):
        if "500_5400" not in url:
            raise lod2_laden.KachelFehlt(url)
        return 12_345

    def lade(url, client, max_bytes):
        geladen.append(url)
        assert max_bytes >= 12_345
        return [BOX10]

    ohne_netz.setattr(lod2_laden, "geocode", lambda adresse, client: [t])
    ohne_netz.setattr(lod2_laden, "groesse", groesse)
    ohne_netz.setattr(lod2_laden, "lade", lade)
    out = tmp_path / "s.json"
    assert modell3d.main(["--adresse", "Musterweg 1", "--out", str(out)]) == 0
    letzte = _letzte_zeile(capsys)
    assert letzte == {
        "szene": str(out),
        "bundesland": "by",
        "ziel": True,
        "groesse_mb": letzte["groesse_mb"],
    }
    assert geladen == ["https://download1.bayernwolke.de/a/lod2/citygml/500_5400.gml"]
    sz = json.loads(out.read_text())
    pruefe_format(sz)
    h = sz["herkunft"]
    assert (h["art"], h["land"], h["lizenz"], h["datei"]) == (
        "lod2",
        "by",
        "CC BY 4.0",
        None,
    )
    assert (
        "Bayerische Vermessungsverwaltung" in h["quelle"] and "500_5400" in h["quelle"]
    )
    assert sz["ziel"]["id"] == "TEST_GEB_1"
    assert sz["radius_m"] == 250.0
    assert "Musterweg" not in out.read_text()


def test_cli_keine_kachel_2(tmp_path, ohne_netz):
    def fehlt(url, client):
        raise lod2_laden.KachelFehlt(url)

    ohne_netz.setattr(lod2_laden, "groesse", fehlt)
    rc = modell3d.main(
        [
            "--lat",
            "48.1",
            "--lon",
            "11.5",
            "--bundesland",
            "by",
            "--out",
            str(tmp_path / "s.json"),
        ]
    )
    assert rc == 2
