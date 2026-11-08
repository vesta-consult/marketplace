#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "httpx>=0.27",
#   "truststore>=0.9",
#   "platformdirs>=4",
#   "pyproj>=3.6",
#   "lxml>=5",
#   "numpy>=1.26",
#   "shapely>=2",
#   "mapbox-earcut>=1.0",
#   "ifcopenshell>=0.8",
# ]
# ///
"""3D-Szene für das Förder-Check-Dashboard (Format vesta-szene/1), lokal beim Kunden gebaut.

Quellen (genau eine):
  --modell PFAD        eigenes Modell: CityGML 1.0/2.0 (.gml, .xml, .zip mit GML) oder IFC (.ifc)
  --adresse TEXT       Adresse, Lage über OpenStreetMap Nominatim, LoD2 vom Download-Server des Landes
  --lat F --lon F      Koordinate (WGS84), dann ist --bundesland Pflicht

Weitere Optionen: --bundesland CODE, --radius 250, --out szene.json, --erlaube-gross.

Exit-Codes:
  0 ok (letzte stdout-Zeile: {"szene", "bundesland", "ziel", "groesse_mb"})
  2 Fehler (Meldung auf stderr)
  3 Adresse unklar (stdout {"kandidaten": [...]}), nachfragen statt raten
  4 Download über 200 MB (stdout {"groesse_mb": x}), nach Rückfrage mit --erlaube-gross
  5 Land ohne automatische Quelle (stdout {"hinweis": "..."}), ohne 3D weiter
  6 Format nicht unterstützt (stdout {"hinweis": "..."}), um IFC- oder CityGML-Export bitten

Datenschutz: Die Adresse geht an Nominatim und an den Landesserver, nie an Vesta. Die Szene enthält
keine Adressen, wohl aber die Lage (Ursprung) des Gebäudes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lod2_laden  # noqa: E402
import lod2_laender  # noqa: E402
import szene_citygml  # noqa: E402

GRENZE_BYTES = 200_000_000
GRENZE_ERLAUBT = 5_000_000_000
CODES = sorted(set(lod2_laender.LAENDER) | set(lod2_laender.HINWEIS))
FORMAT_HINWEIS = (
    "Format nicht unterstützt. Bitte das Modell als IFC oder CityGML exportieren."
)


class _Abbruch(Exception):
    def __init__(self, code: int, meldung: str, ausgabe: dict | None = None):
        super().__init__(meldung)
        self.code, self.ausgabe = code, ausgabe


def _info(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


def _heute() -> str:
    return dt.date.today().isoformat()


def _aus_modell(pfad: Path) -> dict:
    if not pfad.is_file():
        raise _Abbruch(2, f"Datei nicht gefunden: {pfad.name}")
    endung = pfad.suffix.lower()
    herkunft = {
        "land": None,
        "quelle": "Modell aus Ihren Unterlagen",
        "lizenz": None,
        "abgerufen": _heute(),
        "datei": pfad.name,
    }
    if endung == ".ifc":
        import szene_ifc

        return szene_ifc.baue_szene_ifc(pfad, herkunft={"art": "ifc", **herkunft})
    if endung not in (".gml", ".xml", ".zip"):
        raise _Abbruch(6, FORMAT_HINWEIS, {"hinweis": FORMAT_HINWEIS})
    tmp = Path(tempfile.mkdtemp(prefix="vesta-modell-")) if endung == ".zip" else None
    try:
        dateien = lod2_laden.entpacke_zip(pfad, tmp) if tmp else [pfad]
        if not dateien:
            raise _Abbruch(
                6, "Im ZIP liegt keine GML-Datei.", {"hinweis": FORMAT_HINWEIS}
            )
        try:
            return szene_citygml.baue_szene(
                dateien,
                punkt=None,
                epsg=szene_citygml.epsg_aus_datei(dateien[0]),
                radius_m=None,
                herkunft={"art": "citygml", **herkunft},
            )
        except szene_citygml.etree.XMLSyntaxError as e:
            raise _Abbruch(
                6, f"Datei ist kein lesbares CityGML: {e}", {"hinweis": FORMAT_HINWEIS}
            )
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


def _aus_lod2(a: argparse.Namespace) -> tuple[dict, str]:
    with lod2_laden.http_client() as client:
        if a.adresse is not None:
            try:
                t = lod2_laden.waehle_treffer(
                    lod2_laden.geocode(a.adresse, client=client)
                )
            except lod2_laden.UnklareAdresse as e:
                raise _Abbruch(
                    3,
                    "Adresse nicht eindeutig gefunden, bitte nachfragen statt raten.",
                    {"kandidaten": [asdict(k) for k in e.kandidaten]},
                ) from None
            lat, lon, land = t.lat, t.lon, a.bundesland or t.bundesland
            _info(f"Lage gefunden: {t.anzeige}")
        else:
            if a.lon is None:
                raise _Abbruch(2, "--lat braucht --lon")
            if not a.bundesland:
                raise _Abbruch(2, "Bei --lat/--lon ist --bundesland Pflicht.")
            lat, lon, land = a.lat, a.lon, a.bundesland
        if not land:
            raise _Abbruch(2, "Bundesland nicht erkannt, bitte --bundesland angeben.")
        if land in lod2_laender.HINWEIS:
            hinweis = lod2_laender.HINWEIS[land]
            raise _Abbruch(5, hinweis, {"hinweis": hinweis})
        q = lod2_laender.LAENDER[land]
        e, n = lod2_laden.nach_utm(lat, lon, q.epsg)

        kacheln: list[tuple[str, str]] = []
        for ek, nk in lod2_laender.kacheln(land, e, n, a.radius):
            if q.index == "sh_geojson":
                try:
                    url = lod2_laden.sh_url_aus_index(
                        ek * 1000 + 500, nk * 1000 + 500, client=client
                    )
                except lod2_laden.KachelFehlt:
                    continue
            else:
                url = lod2_laender.kachel_url(land, ek, nk)
            kacheln.append((f"{ek}_{nk}", url))

        vorhanden, summe = [], 0
        for name, url in kacheln:
            if lod2_laden.ist_im_cache(url):
                vorhanden.append((name, url))
                continue
            try:
                summe += lod2_laden.groesse(url, client=client) or 0
            except lod2_laden.KachelFehlt:
                _info(f"Kachel {name}: keine Daten (404), übersprungen")
                continue
            vorhanden.append((name, url))
        if not vorhanden:
            raise _Abbruch(2, "Für diese Stelle gibt es keine LoD2-Kachel.")
        if summe > GRENZE_BYTES and not a.erlaube_gross:
            mb = round(summe / 1e6, 1)
            raise _Abbruch(
                4, f"Download {mb} MB über der Grenze von 200 MB.", {"groesse_mb": mb}
            )

        budget = GRENZE_ERLAUBT if a.erlaube_gross else GRENZE_BYTES
        _info(f"LoD2 {land}: {len(vorhanden)} Kachel(n), zu laden {summe / 1e6:.1f} MB")
        dateien, namen = [], []
        for name, url in vorhanden:
            try:
                dateien += lod2_laden.lade(url, client=client, max_bytes=budget)
            except lod2_laden.ZuGross as z:
                mb = round(max(z.bytes, summe) / 1e6, 1)
                raise _Abbruch(
                    4, f"Download über {budget / 1e6:.0f} MB.", {"groesse_mb": mb}
                ) from None
            except lod2_laden.KachelFehlt:
                continue
            namen.append(name)
        if not dateien:
            raise _Abbruch(2, "Für diese Stelle gibt es keine LoD2-Kachel.")

    _info("Szene wird gebaut …")
    try:
        sz = szene_citygml.baue_szene(
            dateien,
            punkt=(e, n),
            epsg=q.epsg,
            radius_m=a.radius,
            herkunft={
                "art": "lod2",
                "land": land,
                "quelle": f"{q.quelle}, Kacheln {', '.join(namen)}",
                "lizenz": q.lizenz,
                "abgerufen": _heute(),
                "datei": None,
            },
        )
    except szene_citygml.KeineGebaeude:
        raise _Abbruch(
            2, f"Im Umkreis von {a.radius:.0f} m stehen laut LoD2 keine Gebäude."
        ) from None
    return sz, land


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="3D-Szene für das Förder-Check-Dashboard")
    quelle = ap.add_mutually_exclusive_group(required=True)
    quelle.add_argument(
        "--modell", type=Path, help="eigenes Modell (.gml, .xml, .zip, .ifc)"
    )
    quelle.add_argument("--adresse", help="Adresse des Gebäudes")
    quelle.add_argument(
        "--lat", type=float, help="Breite WGS84 (mit --lon und --bundesland)"
    )
    ap.add_argument("--lon", type=float, help="Länge WGS84")
    ap.add_argument(
        "--bundesland", choices=CODES, help="Bundesland-Code wie im Berater"
    )
    ap.add_argument(
        "--radius", type=float, default=250.0, help="Umkreis in m (25 bis 500)"
    )
    ap.add_argument("--out", type=Path, default=Path("szene.json"))
    ap.add_argument(
        "--erlaube-gross", action="store_true", help="Downloads über 200 MB erlauben"
    )
    a = ap.parse_args(argv)

    try:
        if a.lon is not None and a.lat is None:
            raise _Abbruch(2, "--lon braucht --lat")
        if not 25 <= a.radius <= 500:
            raise _Abbruch(2, "--radius muss zwischen 25 und 500 m liegen")
        if a.modell is not None:
            sz, land = _aus_modell(a.modell), a.bundesland
        else:
            sz, land = _aus_lod2(a)
    except _Abbruch as e:
        _info(str(e))
        if e.ausgabe is not None:
            print(json.dumps(e.ausgabe, ensure_ascii=False))
        return e.code
    except (
        Exception
    ) as e:  # Download, Parser, Geometrie: Förderteil läuft ohne 3D weiter
        _info(f"Fehler: {type(e).__name__}: {e}")
        return 2

    text = json.dumps(sz, ensure_ascii=False, separators=(",", ":"))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text, encoding="utf-8")
    if sz["hinweis"]:
        _info(f"Hinweis: {sz['hinweis']}")
    _info(f"{sz['counts']['buildings']} Gebäude, Szene {len(text) / 1e6:.2f} MB")
    print(
        json.dumps(
            {
                "szene": str(a.out.absolute()),
                "bundesland": land,
                "ziel": sz["ziel"] is not None,
                "groesse_mb": round(len(text.encode("utf-8")) / 1e6, 2),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
