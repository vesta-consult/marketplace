"""Prüft eine Szene gegen das Format vesta-szene/1, so streng wie der Berater (extra = verboten)."""
from __future__ import annotations

import base64
import gzip
import json

import numpy as np

SCHLUESSEL = {
    "format",
    "herkunft",
    "origin",
    "radius_m",
    "counts",
    "starts",
    "edge_starts",
    "buildings",
    "ziel",
    "hinweis",
    "bin_gz_b64",
}
HERKUNFT = {"art", "land", "quelle", "lizenz", "abgerufen", "datei"}
GEBAEUDE = {"id", "h", "a", "fn", "d", "ziel"}
ZIEL = {
    "id",
    "hoehe_m",
    "grundflaeche_m2",
    "wandflaeche_m2",
    "dachflaeche_m2",
    "volumen_m3",
    "dachform",
    "funktion",
}


def pruefe_format(sz: dict) -> dict:
    """Prüft Schema und Binärteil, liefert die dekodierten Arrays."""
    json.dumps(sz)  # nur JSON-Typen, keine numpy-Werte
    assert set(sz) == SCHLUESSEL
    assert sz["format"] == "vesta-szene/1"
    h = sz["herkunft"]
    assert set(h) == HERKUNFT
    assert h["art"] in ("lod2", "citygml", "ifc")
    assert len(h["quelle"]) <= 300 and (h["lizenz"] is None or len(h["lizenz"]) <= 120)
    assert h["datei"] is None or len(h["datei"]) <= 200
    assert h["land"] is None or len(h["land"]) <= 3
    assert sz["hinweis"] is None or len(sz["hinweis"]) <= 300
    c = sz["counts"]
    assert (
        c["buildings"] <= 20_000
        and max(c["vertices"], c["triangles"], c["edges"]) <= 2_000_000
    )
    assert len(sz["buildings"]) == c["buildings"]
    for name, ende in (("starts", c["vertices"]), ("edge_starts", c["edges"])):
        s = sz[name]
        assert len(s) == c["buildings"] + 1 and s[0] == 0 and s[-1] == ende
        assert all(b >= a for a, b in zip(s, s[1:]))
    for b in sz["buildings"]:
        assert set(b) == GEBAEUDE and len(b["id"]) <= 80
    if sz["ziel"] is not None:
        assert set(sz["ziel"]) == ZIEL
    assert len(sz["bin_gz_b64"]) <= 8_000_000
    roh = gzip.decompress(base64.b64decode(sz["bin_gz_b64"], validate=True))
    v, t, e = c["vertices"], c["triangles"], c["edges"]
    assert len(roh) == 6 * v + 2 * v + 12 * t + 12 * e
    o = 0
    pos = np.frombuffer(roh, "<i2", 3 * v, o).reshape(-1, 3)
    o += 6 * v
    licht = np.frombuffer(roh, "u1", v, o)
    o += v
    klasse = np.frombuffer(roh, "u1", v, o)
    o += v
    dreiecke = np.frombuffer(roh, "<u4", 3 * t, o).reshape(-1, 3)
    o += 12 * t
    kanten = np.frombuffer(roh, "<i2", 6 * e, o).reshape(-1, 6)
    assert set(np.unique(klasse)) <= {1, 2}
    assert t == 0 or int(dreiecke.max()) < v
    return {
        "pos": pos,
        "licht": licht,
        "klasse": klasse,
        "dreiecke": dreiecke,
        "kanten": kanten,
    }
