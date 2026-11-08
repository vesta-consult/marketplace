"""Szene aus IFC (Beispieldatei aus vesta-quick-check)."""
from __future__ import annotations

from pathlib import Path

import pytest

from szene_pruefen import pruefe_format

BEISPIEL = (
    Path(__file__).resolve().parents[2]
    / "vesta-quick-check"
    / "examples"
    / "beispiel.ifc"
)
HERKUNFT = {
    "art": "ifc",
    "land": None,
    "quelle": "Modell aus Ihren Unterlagen",
    "lizenz": None,
    "abgerufen": "2026-11-08",
    "datei": "beispiel.ifc",
}


def test_ifc_beispiel():
    pytest.importorskip("ifcopenshell")
    import szene_ifc

    sz = szene_ifc.baue_szene_ifc(BEISPIEL, herkunft=HERKUNFT)
    arr = pruefe_format(sz)
    assert sz["counts"]["vertices"] > 0
    assert sz["origin"] is None and sz["radius_m"] is None
    assert sz["herkunft"]["art"] == "ifc"
    assert sz["counts"]["buildings"] == 1 and sz["buildings"][0]["ziel"] is True
    # Wand 3,0 × 0,3 × 2,0 m in Millimetern modelliert: Szene in Metern
    assert sz["ziel"]["hoehe_m"] == pytest.approx(2.0, abs=0.01)
    assert sz["ziel"]["grundflaeche_m2"] is None
    assert arr["pos"][:, 2].min() == 0 and arr["pos"][:, 2].max() == 20
    ausdehnung = arr["pos"][:, 0].max() - arr["pos"][:, 0].min()
    assert ausdehnung == 30
    assert sz["counts"]["edges"] > 0
    assert set(arr["klasse"]) == {1}


def test_ifc_ohne_geometrie(tmp_path):
    ifcopenshell = pytest.importorskip("ifcopenshell")
    import szene_ifc

    f = ifcopenshell.file(schema="IFC4")
    f.createIfcProject(ifcopenshell.guid.new(), None, "leer")
    leer = tmp_path / "leer.ifc"
    f.write(str(leer))
    with pytest.raises(ValueError):
        szene_ifc.baue_szene_ifc(leer, herkunft=HERKUNFT)
