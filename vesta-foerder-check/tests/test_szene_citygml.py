"""Szene aus CityGML 1.0 und 2.0 (synthetische Quader, keine echten Orte)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from lxml import etree

import szene_citygml as sc
from szene_pruefen import pruefe_format

DATEN = Path(__file__).parent / "daten"
BOX10 = DATEN / "box_citygml10.gml"
BOX20 = DATEN / "box_citygml20.gml"
HERKUNFT = {
    "art": "citygml",
    "land": None,
    "quelle": "Testdaten (synthetisch)",
    "lizenz": None,
    "abgerufen": "2026-11-08",
    "datei": "box.gml",
}
# Quader 1: E 500000..500010, N 5400000..5400010; Quader 2: E 500050..500060 (EPSG:25832)
IM_QUADER_1 = (500005.0, 5400005.0)


def _szene(datei, punkt=IM_QUADER_1, radius=250.0, epsg=25832):
    return sc.baue_szene(
        [datei], punkt=punkt, epsg=epsg, radius_m=radius, herkunft=HERKUNFT
    )


@pytest.mark.parametrize("datei", [BOX10, BOX20], ids=["citygml10", "citygml20"])
def test_box_citygml_10_und_20(datei):
    sz = _szene(datei)
    arr = pruefe_format(sz)
    assert sz["counts"]["buildings"] == 2
    z = sz["ziel"]
    assert z["id"] == "TEST_GEB_1"
    assert z["grundflaeche_m2"] == pytest.approx(100, abs=1)
    assert z["hoehe_m"] == pytest.approx(6, abs=0.05)
    assert z["wandflaeche_m2"] == pytest.approx(240, abs=2)
    assert z["dachflaeche_m2"] == pytest.approx(100, abs=1)
    assert z["volumen_m3"] == pytest.approx(600, abs=6)
    assert z["funktion"] == "Wohngebäude"
    assert z["dachform"] == "Flachdach"
    assert [b["ziel"] for b in sz["buildings"]] == [True, False]
    assert sz["radius_m"] == 250.0
    lon, lat = sz["origin"]
    assert 8.9 < lon < 9.1 and 48.7 < lat < 48.8
    # Ursprung im Quader 1: dessen Vertices liegen um 0, Höhe 0 bis 6 m (Dezimeter)
    s = sz["starts"]
    p0 = arr["pos"][s[0] : s[1]]
    assert p0[:, :2].min() >= -52 and p0[:, :2].max() <= 52
    assert p0[:, 2].min() == 0 and p0[:, 2].max() == 60
    assert set(arr["klasse"][s[0] : s[1]]) == {1, 2}
    # 12 Außenkanten je Quader
    assert sz["edge_starts"] == [0, 12, 24]


def test_keine_adresse():
    for datei in (BOX10, BOX20):
        text = json.dumps(_szene(datei), ensure_ascii=False)
        for wort in ("Musterweg", "Beispielgasse", "Musterstadt", '"adr"'):
            assert wort not in text


def test_punkt_neben_gebaeude():
    # Review Focus 2: Punkt auf der Straße, 20 m westlich von Quader 1
    sz = _szene(BOX10, punkt=(499980.0, 5400005.0))
    assert sz["ziel"]["id"] == "TEST_GEB_1"
    assert sz["hinweis"] is None
    # 100 m entfernt: kein Zielgebäude, dafür ein Hinweis
    sz = _szene(BOX10, punkt=(499900.0, 5400005.0))
    pruefe_format(sz)
    assert sz["ziel"] is None
    assert sz["hinweis"] == sc.HINWEIS_KEIN_ZIEL
    assert not any(b["ziel"] for b in sz["buildings"])


def test_ohne_punkt_alle_gebaeude():
    sz = _szene(BOX20, punkt=None, radius=None)
    pruefe_format(sz)
    assert sz["counts"]["buildings"] == 2
    assert sz["ziel"] is None  # zwei Gebäude, keins ist ausgezeichnet
    assert sz["radius_m"] is None
    assert [b["d"] for b in sz["buildings"]] == [
        20.0,
        20.0,
    ]  # Ursprung = Mitte der Bounding Box


def test_ohne_punkt_ein_gebaeude_ist_ziel(tmp_path):
    baum = etree.parse(str(BOX20))
    mitglieder = baum.getroot().findall(
        "{http://www.opengis.net/citygml/2.0}cityObjectMember"
    )
    baum.getroot().remove(mitglieder[1])
    einzeln = tmp_path / "einzeln.gml"
    baum.write(str(einzeln))
    sz = _szene(einzeln, punkt=None, radius=None)
    assert sz["counts"]["buildings"] == 1
    assert sz["ziel"]["id"] == "TEST_GEB_1"
    assert sz["buildings"][0]["ziel"] is True


def test_radius_filtert_nach_grundrissmitte():
    sz = _szene(BOX10, radius=30.0)  # Mitte Quader 2 liegt 50 m entfernt
    assert [b["id"] for b in sz["buildings"]] == ["TEST_GEB_1"]


def test_doppelte_gebaeude_aus_zwei_kacheln_einmal():
    sz = sc.baue_szene(
        [BOX10, BOX10], punkt=IM_QUADER_1, epsg=25832, radius_m=250, herkunft=HERKUNFT
    )
    assert sz["counts"]["buildings"] == 2


def test_gebaeude_ohne_gml_id_bleiben_erhalten(tmp_path):
    baum = etree.parse(str(BOX10))
    for geb in baum.getroot().iter(
        "{http://www.opengis.net/citygml/building/1.0}Building"
    ):
        del geb.attrib["{http://www.opengis.net/gml}id"]
    ohne_id = tmp_path / "ohne_id.gml"
    baum.write(str(ohne_id))
    sz = _szene(ohne_id)
    pruefe_format(sz)
    ids = [b["id"] for b in sz["buildings"]]
    assert len(ids) == 2 and len(set(ids)) == 2
    assert sz["ziel"]["id"] == ids[0]


def test_radius_wird_verkleinert_wenn_szene_zu_gross(monkeypatch):
    eins = _szene(BOX10, radius=30.0)  # nur Quader 1
    monkeypatch.setattr(sc, "MAX_B64", len(eins["bin_gz_b64"]) + 10)
    monkeypatch.setattr(sc, "MIN_RADIUS_M", 10.0)
    sz = _szene(
        BOX10, radius=100.0
    )  # 100 → 75 → 56 → 42 m, Quader 2 (50 m) fällt heraus
    pruefe_format(sz)
    assert [b["id"] for b in sz["buildings"]] == ["TEST_GEB_1"]
    assert sz["radius_m"] == 42.0
    assert "Radius auf 42 m verkleinert" in sz["hinweis"]
    assert sz["ziel"]["id"] == "TEST_GEB_1"


def test_szene_zu_gross_ohne_punkt(monkeypatch):
    monkeypatch.setattr(sc, "MAX_B64", 10)
    with pytest.raises(sc.SzeneZuGross):
        _szene(BOX10, punkt=None, radius=None)


def test_keine_gebaeude_im_radius():
    with pytest.raises(sc.KeineGebaeude):
        _szene(BOX10, punkt=(510000.0, 5410000.0))


def test_ohne_crs_lokale_koordinaten():
    sz = _szene(BOX10, punkt=None, radius=None, epsg=None)
    pruefe_format(sz)
    assert sz["origin"] is None


def test_herkunft_wird_gekuerzt_und_bereinigt():
    h = dict(HERKUNFT, quelle="q" * 400, datei="d" * 300, unbekannt="x")
    sz = sc.baue_szene([BOX10], punkt=IM_QUADER_1, epsg=25832, radius_m=250, herkunft=h)
    pruefe_format(sz)
    assert len(sz["herkunft"]["quelle"]) == 300


def test_epsg_aus_datei_und_srs():
    assert sc.epsg_aus_datei(BOX10) == 25832
    assert sc.epsg_aus_datei(BOX20) == 25832
    assert (
        sc.epsg_aus_srs("urn:ogc:def:crs,crs:EPSG:6.12:25833,crs:EPSG:6.12:7837")
        == 25833
    )
    assert sc.epsg_aus_srs("EPSG:25832") == 25832
    assert sc.epsg_aus_srs("urn:adv:crs:ETRS89_UTM33*DE_DHHN2016_NH") == 25833
    assert sc.epsg_aus_srs("http://www.opengis.net/def/crs/EPSG/0/25832") == 25832
    assert sc.epsg_aus_srs("urn:ogc:def:crs:EPSG::31468") == 31468
    assert sc.epsg_aus_srs("lokal") is None


def test_codes_zu_namen():
    assert sc.funktion_name("31001_1000") == "Wohngebäude"
    assert sc.funktion_name("1000") == "Wohngebäude"
    assert sc.funktion_name("31001_4711") == "31001_4711"
    assert sc.funktion_name("31001_3012") == "Rathaus"
    assert sc.funktion_name("31001_3034") == "Museum"
    assert sc.funktion_name("51009_1610") == "Überdachung"
    assert sc.funktion_name("51009_4711") == "51009_4711"
    assert sc.funktion_name(None) is None
    assert sc.dachform_name("3100") == "Satteldach"
    assert sc.dachform_name("4711") == "4711"
