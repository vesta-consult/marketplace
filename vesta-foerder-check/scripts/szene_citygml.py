"""Szene `vesta-szene/1` aus CityGML 1.0 oder 2.0 (LoD2-Kacheln der Länder oder eigene Datei).

Port des Vesta-Werkzeugs für LoD2-Szenen (Licht, Newell-Normale, earcut, Kanten, Binärformat),
erweitert um CityGML 2.0, Streaming per iterparse, Zielgebäude am Punkt und das Szenenformat des
Förder-Check-Dashboards. Adressen (xAL) werden nie gelesen, die Szene enthält keine.

Binärteil (little endian, gzip, base64), in dieser Reihenfolge:
  Positionen  int16 × 3V   Dezimeter, lokal relativ zu `origin` (deck.gl METER_OFFSETS)
  Licht       uint8 × V    eingebackene Helligkeit 0..255
  Klasse      uint8 × V    1 = Wand, 2 = Dach
  Dreiecke    uint32 × 3T  globale Vertexindizes
  Kanten      int16 × 6E   Kantensegmente in Dezimetern
Gebäude b belegt die Vertices starts[b] .. starts[b+1]-1 und die Kanten edge_starts[b] ..
edge_starts[b+1]-1 (gemeinsame Kanten zählen zum zuerst gelesenen Gebäude).
"""
from __future__ import annotations

import base64
import datetime as dt
import gzip
import math
import re
from dataclasses import dataclass
from pathlib import Path

import mapbox_earcut as earcut
import numpy as np
from lxml import etree
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

GML = "http://www.opengis.net/gml"
GML_ID = f"{{{GML}}}id"
_VERSIONEN = ("1.0", "2.0")
_TAGS = [f"{{http://www.opengis.net/citygml/building/{v}}}Building" for v in _VERSIONEN]

WALL, ROOF = 1, 2
SURF = {
    "WallSurface": WALL,
    "RoofSurface": ROOF,
    "ClosureSurface": WALL,
    "OuterFloorSurface": ROOF,
    "OuterCeilingSurface": WALL,
}
ZIEL_MAX_M = 30.0  # nächstes Gebäude bis zu diesem Abstand wird Zielgebäude
MAX_OHNE_PUNKT = 5000
MAX_GEBAEUDE = 20_000
MAX_ELEMENTE = 2_000_000
MAX_B64 = 8_000_000
MIN_RADIUS_M = 60.0
HINWEIS_KEIN_ZIEL = (
    "Am angegebenen Punkt steht laut LoD2 kein Gebäude, Umgebung ohne Hervorhebung."
)

# ALKIS-Gebäudefunktion (Auszug), Schlüssel ohne Präfix 31001_
FUNKTION = {
    "1000": "Wohngebäude",
    "1010": "Wohnhaus",
    "1020": "Wohnheim",
    "1100": "Gemischt genutztes Gebäude mit Wohnen",
    "1120": "Wohngebäude mit Handel und Dienstleistungen",
    "1130": "Wohngebäude mit Gewerbe und Industrie",
    "2000": "Gebäude für Wirtschaft oder Gewerbe",
    "2010": "Gebäude für Handel und Dienstleistungen",
    "2020": "Bürogebäude",
    "2050": "Geschäftsgebäude",
    "2070": "Hotel, Motel, Pension",
    "2100": "Gebäude für Gewerbe und Industrie",
    "2463": "Garage",
    "3000": "Gebäude für öffentliche Zwecke",
    "3010": "Verwaltungsgebäude",
    "3012": "Rathaus",
    "3020": "Gebäude für Bildung und Forschung",
    "3021": "Allgemein bildende Schule",
    "3030": "Gebäude für Kultur",
    "3034": "Museum",
    "3035": "Rundfunk, Fernsehen",
    "3040": "Gebäude für religiöse Zwecke",
    "3041": "Kirche",
    "3050": "Gebäude für Gesundheitswesen",
    "3051": "Krankenhaus",
    "3060": "Gebäude für soziale Zwecke",
    "3065": "Kinderkrippe, Kindergarten, Kindertagesstätte",
    "3071": "Polizei",
    "9998": "nach Quellenlage nicht zuzuordnen",
    # Bauwerksfunktion sonstiger Bauwerke (51009), in LoD2-Kacheln als Gebäude geführt
    "51009_1610": "Überdachung",
}
# Dachform nach AdV-Codeliste
DACHFORM = {
    "1000": "Flachdach",
    "2100": "Pultdach",
    "2200": "Versetztes Pultdach",
    "3100": "Satteldach",
    "3200": "Walmdach",
    "3300": "Krüppelwalmdach",
    "3400": "Mansardendach",
    "3500": "Zeltdach",
    "3600": "Kegeldach",
    "3700": "Kuppeldach",
    "3800": "Sheddach",
    "3900": "Bogendach",
    "4000": "Turmdach",
    "5000": "Mischform",
    "9999": "Sonstiges",
}
# Licht wie in den übrigen 3D-Ansichten von Vesta
L = {
    "sunAz": 210.0,
    "sunEl": 42.0,
    "sun": 0.42,
    "fillAz": 30.0,
    "fillEl": 30.0,
    "fill": 0.12,
    "ambient": 0.50,
    "sky": 0.10,
    "aoFloor": 0.72,
    "aoHeight": 6.0,
    "topGain": 0.06,
    "topHeight": 40.0,
}
M_PER_DEG = 40075016.686 / 360.0  # Kugel der Web-Mercator-Projektion, wie deck.gl


class KeineGebaeude(ValueError):
    """Keine Gebäude mit verwertbarer Geometrie im Radius bzw. in der Datei."""


class SzeneZuGross(ValueError):
    """Die Szene überschreitet die Grenzen des Formats."""


def _dir(az: float, el: float) -> np.ndarray:
    a, e = math.radians(az), math.radians(el)
    return np.array([math.sin(a) * math.cos(e), math.cos(a) * math.cos(e), math.sin(e)])


LS, LF = _dir(L["sunAz"], L["sunEl"]), _dir(L["fillAz"], L["fillEl"])


def _smoothstep(a: float, b: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def licht(normalen: np.ndarray, z: np.ndarray, klasse: np.ndarray) -> np.ndarray:
    """Eingebackene Helligkeit je Vertex: Normalen (V,3), Höhe über Grund (V,), Klasse (V,)."""
    s = (
        L["ambient"]
        + L["sun"] * np.clip(normalen @ LS, 0, None)
        + L["fill"] * np.clip(normalen @ LF, 0, None)
        + L["sky"] * np.clip(normalen[:, 2], 0, None)
    )
    ao = L["aoFloor"] + (1 - L["aoFloor"]) * _smoothstep(0, L["aoHeight"], z)
    top = 1 + L["topGain"] * np.clip(
        (z - L["aoHeight"]) / (L["topHeight"] - L["aoHeight"]), 0, 1
    )
    s = np.where(klasse == WALL, s * ao * top, s)
    return np.round(np.clip(s, 0, 1) * 255).astype(np.uint8)


def newell(p: np.ndarray) -> tuple[np.ndarray, float]:
    """Einheitsnormale und Fläche eines Rings (n,3)."""
    q = np.roll(p, -1, axis=0)
    n = np.array(
        [
            np.sum((p[:, 1] - q[:, 1]) * (p[:, 2] + q[:, 2])),
            np.sum((p[:, 2] - q[:, 2]) * (p[:, 0] + q[:, 0])),
            np.sum((p[:, 0] - q[:, 0]) * (p[:, 1] + q[:, 1])),
        ]
    )
    ln = float(np.linalg.norm(n))
    return (n / ln if ln > 0 else n), ln / 2.0


def _triangulate(pts: np.ndarray, laengen: list[int], n: np.ndarray) -> np.ndarray:
    keep = [i for i in range(3) if i != int(np.argmax(np.abs(n)))]
    ends = np.cumsum(laengen).astype(np.uint32)
    tri = earcut.triangulate_float64(np.ascontiguousarray(pts[:, keep]), ends)
    return np.asarray(tri, dtype=np.int64).reshape(-1, 3)


# --- Namen und Koordinatensystem ------------------------------------------------------------


def funktion_name(code: str | None) -> str | None:
    if not code:
        return None
    code = code.strip()
    schluessel = code[6:] if code.startswith("31001_") else code
    return FUNKTION.get(code, FUNKTION.get(schluessel, code))[:80]


def dachform_name(code: str | None) -> str | None:
    if not code:
        return None
    code = code.strip()
    return DACHFORM.get(code, code)[:80]


_VERTIKAL = {5783, 5784, 5785, 7837}  # Höhensysteme in zusammengesetzten CRS


def epsg_aus_srs(srs: str | None) -> int | None:
    """EPSG-Code aus einem srsName (EPSG-URN/URL oder AdV-Kennung ETRS89_UTM32/33)."""
    s = srs or ""
    m = re.search(r"ETRS89_UTM(32|33)", s)
    if m:
        return 25800 + int(m.group(1))
    for teil in s.split("EPSG")[1:]:
        m = re.search(r"(?<![\d.])(\d{4,5})(?![\d.])", teil)
        if m and int(m.group(1)) not in _VERTIKAL:
            return int(m.group(1))
    return None


def epsg_aus_datei(pfad: Path) -> int | None:
    with open(pfad, "rb") as fh:
        kopf = fh.read(512 * 1024).decode("utf-8", "replace")
    m = re.search(r"srsName\s*=\s*[\"']([^\"']+)[\"']", kopf)
    return epsg_aus_srs(m.group(1)) if m else None


# --- Lesen (Phase 1, streamend) -------------------------------------------------------------


class _XP:
    def __init__(self, v: str):
        ns = {"bldg": f"http://www.opengis.net/citygml/building/{v}", "gml": GML}
        x = lambda p: etree.XPath(p, namespaces=ns)  # noqa: E731
        self.grund = x(".//bldg:GroundSurface//gml:Polygon")
        self.flaechen = {art: x(f".//bldg:{art}//gml:Polygon") for art in SURF}
        self.aussen = x("./gml:exterior//gml:LinearRing")
        self.innen = x("./gml:interior//gml:LinearRing")
        self.poslist = x("./gml:posList/text()")
        self.pos = x("./gml:pos/text()")
        self.hoehe = x("./bldg:measuredHeight/text()")
        self.hoehe_teile = x(".//bldg:BuildingPart/bldg:measuredHeight/text()")
        self.funktion = x(
            "./bldg:function/text()|.//bldg:BuildingPart/bldg:function/text()"
        )
        self.dach = x(
            "./bldg:roofType/text()|.//bldg:BuildingPart/bldg:roofType/text()"
        )


_XPS = {f"http://www.opengis.net/citygml/building/{v}": _XP(v) for v in _VERSIONEN}


@dataclass
class _Geb:
    id: str
    fp: Polygon
    flaechen: list[tuple[str, list[np.ndarray]]]
    z0: float
    hoehe: float
    funktion: str | None
    dachform: str | None


def _ring(lr, xp: _XP) -> np.ndarray | None:
    t = xp.poslist(lr)
    text = t[0] if t else " ".join(xp.pos(lr))
    try:
        v = np.array(text.split(), dtype=float)
    except ValueError:
        return None
    if v.size < 9 or v.size % 3:
        return None
    v = v.reshape(-1, 3)
    if np.allclose(v[0], v[-1]):
        v = v[:-1]
    return v if len(v) >= 3 else None


def _polygon(poly, xp: _XP) -> list[np.ndarray] | None:
    aussen = xp.aussen(poly)
    r0 = _ring(aussen[0], xp) if aussen else None
    if r0 is None:
        return None
    return [r0] + [r for r in (_ring(i, xp) for i in xp.innen(poly)) if r is not None]


def _grundriss(polys: list[list[np.ndarray]]):
    teile = []
    for rings in polys:
        try:
            pg = Polygon(rings[0][:, :2], [r[:, :2] for r in rings[1:]]).buffer(0)
        except (ValueError, TypeError):
            continue
        if not pg.is_empty and pg.area > 0:
            teile.append(pg)
    if not teile:
        return None
    fp = unary_union(teile)
    return None if fp.is_empty else fp


def _zahl(texte: list[str]) -> float | None:
    for t in texte:
        try:
            return float(t)
        except ValueError:
            continue
    return None


def _gebaeude(el, pt: Point | None, radius_m: float | None) -> _Geb | None:
    xp = _XPS[etree.QName(el).namespace]
    grund = [p for p in (_polygon(q, xp) for q in xp.grund(el)) if p]
    fp = _grundriss(grund)
    if fp is None:  # ohne Grundfläche: Dachflächen von oben
        fp = _grundriss(
            [p for p in (_polygon(q, xp) for q in xp.flaechen["RoofSurface"](el)) if p]
        )
    if fp is None:
        return None
    if pt is not None and radius_m is not None:
        if fp.centroid.distance(pt) > radius_m and fp.distance(pt) > ZIEL_MAX_M:
            return None
    flaechen = [
        (art, rings)
        for art in SURF
        for rings in (_polygon(q, xp) for q in xp.flaechen[art](el))
        if rings
    ]
    if not flaechen:
        return None
    alle_z = np.concatenate([r[:, 2] for _, rings in flaechen for r in rings])
    # Unterkante = tiefster Punkt der Grundfläche (nicht HoeheGrund), so liegt nichts unter 0
    z0 = (
        float(min(r[:, 2].min() for rings in grund for r in rings))
        if grund
        else float(alle_z.min())
    )
    hoehe = _zahl(xp.hoehe(el))
    if hoehe is None:
        teile = [h for h in (_zahl([t]) for t in xp.hoehe_teile(el)) if h is not None]
        hoehe = max(teile) if teile else float(alle_z.max()) - z0
    return _Geb(
        id=(el.get(GML_ID) or "")[:80],  # leer: _lese vergibt eine laufende ID
        fp=fp,
        flaechen=flaechen,
        z0=z0,
        hoehe=hoehe,
        funktion=next(iter(xp.funktion(el)), None),
        dachform=next(iter(xp.dach(el)), None),
    )


def _aufraeumen(el) -> None:
    el.clear(keep_tail=True)
    anker = el.getparent() if el.getparent() is not None else el
    while anker.getprevious() is not None and anker.getparent() is not None:
        del anker.getparent()[0]


def _lese(dateien: list[Path], pt: Point | None, radius_m: float | None):
    gebaeude: list[_Geb] = []
    gesehen: set[str] = set()
    for datei in dateien:
        for _, el in etree.iterparse(
            str(datei),
            events=("end",),
            tag=_TAGS,
            huge_tree=True,
            resolve_entities=False,
            no_network=True,
        ):
            try:
                g = _gebaeude(el, pt, radius_m)
            finally:
                _aufraeumen(el)
            # Dubletten (Gebäude in zwei Kacheln) nur über eine echte gml:id erkennen
            if g is None or (g.id and g.id in gesehen):
                continue
            if pt is None and len(gebaeude) >= MAX_OHNE_PUNKT:
                return gebaeude, True
            if not g.id:
                g.id = f"geb_{len(gebaeude) + 1}"
            gesehen.add(g.id)
            gebaeude.append(g)
    return gebaeude, False


# --- Geometrie (Phase 2) --------------------------------------------------------------------


@dataclass
class Mesh:
    pos: np.ndarray  # (V,3) Meter, lokal
    licht: np.ndarray  # (V,) uint8
    klasse: np.ndarray  # (V,) uint8
    dreiecke: np.ndarray  # (T,3) Indizes innerhalb des Mesh
    kanten: np.ndarray  # (K,6) Meter


@dataclass
class _Kenn:
    wand: float
    dach: float
    volumen: float


def _mesh(g: _Geb, lokal) -> tuple[Mesh, _Kenn] | None:
    ringe = [r for _, rings in g.flaechen for r in rings]
    utm = np.vstack(ringe)
    enu = lokal(utm, g.z0)
    c = g.fp.centroid
    u_all = utm - np.array([c.x, c.y, g.z0])
    pos, lic, kla, tri, kan = [], [], [], [], []
    wand = dach = vol = 0.0
    nv, o = 0, 0
    for art, rings in g.flaechen:
        laengen = [len(r) for r in rings]
        k = sum(laengen)
        u, e = u_all[o : o + k], enu[o : o + k]
        o += k
        r0 = u[: laengen[0]]
        n, flaeche = newell(r0)
        if flaeche < 0.05:
            continue
        cls = SURF[art]
        # Wicklung nach außen: Dach nach oben, Wand vom Grundrissschwerpunkt weg
        if cls == ROOF and n[2] < 0:
            n = -n
        if cls == WALL and abs(n[2]) < 0.9:
            m = r0.mean(axis=0)
            if m[0] * n[0] + m[1] * n[1] < 0:
                n = -n
        try:
            t = _triangulate(u, laengen, n)
        except Exception:
            continue
        if len(t) == 0:
            continue
        p0, p1, p2 = u[t[:, 0]], u[t[:, 1]], u[t[:, 2]]
        dreh = np.cross(p1 - p0, p2 - p0) @ n < 0
        t[dreh] = t[dreh][:, [0, 2, 1]]
        vol += float(
            np.einsum("ij,ij->i", u[t[:, 0]], np.cross(u[t[:, 1]], u[t[:, 2]])).sum()
            / 6.0
        )
        if art == "WallSurface":
            wand += flaeche
        elif art == "RoofSurface":
            dach += flaeche
        kl = np.full(k, cls, np.uint8)
        pos.append(e)
        lic.append(licht(np.broadcast_to(n, (k, 3)), e[:, 2], kl))
        kla.append(kl)
        tri.append(t + nv)
        nv += k
        a = e[: laengen[0]]
        kan.append(np.hstack([a, np.roll(a, -1, axis=0)]))
    if not pos:
        return None
    mesh = Mesh(
        pos=np.vstack(pos),
        licht=np.concatenate(lic),
        klasse=np.concatenate(kla),
        dreiecke=np.vstack(tri),
        kanten=np.vstack(kan),
    )
    return mesh, _Kenn(wand=wand, dach=dach, volumen=abs(vol))


def packe(meshes: list[Mesh]) -> tuple[dict, list[int], list[int], str]:
    """Binärteil und Indizes aus Meshes (eines je Gebäude). Wirft SzeneZuGross."""
    if not meshes:
        raise KeineGebaeude("Keine Gebäude mit verwertbarer Geometrie gefunden")
    starts, nv = [0], 0
    idx = []
    for m in meshes:
        idx.append(m.dreiecke + nv)
        nv += len(m.pos)
        starts.append(nv)
    pos = np.round(np.vstack([m.pos for m in meshes]) * 10)
    kanten = [np.asarray(m.kanten, float).reshape(-1, 6) for m in meshes]
    e = np.round(np.vstack(kanten) * 10) if kanten else np.zeros((0, 6))
    if max(np.abs(pos).max(initial=0), np.abs(e).max(initial=0)) > 32767:
        raise SzeneZuGross(
            "Modell reicht weiter als 3,2 km vom Ursprung, Szenenformat zu klein"
        )
    pos = pos.astype("<i2")
    e = e.astype("<i2")
    eb = np.concatenate([np.full(len(k), b) for b, k in enumerate(kanten)]).astype(
        np.int64
    )
    if len(e):
        # doppelte Kanten (gemeinsame Kanten benachbarter Flächen) entfernen, Richtung egal
        a_, b_ = e[:, :3], e[:, 3:]
        a_zuerst = (
            (a_[:, 0] < b_[:, 0])
            | ((a_[:, 0] == b_[:, 0]) & (a_[:, 1] < b_[:, 1]))
            | ((a_[:, 0] == b_[:, 0]) & (a_[:, 1] == b_[:, 1]) & (a_[:, 2] <= b_[:, 2]))
        )[:, None]
        key = np.ascontiguousarray(
            np.hstack([np.where(a_zuerst, a_, b_), np.where(a_zuerst, b_, a_)])
        )
        _, uniq = np.unique(key, axis=0, return_index=True)
        uniq = np.sort(uniq)  # Kanten bleiben nach Gebäude geordnet
        e, eb = e[uniq], eb[uniq]
    edge_starts = np.concatenate(
        [[0], np.cumsum(np.bincount(eb, minlength=len(meshes)))]
    )
    counts = {
        "buildings": len(meshes),
        "vertices": int(len(pos)),
        "triangles": int(sum(len(i) for i in idx)),
        "edges": int(len(e)),
    }
    if (
        counts["buildings"] > MAX_GEBAEUDE
        or max(counts["vertices"], counts["triangles"], counts["edges"]) > MAX_ELEMENTE
    ):
        raise SzeneZuGross(f"Szene zu groß: {counts}")
    blob = b"".join(
        [
            pos.tobytes(),
            np.concatenate([m.licht for m in meshes]).astype("u1").tobytes(),
            np.concatenate([m.klasse for m in meshes]).astype("u1").tobytes(),
            np.vstack(idx).astype("<u4").tobytes(),
            e.tobytes(),
        ]
    )
    b64 = base64.b64encode(gzip.compress(blob, 9, mtime=0)).decode("ascii")
    if len(b64) > MAX_B64:
        raise SzeneZuGross(f"Szene zu groß: {len(b64)} Zeichen Base64")
    return counts, starts, [int(x) for x in edge_starts], b64


def herkunft_bereinigt(h: dict) -> dict:
    if h.get("art") not in ("lod2", "citygml", "ifc"):
        raise ValueError(f"herkunft.art ungültig: {h.get('art')!r}")
    return {
        "art": h["art"],
        "land": str(h["land"])[:3] if h.get("land") else None,
        "quelle": str(h.get("quelle") or "")[:300],
        "lizenz": str(h["lizenz"])[:120] if h.get("lizenz") else None,
        "abgerufen": str(h.get("abgerufen") or dt.date.today().isoformat()),
        "datei": str(h["datei"])[:200] if h.get("datei") else None,
    }


def szene_dict(
    *,
    herkunft: dict,
    origin,
    radius_m,
    packung,
    buildings: list[dict],
    ziel,
    hinweise: list[str],
) -> dict:
    counts, starts, edge_starts, b64 = packung
    return {
        "format": "vesta-szene/1",
        "herkunft": herkunft_bereinigt(herkunft),
        "origin": origin,
        "radius_m": radius_m,
        "counts": counts,
        "starts": starts,
        "edge_starts": edge_starts,
        "buildings": buildings,
        "ziel": ziel,
        "hinweis": " ".join(hinweise)[:300] or None,
        "bin_gz_b64": b64,
    }


def _r(x: float, stellen: int = 1) -> float:
    return round(float(x), stellen)


def baue_szene(
    dateien: list[Path],
    *,
    punkt: tuple[float, float] | None,
    epsg: int | None,
    radius_m: float | None,
    herkunft: dict,
) -> dict:
    """Szene aus CityGML-Dateien. `punkt` (Ost, Nord) und die Dateien liegen in `epsg`.

    Mit Punkt: Gebäude, deren Grundrissmitte im Radius liegt; Zielgebäude enthält den Punkt, sonst
    das nächste bis 30 m. Ohne Punkt: alle Gebäude (höchstens 5000), Ursprung in der Mitte der
    Bounding Box, Zielgebäude nur bei genau einem Gebäude. Ohne `epsg` lokale Koordinaten ohne
    Kartenbezug (`origin` = None).
    """
    pt = Point(punkt) if punkt is not None else None
    gebaeude, abgeschnitten = _lese([Path(d) for d in dateien], pt, radius_m)
    if not gebaeude:
        raise KeineGebaeude("Keine Gebäude mit verwertbarer Geometrie gefunden")
    hinweise: list[str] = []
    if abgeschnitten:
        hinweise.append(
            f"Die Datei enthält mehr als {MAX_OHNE_PUNKT} Gebäude, gezeigt sind die ersten {MAX_OHNE_PUNKT}."
        )

    if pt is not None:
        cx, cy = pt.x, pt.y
    else:
        b = np.array([g.fp.bounds for g in gebaeude])
        cx, cy = (b[:, 0].min() + b[:, 2].max()) / 2, (
            b[:, 1].min() + b[:, 3].max()
        ) / 2
    zentrum = Point(cx, cy)
    if epsg is not None:
        from pyproj import Transformer

        trafo = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
        lon0, lat0 = trafo.transform(cx, cy)
        kx = M_PER_DEG * math.cos(math.radians(lat0))
        origin = [round(float(lon0), 7), round(float(lat0), 7)]

        def lokal(v: np.ndarray, z0: float) -> np.ndarray:
            lon, lat = trafo.transform(v[:, 0], v[:, 1])
            return np.column_stack(
                [
                    (np.asarray(lon) - lon0) * kx,
                    (np.asarray(lat) - lat0) * M_PER_DEG,
                    v[:, 2] - z0,
                ]
            )

    else:
        origin = None

        def lokal(v: np.ndarray, z0: float) -> np.ndarray:
            return np.column_stack([v[:, 0] - cx, v[:, 1] - cy, v[:, 2] - z0])

    meshes = []
    for g in gebaeude:
        m = _mesh(g, lokal)
        if m is not None:
            meshes.append((g, *m))
    if not meshes:
        raise KeineGebaeude("Keine Gebäude mit verwertbarer Geometrie gefunden")

    ziel_i = None
    if pt is not None:
        drin = [i for i, (g, _, _) in enumerate(meshes) if g.fp.covers(pt)]
        if drin:
            ziel_i = min(drin, key=lambda i: meshes[i][0].fp.area)
        else:
            i = min(range(len(meshes)), key=lambda i: meshes[i][0].fp.distance(pt))
            if meshes[i][0].fp.distance(pt) <= ZIEL_MAX_M:
                ziel_i = i
        if ziel_i is None:
            hinweise.append(HINWEIS_KEIN_ZIEL)
    elif len(meshes) == 1:
        ziel_i = 0

    radius = radius_m
    auswahl = list(range(len(meshes)))
    while True:
        try:
            packung = packe([meshes[i][1] for i in auswahl])
            break
        except SzeneZuGross:
            if pt is None or radius is None or radius * 0.75 < MIN_RADIUS_M:
                raise
            radius = round(radius * 0.75)
            auswahl = [
                i
                for i in auswahl
                if i == ziel_i or meshes[i][0].fp.centroid.distance(pt) <= radius
            ]
            if not auswahl:
                raise
    if radius != radius_m:
        hinweise.append(
            f"Radius auf {radius:.0f} m verkleinert, damit die Szene klein genug bleibt."
        )

    buildings, ziel = [], None
    for i in auswahl:
        g, _, kenn = meshes[i]
        buildings.append(
            {
                "id": g.id,
                "h": _r(g.hoehe),
                "a": _r(g.fp.area),
                "fn": funktion_name(g.funktion),
                "d": _r(g.fp.distance(zentrum)),
                "ziel": i == ziel_i,
            }
        )
        if i == ziel_i:
            ziel = {
                "id": g.id,
                "hoehe_m": _r(g.hoehe, 2),
                "grundflaeche_m2": _r(g.fp.area),
                "wandflaeche_m2": _r(kenn.wand),
                "dachflaeche_m2": _r(kenn.dach),
                "volumen_m3": _r(kenn.volumen),
                "dachform": dachform_name(g.dachform),
                "funktion": funktion_name(g.funktion),
            }
    return szene_dict(
        herkunft=herkunft,
        origin=origin,
        radius_m=float(radius) if radius is not None else None,
        packung=packung,
        buildings=buildings,
        ziel=ziel,
        hinweise=hinweise,
    )
