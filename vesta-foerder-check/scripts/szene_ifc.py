"""Szene `vesta-szene/1` aus einer IFC-Datei (eigenes Modell aus den Unterlagen).

Dreiecke über `ifcopenshell.geom` in Weltkoordinaten, umgerechnet auf Meter. Die Georeferenz der IFC
wird in Version 1.1 nicht ausgewertet: Die Szene liegt in lokalen Koordinaten (`origin` = None), mit
der Mitte der Bounding Box im Ursprung und der Unterkante auf 0. Das ganze Modell ist ein Gebäude
und zugleich das Zielgebäude. Jedes Dreieck bekommt eigene Vertices (flache Schattierung), Kanten
sind Außenkanten und Knicke über 30 Grad.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np

from szene_citygml import ROOF, WALL, Mesh, licht, packe, szene_dict

AUSGESCHLOSSEN = ("IfcSpace", "IfcOpeningElement", "IfcSite", "IfcAnnotation")
KNICK_GRAD = 30.0


def _klasse(el) -> int:
    import ifcopenshell.util.element as ue

    if el.is_a("IfcRoof"):
        return ROOF
    if el.is_a("IfcSlab"):
        if ue.get_predefined_type(el) == "ROOF":
            return ROOF
        aggregat = ue.get_aggregate(el)
        if aggregat is not None and aggregat.is_a("IfcRoof"):
            return ROOF
    return WALL


def _kanten(v: np.ndarray, flaechen: np.ndarray, normalen: np.ndarray) -> np.ndarray:
    """Außenkanten und Knickkanten eines Dreiecksnetzes als (K,6)."""
    if len(flaechen) == 0:
        return np.zeros((0, 6))
    _, wid = np.unique(np.round(v * 1000).astype(np.int64), axis=0, return_inverse=True)
    w = wid.reshape(-1)[flaechen]
    paare = np.concatenate([w[:, [0, 1]], w[:, [1, 2]], w[:, [2, 0]]])
    ecken = np.concatenate(
        [flaechen[:, [0, 1]], flaechen[:, [1, 2]], flaechen[:, [2, 0]]]
    )
    dreieck = np.tile(np.arange(len(flaechen)), 3)
    paare.sort(axis=1)
    ordnung = np.lexsort((paare[:, 1], paare[:, 0]))
    paare, ecken, dreieck = paare[ordnung], ecken[ordnung], dreieck[ordnung]
    erster = np.flatnonzero(np.r_[True, np.any(paare[1:] != paare[:-1], axis=1)])
    anzahl = np.diff(np.r_[erster, len(paare)])
    behalten = anzahl != 2  # Rand (1) oder nicht-mannigfaltig (> 2)
    zwei = np.flatnonzero(anzahl == 2)
    i, j = dreieck[erster[zwei]], dreieck[erster[zwei] + 1]
    knick = np.einsum("ij,ij->i", normalen[i], normalen[j]) < math.cos(
        math.radians(KNICK_GRAD)
    )
    behalten[zwei[knick]] = True
    sel = erster[behalten]
    return np.hstack([v[ecken[sel, 0]], v[ecken[sel, 1]]])


def baue_szene_ifc(datei: Path, *, herkunft: dict) -> dict:
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.unit

    f = ifcopenshell.open(str(datei))
    skala = ifcopenshell.util.unit.calculate_unit_scale(f)
    produkte = [
        p
        for p in f.by_type("IfcProduct")
        if p.Representation is not None and not any(p.is_a(t) for t in AUSGESCHLOSSEN)
    ]
    teile: list[tuple[np.ndarray, np.ndarray, int]] = []
    if produkte:
        s = ifcopenshell.geom.settings()
        s.set("use-world-coords", True)
        s.set(
            "convert-back-units", True
        )  # Ausgabe in Dateieinheiten, Umrechnung hier mit skala
        it = ifcopenshell.geom.iterator(
            s, f, min(4, os.cpu_count() or 1), include=produkte
        )
        if it.initialize():
            while True:
                form = it.get()
                v = np.asarray(form.geometry.verts, dtype=float).reshape(-1, 3) * skala
                fl = np.asarray(form.geometry.faces, dtype=np.int64).reshape(-1, 3)
                if len(fl):
                    teile.append((v, fl, _klasse(f.by_id(form.id))))
                if not it.next():
                    break
    if not teile:
        raise ValueError("Die IFC-Datei enthält keine darstellbare Geometrie")

    alle = np.vstack([v for v, _, _ in teile])
    lo, hi = alle.min(axis=0), alle.max(axis=0)
    mitte = np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
    pos, lic, kla, tri, kan = [], [], [], [], []
    nv = 0
    for v, fl, cls in teile:
        v = v - mitte
        p = v[fl]
        n = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
        ln = np.linalg.norm(n, axis=1)
        ok = ln > 1e-9
        if not ok.any():
            continue
        p, n, fl = p[ok], n[ok] / ln[ok, None], fl[ok]
        flach = p.reshape(-1, 3)
        k = np.full(len(flach), cls, np.uint8)
        pos.append(flach)
        lic.append(licht(np.repeat(n, 3, axis=0), flach[:, 2], k))
        kla.append(k)
        tri.append(np.arange(len(flach)).reshape(-1, 3) + nv)
        nv += len(flach)
        kan.append(_kanten(v, fl, n))
    if not pos:
        raise ValueError("Die IFC-Datei enthält keine darstellbare Geometrie")
    mesh = Mesh(
        pos=np.vstack(pos),
        licht=np.concatenate(lic),
        klasse=np.concatenate(kla),
        dreiecke=np.vstack(tri),
        kanten=np.vstack(kan),
    )
    gebaeude = f.by_type("IfcBuilding")
    gid = str(gebaeude[0].GlobalId)[:80] if gebaeude else "IFC"
    hoehe = round(float(hi[2] - lo[2]), 2)
    return szene_dict(
        herkunft=herkunft,
        origin=None,
        radius_m=None,
        packung=packe([mesh]),
        buildings=[
            {
                "id": gid,
                "h": round(hoehe, 1),
                "a": None,
                "fn": None,
                "d": 0.0,
                "ziel": True,
            }
        ],
        ziel={
            "id": gid,
            "hoehe_m": hoehe,
            "grundflaeche_m2": None,
            "wandflaeche_m2": None,
            "dachflaeche_m2": None,
            "volumen_m3": None,
            "dachform": None,
            "funktion": None,
        },
        hinweise=[],
    )
