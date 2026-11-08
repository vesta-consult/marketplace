"""Länderquellen: Kachelraster und URL-Vorlagen (Recherche 08.11.2026)."""
from __future__ import annotations

import pytest

import lod2_laender as ll


def test_kacheln_by_zwei_kacheln_nord():
    # 2-km-Raster: Radius 350 m schneidet die Kachelgrenze bei N = 5516 km
    assert ll.kacheln("by", 726500.0, 5431950.0, 100) == [(726, 5430), (726, 5432)]


def test_kacheln_ecke():
    # Review Focus 3: Radius schneidet eine Kachelecke, alle vier Kacheln
    assert ll.kacheln("by", 566010, 5516010, 100) == [
        (564, 5514),
        (564, 5516),
        (566, 5514),
        (566, 5516),
    ]


def test_kacheln_bw_ungerade():
    assert ll.kacheln("bw", 513553, 5402810, 150) == [(513, 5402)]


def test_kacheln_mv():
    assert ll.kacheln("mv", 312297, 5997199, 150) == [(312, 5996)]


def test_kacheln_1km_grenze():
    # 1-km-Raster (NRW): Radius über die Ostgrenze ergibt zwei Kacheln
    assert ll.kacheln("nrw", 356950, 5645500, 100) == [(356, 5645), (357, 5645)]


@pytest.mark.parametrize(
    "land, e, n, erwartet",
    [
        (
            "by",
            566,
            5516,
            "https://download1.bayernwolke.de/a/lod2/citygml/566_5516.gml",
        ),
        (
            "bw",
            513,
            5402,
            "https://opengeodata.lgl-bw.de/data/lod2/LoD2_32_513_5402_2_bw.zip",
        ),
        ("be", 392, 5820, "https://gdi.berlin.de/data/a_lod2/atom/LoD2_392_5820.zip"),
        (
            "bb",
            368,
            5806,
            "https://data.geobasis-bb.de/geobasis/daten/3d_gebaeude/lod2_gml/lod2_33368-5806.zip",
        ),
        (
            "mv",
            312,
            5996,
            "https://www.geodaten-mv.de/dienste/gebaeude_download?index=0"
            "&dataset=8397b554-5cb9-4274-8be8-c20490d9a6e8&file=lod2_33_312_5996_2_gml.zip",
        ),
        (
            "ni",
            434,
            5792,
            "https://lod2.s3.eu-de.cloud-object-storage.appdomain.cloud/LoD2_32_434_5792_1_ni.gml",
        ),
        (
            "rp",
            446,
            5538,
            "https://geobasis-rlp.de/data/geb3dlo/current/gml/LoD2_32_446_5538_2_RP.gml",
        ),
        (
            "nrw",
            356,
            5645,
            "https://www.opengeodata.nrw.de/produkte/geobasis/3dg/lod2_gml/lod2_gml/"
            "LoD2_32_356_5645_1_NW.gml",
        ),
    ],
)
def test_urls(land, e, n, erwartet):
    assert ll.kachel_url(land, e, n) == erwartet


def test_sh_nur_ueber_index():
    with pytest.raises(ValueError):
        ll.kachel_url("sh", 573, 6020)
    assert ll.LAENDER["sh"].index == "sh_geojson"


def test_hinweislaender():
    assert set(ll.HINWEIS) == {"hb", "hh", "he", "sl", "sn", "st", "th"}
    assert set(ll.LAENDER) == {"by", "nrw", "bw", "be", "bb", "mv", "ni", "sh", "rp"}
    assert not set(ll.LAENDER) & set(ll.HINWEIS)
    for satz in ll.HINWEIS.values():
        assert "https://" in satz


def test_epsg_und_versatz():
    assert {k for k, q in ll.LAENDER.items() if q.epsg == 25833} == {"be", "bb", "mv"}
    assert ll.LAENDER["bw"].e_versatz_km == 1
    assert all(q.e_versatz_km == 0 for k, q in ll.LAENDER.items() if k != "bw")
    for q in ll.LAENDER.values():
        assert q.lizenz and q.quelle
        assert len(q.quelle) <= 200 and len(q.lizenz) <= 120


def test_unbekanntes_land():
    with pytest.raises(ValueError):
        ll.kacheln("xx", 0, 0, 100)
    with pytest.raises(ValueError):
        ll.kachel_url("hh", 565, 5933)
