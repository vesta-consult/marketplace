"""Geokodierung (Nominatim) und Download der LoD2-Kacheln mit Nutzer-Cache.

Datenschutz: Die Adresse geht an OpenStreetMap Nominatim, die Kachelanfrage an den Download-Server
des Landes. An Vesta geht nichts von hier.

TLS läuft über den Zertifikatsspeicher des Betriebssystems (`truststore`), die Prüfung wird nie
abgeschaltet. Ob eine Kachel existiert und wie groß sie ist, prüft ein GET mit `Range: bytes=0-0`
(HEAD ist nicht überall verlässlich).
"""
from __future__ import annotations

import functools
import hashlib
import json
import math
import os
import re
import shutil
import ssl
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, urlsplit

import httpx

UA = "vesta-foerder-check/1.1 (+https://vesta-consult.de)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"
MAX_ABSTAND_M = 100.0  # Treffer, die weiter auseinanderliegen, gelten als unklar
MAX_ENTPACKT = 2 * 1024**3  # Obergrenze für die entpackten GML-Dateien eines ZIPs
SH_INDEX_TAGE = 7
_MIN_ABSTAND_S = 1.0  # Nominatim: höchstens eine Anfrage pro Sekunde
_letzte_anfrage = 0.0

_ISO = {
    "DE-BW": "bw",
    "DE-BY": "by",
    "DE-BE": "be",
    "DE-BB": "bb",
    "DE-HB": "hb",
    "DE-HH": "hh",
    "DE-HE": "he",
    "DE-MV": "mv",
    "DE-NI": "ni",
    "DE-NW": "nrw",
    "DE-RP": "rp",
    "DE-SL": "sl",
    "DE-SN": "sn",
    "DE-ST": "st",
    "DE-SH": "sh",
    "DE-TH": "th",
}
_NAMEN = {
    "baden-württemberg": "bw",
    "bayern": "by",
    "berlin": "be",
    "brandenburg": "bb",
    "bremen": "hb",
    "freie hansestadt bremen": "hb",
    "hamburg": "hh",
    "hessen": "he",
    "mecklenburg-vorpommern": "mv",
    "niedersachsen": "ni",
    "nordrhein-westfalen": "nrw",
    "rheinland-pfalz": "rp",
    "saarland": "sl",
    "sachsen": "sn",
    "sachsen-anhalt": "st",
    "schleswig-holstein": "sh",
    "thüringen": "th",
}


@dataclass(frozen=True)
class Treffer:
    lat: float
    lon: float
    bundesland: str | None
    anzeige: str


class UnklareAdresse(Exception):
    def __init__(self, kandidaten: list[Treffer]):
        super().__init__(f"Adresse nicht eindeutig ({len(kandidaten)} Treffer)")
        self.kandidaten = kandidaten


class ZuGross(Exception):
    def __init__(self, bytes: int):  # noqa: A002 (Name aus der Schnittstelle)
        super().__init__(f"Download zu groß: {bytes} Bytes")
        self.bytes = bytes


class KachelFehlt(Exception):
    """Für diese Stelle gibt es keine Kachel (404 oder nicht im Index)."""


def _ist_tls_fehler(exc: Exception) -> bool:
    text = str(exc).upper()
    return any(m in text for m in ("CERTIFICATE", "SSL", "OSSTATUS", "TLS"))


class _TlsRueckfall(httpx.BaseTransport):
    """Probiert Zertifikatsquellen der Reihe nach, bleibt bei der ersten, die funktioniert.

    Reihenfolge aus `_tls_kontexte()`: Zertifikatsspeicher des Systems (truststore), certifi-Bündel,
    `/etc/ssl/cert.pem`. Hintergrund: In abgeschotteten Umgebungen (etwa der Sandbox von Claude Code
    unter macOS) ist der Zertifikatsdienst des Systems gesperrt (OSStatus -26276) und teils auch das
    Lesen von .pem-Dateien. Die Prüfung wird nie abgeschaltet, nur die Quelle der Wurzeln wechselt.
    """

    def __init__(self, transporte: list[httpx.BaseTransport]) -> None:
        if not transporte:
            raise ValueError("Keine nutzbare Zertifikatsquelle für TLS gefunden.")
        self._transporte = list(transporte)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        while True:
            try:
                return self._transporte[0].handle_request(request)
            except httpx.ConnectError as exc:
                if not _ist_tls_fehler(exc) or len(self._transporte) == 1:
                    raise
                self._transporte.pop(0).close()
                print(
                    "[HINWEIS] Zertifikatsquelle nicht nutzbar, prüfe TLS mit der nächsten "
                    "(certifi bzw. System-Bündel).",
                    file=sys.stderr,
                )

    def close(self) -> None:
        for t in self._transporte:
            t.close()


def _tls_kontexte() -> list[ssl.SSLContext]:
    """Alle Zertifikatsquellen, die sich hier laden lassen, in fester Reihenfolge."""
    kandidaten = []

    def truststore_kontext() -> ssl.SSLContext:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    def certifi_kontext() -> ssl.SSLContext:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())

    def system_buendel() -> ssl.SSLContext:
        return ssl.create_default_context(cafile="/etc/ssl/cert.pem")

    for bauen in (truststore_kontext, certifi_kontext, system_buendel):
        try:
            kandidaten.append(bauen())
        except Exception:  # noqa: BLE001 - Quelle fehlt oder ist nicht lesbar
            continue
    return kandidaten


def _proxy_aus_umgebung() -> str | None:
    """HTTPS-Proxy aus der Umgebung. Ein eigener Transport übernimmt ihn nicht von selbst."""
    for k in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        wert = os.environ.get(k, "").strip()
        if wert:
            return wert
    return None


def http_client() -> httpx.Client:
    proxy = _proxy_aus_umgebung()
    transporte = [httpx.HTTPTransport(verify=k, proxy=proxy) for k in _tls_kontexte()]
    return httpx.Client(
        transport=_TlsRueckfall(transporte),
        timeout=httpx.Timeout(30.0, read=120.0),
        follow_redirects=True,
        headers={"User-Agent": UA},
    )


# --- Geokodierung ---------------------------------------------------------------------------


def _bundesland(adr: dict) -> str | None:
    code = _ISO.get(adr.get("ISO3166-2-lvl4", ""))
    if code:
        return code
    for feld in ("state", "city"):
        code = _NAMEN.get(str(adr.get(feld, "")).strip().lower())
        if code:
            return code
    return None


def geocode(adresse: str, *, client: httpx.Client) -> list[Treffer]:
    global _letzte_anfrage
    warte = _MIN_ABSTAND_S - (time.monotonic() - _letzte_anfrage)
    if warte > 0:
        time.sleep(warte)
    try:
        r = client.get(
            NOMINATIM,
            params={
                "q": adresse,
                "format": "jsonv2",
                "addressdetails": "1",
                "countrycodes": "de",
                "limit": "3",
            },
            headers={"User-Agent": UA},
        )
    finally:
        _letzte_anfrage = time.monotonic()
    r.raise_for_status()
    return [
        Treffer(
            lat=float(e["lat"]),
            lon=float(e["lon"]),
            bundesland=_bundesland(e.get("address") or {}),
            anzeige=str(e.get("display_name", ""))[:300],
        )
        for e in r.json()
    ]


def _abstand_m(a: Treffer, b: Treffer) -> float:
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(h))


def waehle_treffer(treffer: list[Treffer]) -> Treffer:
    """Erster Treffer, wenn alle Treffer an derselben Stelle liegen. Sonst nicht raten."""
    if not treffer:
        raise UnklareAdresse([])
    for i, a in enumerate(treffer):
        for b in treffer[i + 1 :]:
            if _abstand_m(a, b) > MAX_ABSTAND_M:
                raise UnklareAdresse(list(treffer))
    return treffer[0]


@functools.lru_cache(maxsize=4)
def _transformer(epsg: int):
    from pyproj import Transformer

    return Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)


def nach_utm(lat: float, lon: float, epsg: int) -> tuple[float, float]:
    e, n = _transformer(epsg).transform(lon, lat)
    return float(e), float(n)


# --- Cache und Download ---------------------------------------------------------------------


def cache_ordner() -> Path:
    import platformdirs

    return Path(platformdirs.user_cache_dir("vesta", appauthor=False)) / "lod2"


def _cache_name(url: str) -> str:
    teile = urlsplit(url)
    name = parse_qs(teile.query).get("file", [PurePosixPath(teile.path).name])[0]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120] or "kachel"
    return f"{hashlib.sha1(url.encode()).hexdigest()[:10]}-{name}"


def _entpackt_ordner(url: str) -> Path:
    return cache_ordner() / (_cache_name(url) + "_entpackt")


def ist_im_cache(url: str) -> bool:
    return (cache_ordner() / _cache_name(url)).is_file() or (
        _entpackt_ordner(url) / ".fertig"
    ).is_file()


def groesse(url: str, *, client: httpx.Client) -> int | None:
    """Größe der Datei in Bytes per GET auf das erste Byte, None wenn der Server sie nicht nennt."""
    with client.stream("GET", url, headers={"Range": "bytes=0-0"}) as r:
        if r.status_code in (404, 410):
            raise KachelFehlt(url)
        r.raise_for_status()
        if r.status_code == 206:
            gesamt = r.headers.get("Content-Range", "").rpartition("/")[2]
            return int(gesamt) if gesamt.isdigit() else None
        laenge = r.headers.get("Content-Length", "")
        return int(laenge) if laenge.isdigit() and int(laenge) > 0 else None


def _download(url: str, ziel: Path, *, client: httpx.Client, max_bytes: int) -> None:
    teil = ziel.with_name(ziel.name + ".part")
    try:
        with client.stream("GET", url) as r:
            if r.status_code in (404, 410):
                raise KachelFehlt(url)
            r.raise_for_status()
            laenge = r.headers.get("Content-Length", "")
            if laenge.isdigit() and int(laenge) > max_bytes:
                raise ZuGross(int(laenge))
            n = 0
            with teil.open("wb") as fh:
                for stueck in r.iter_bytes(1 << 20):
                    n += len(stueck)
                    if n > max_bytes:
                        raise ZuGross(n)
                    fh.write(stueck)
        teil.replace(ziel)
    finally:
        teil.unlink(missing_ok=True)


def entpacke_zip(zip_pfad: Path, ziel: Path) -> list[Path]:
    """Entpackt nur .gml und .xml. Absolute Pfade und `..` werden abgewiesen (ValueError)."""
    basis = ziel.resolve()
    with zipfile.ZipFile(zip_pfad) as z:
        auswahl = []
        for info in z.infolist():
            teile = PurePosixPath(info.filename.replace("\\", "/"))
            if (
                teile.is_absolute()
                or ".." in teile.parts
                or (teile.parts and ":" in teile.parts[0])
            ):
                raise ValueError(f"unsicherer Pfad im ZIP: {info.filename!r}")
            if not info.is_dir() and teile.suffix.lower() in (".gml", ".xml"):
                auswahl.append((info, basis.joinpath(*teile.parts)))
        if sum(i.file_size for i, _ in auswahl) > MAX_ENTPACKT:
            raise ValueError("ZIP entpackt zu groß")
        for info, aus in auswahl:
            if basis not in aus.resolve().parents:
                raise ValueError(f"unsicherer Pfad im ZIP: {info.filename!r}")
        for info, aus in auswahl:
            aus.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as quelle, aus.open("wb") as senke:
                shutil.copyfileobj(quelle, senke, 1 << 20)
    return sorted(aus for _, aus in auswahl)


def lade(url: str, *, client: httpx.Client, max_bytes: int) -> list[Path]:
    """Lädt eine Kachel in den Cache (oder nimmt die vorhandene) und liefert die GML-Pfade."""
    ordner = cache_ordner()
    entpackt = _entpackt_ordner(url)
    if (entpackt / ".fertig").is_file():
        return sorted(
            p for p in entpackt.rglob("*") if p.suffix.lower() in (".gml", ".xml")
        )
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / _cache_name(url)
    if not datei.is_file():
        _download(url, datei, client=client, max_bytes=max_bytes)
    if not zipfile.is_zipfile(datei):
        return [datei]
    try:
        pfade = entpacke_zip(datei, entpackt)
    except Exception:
        shutil.rmtree(entpackt, ignore_errors=True)
        raise
    finally:
        datei.unlink(missing_ok=True)
    (entpackt / ".fertig").write_text("ok")
    return pfade


# --- Schleswig-Holstein: Kachel-URL aus dem GeoJSON-Index -----------------------------------


@functools.lru_cache(maxsize=2)
def _sh_index(
    pfad: str, mtime: float
) -> list[tuple[tuple[float, float, float, float], list, str]]:
    daten = json.loads(Path(pfad).read_text(encoding="utf-8"))
    eintraege = []
    for f in daten.get("features", []):
        g, link = f.get("geometry") or {}, (f.get("properties") or {}).get("data_link")
        if not link:
            continue
        polys = {
            "Polygon": [g.get("coordinates")],
            "MultiPolygon": g.get("coordinates"),
        }.get(g.get("type"), [])
        for poly in polys or []:
            ring = poly[0]
            xs, ys = [p[0] for p in ring], [p[1] for p in ring]
            eintraege.append(((min(xs), min(ys), max(xs), max(ys)), ring, link))
    return eintraege


def _im_ring(x: float, y: float, ring: list) -> bool:
    drin = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            drin = not drin
    return drin


def sh_url_aus_index(e: float, n: float, *, client: httpx.Client) -> str:
    """URL der SH-Kachel am Punkt (EPSG:25832) aus dem Index; der Index wird gecacht."""
    from lod2_laender import LAENDER

    pfad = cache_ordner() / "sh_index.geojson"
    if not pfad.is_file() or time.time() - pfad.stat().st_mtime > SH_INDEX_TAGE * 86400:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.unlink(missing_ok=True)
        _download(LAENDER["sh"].url, pfad, client=client, max_bytes=100 * 1024**2)
    for (x0, y0, x1, y1), ring, link in _sh_index(str(pfad), pfad.stat().st_mtime):
        if x0 <= e <= x1 and y0 <= n <= y1 and _im_ring(e, n, [p[:2] for p in ring]):
            return link
    raise KachelFehlt(f"sh {e:.0f}/{n:.0f}")
