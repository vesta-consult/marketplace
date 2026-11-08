"""LoD2-Quellen der Länder für den Abruf bei Bedarf (nur Standardbibliothek).

Stand der Quellen: Prüfung vom 08.11.2026 mit echten HTTP-Abrufen. Automatisch geladen werden in
Version 1.1 die neun Länder mit fester Kachel-URL (bzw. Kachel-Index in Schleswig-Holstein). Für die
übrigen Länder gibt es einen Hinweis mit Portal-URL, dort kann die Datei von Hand geladen und mit
`modell3d.py --modell` verwendet werden.

Kachelraster: `x0_km = floor((x_m/1000 - off)/size)*size + off`, `off` = 1 nur für den Ostwert in
Baden-Württemberg (2-km-Kacheln mit ungeradem Ostwert). Die Kachel heißt nach ihrer linken unteren
Ecke in km.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class LandQuelle:
    code: str
    epsg: int
    kachel_km: int
    e_versatz_km: int
    url: str  # Vorlage mit {e} und {n}; bei index != None die Adresse des Index
    format: Literal["gml", "zip"]  # gml = unkomprimiertes CityGML (.gml oder .xml)
    index: str | None
    lizenz: str
    quelle: str


_MV = (
    "https://www.geodaten-mv.de/dienste/gebaeude_download?index=0"
    "&dataset=8397b554-5cb9-4274-8be8-c20490d9a6e8&file=lod2_33_{e}_{n}_2_gml.zip"
)
_SH_INDEX = (
    "https://geodaten.schleswig-holstein.de/gaialight-sh/_apps/dladownload/single.php"
    "?file=LOD2_SH_Massendownload.geojson&id=4"
)

LAENDER: dict[str, LandQuelle] = {
    q.code: q
    for q in (
        LandQuelle(
            code="by",
            epsg=25832,
            kachel_km=2,
            e_versatz_km=0,
            format="gml",
            index=None,
            url="https://download1.bayernwolke.de/a/lod2/citygml/{e}_{n}.gml",
            lizenz="CC BY 4.0",
            quelle="Bayerische Vermessungsverwaltung, 3D-Gebäudemodelle LoD2",
        ),
        LandQuelle(
            code="nrw",
            epsg=25832,
            kachel_km=1,
            e_versatz_km=0,
            format="gml",
            index=None,
            url="https://www.opengeodata.nrw.de/produkte/geobasis/3dg/lod2_gml/lod2_gml/"
            "LoD2_32_{e}_{n}_1_NW.gml",
            lizenz="dl-de/zero-2.0",
            quelle="Geobasis NRW, 3D-Gebäudemodell LoD2",
        ),
        LandQuelle(
            code="bw",
            epsg=25832,
            kachel_km=2,
            e_versatz_km=1,
            format="zip",
            index=None,
            url="https://opengeodata.lgl-bw.de/data/lod2/LoD2_32_{e}_{n}_2_bw.zip",
            lizenz="dl-de/by-2.0",
            quelle="Datenquelle: LGL, www.lgl-bw.de, 3D-Gebäudemodelle LoD2",
        ),
        LandQuelle(
            code="be",
            epsg=25833,
            kachel_km=1,
            e_versatz_km=0,
            format="zip",
            index=None,
            url="https://gdi.berlin.de/data/a_lod2/atom/LoD2_{e}_{n}.zip",
            lizenz="dl-de/zero-2.0",
            quelle="Geoportal Berlin, 3D-Gebäudemodelle LoD2",
        ),
        LandQuelle(
            code="bb",
            epsg=25833,
            kachel_km=1,
            e_versatz_km=0,
            format="zip",
            index=None,
            url="https://data.geobasis-bb.de/geobasis/daten/3d_gebaeude/lod2_gml/"
            "lod2_33{e}-{n}.zip",
            lizenz="dl-de/by-2.0",
            quelle="GeoBasis-DE/LGB, 3D-Gebäudemodelle LoD2",
        ),
        LandQuelle(
            code="mv",
            epsg=25833,
            kachel_km=2,
            e_versatz_km=0,
            format="zip",
            index=None,
            url=_MV,
            lizenz="CC BY 4.0",
            quelle="GeoBasis-DE/M-V, 3D-Gebäudemodelle LoD2",
        ),
        LandQuelle(
            code="ni",
            epsg=25832,
            kachel_km=1,
            e_versatz_km=0,
            format="gml",
            index=None,
            url="https://lod2.s3.eu-de.cloud-object-storage.appdomain.cloud/"
            "LoD2_32_{e}_{n}_1_ni.gml",
            lizenz="CC BY 4.0",
            quelle="GeoBasis-DE/LGLN, 3D-Gebäudemodelle LoD2",
        ),
        LandQuelle(
            code="sh",
            epsg=25832,
            kachel_km=1,
            e_versatz_km=0,
            format="gml",
            index="sh_geojson",  # Kachel-URL aus properties.data_link, nicht selbst bauen
            url=_SH_INDEX,
            lizenz="CC BY 4.0",
            quelle="GeoBasis-DE/LVermGeo SH, 3D-Gebäudemodelle LoD2",
        ),
        LandQuelle(
            code="rp",
            epsg=25832,
            kachel_km=2,
            e_versatz_km=0,
            format="gml",
            index=None,
            url="https://geobasis-rlp.de/data/geb3dlo/current/gml/LoD2_32_{e}_{n}_2_RP.gml",
            lizenz="dl-de/by-2.0",
            quelle="GeoBasis-DE/LVermGeoRP, 3D-Gebäudemodelle LoD2",
        ),
    )
}

_HAND = "Datei von Hand laden und mit --modell angeben, oder ohne 3D weiter:"

HINWEIS: dict[str, str] = {
    "hb": "Bremen: LoD2 gibt es nur als großes Stadt-ZIP, automatischer Abruf ab Version 1.2. "
    f"{_HAND} https://www.geo.bremen.de/open-data-landingpage-15613",
    "hh": "Hamburg: LoD2 gibt es nur als großes Stadt-ZIP, automatischer Abruf ab Version 1.2. "
    f"{_HAND} https://suche.transparenz.hamburg.de/dataset/3d-gebaeudemodell-lod2-de-hamburg2",
    "he": "Hessen: LoD2 gibt es nur je Gemeinde mit wechselnder Download-Adresse, automatischer "
    f"Abruf ab Version 1.2. {_HAND} https://gds.hessen.de/",
    "sl": "Saarland: LoD2 gibt es nur als Landkreis-ZIP mit wechselnder Freigabe, automatischer "
    f"Abruf ab Version 1.2. {_HAND} https://www.shop.lvgl.saarland.de/cloud/freiegeobasisdaten",
    "sn": "Sachsen: Die Download-Freigabe wechselt, automatischer Abruf ab Version 1.2. "
    f"{_HAND} https://www.geodaten.sachsen.de/",
    "st": "Sachsen-Anhalt: Der Abruf läuft über eine Portalschnittstelle, automatischer Abruf ab "
    f"Version 1.2. {_HAND} https://www.lvermgeo.sachsen-anhalt.de/de/gdp-download-lod2.html",
    "th": "Thüringen: Der Download-Dienst war bei der Prüfung nicht verfügbar, kein automatischer "
    f"Abruf. {_HAND} https://geoportal.thueringen.de/gdi-th/download-offene-geodaten/"
    "download-3d-gebaeudedaten",
}


def _quelle(land: str) -> LandQuelle:
    try:
        return LAENDER[land]
    except KeyError:
        raise ValueError(f"Land {land!r} hat keine automatische LoD2-Quelle") from None


def _ursprung(x_m: float, size: int, off: int) -> int:
    return math.floor((x_m / 1000.0 - off) / size) * size + off


def kacheln(land: str, e: float, n: float, radius_m: float) -> list[tuple[int, int]]:
    """Linke untere Kachelecken (km) aller Kacheln, die das Quadrat Punkt ± Radius berühren."""
    q = _quelle(land)
    s = q.kachel_km
    e0, e1 = (_ursprung(x, s, q.e_versatz_km) for x in (e - radius_m, e + radius_m))
    n0, n1 = (_ursprung(y, s, 0) for y in (n - radius_m, n + radius_m))
    return sorted(
        (ek, nk) for ek in range(e0, e1 + 1, s) for nk in range(n0, n1 + 1, s)
    )


def kachel_url(land: str, e_km: int, n_km: int) -> str:
    q = _quelle(land)
    if q.index is not None:
        raise ValueError(f"{land}: Kachel-URL kommt aus dem Index (sh_url_aus_index)")
    return q.url.format(e=e_km, n=n_km)
