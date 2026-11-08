"""Geokodierung, Größenprüfung, Download mit Cache und ZIP-Entpacken (ohne Netz)."""
from __future__ import annotations

import io
import json
import zipfile

import httpx
import pytest

import lod2_laden as ld

# Synthetische Adressen und Koordinaten, keine echten Orte.
ADRESSE = "Musterweg 1, 99999 Musterstadt"


@pytest.fixture(autouse=True)
def ohne_drossel(monkeypatch):
    monkeypatch.setattr(ld, "_MIN_ABSTAND_S", 0.0)


def _nominatim(eintraege: list[dict]):
    gesehen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        gesehen.append(request)
        return httpx.Response(200, json=eintraege)

    return httpx.Client(transport=httpx.MockTransport(handler)), gesehen


def _eintrag(lat, lon, state, iso=None, name="Musterweg 1, Musterstadt"):
    adr = {"state": state}
    if iso:
        adr["ISO3166-2-lvl4"] = iso
    return {"lat": str(lat), "lon": str(lon), "display_name": name, "address": adr}


def test_geocode_eindeutig():
    client, gesehen = _nominatim([_eintrag(48.1000, 11.5000, "Bayern", "DE-BY")])
    treffer = ld.geocode(ADRESSE, client=client)
    assert len(treffer) == 1
    t = ld.waehle_treffer(treffer)
    assert (t.lat, t.lon, t.bundesland) == (48.1, 11.5, "by")
    assert t.anzeige == "Musterweg 1, Musterstadt"
    req = gesehen[0]
    assert req.url.host == "nominatim.openstreetmap.org"
    p = req.url.params
    assert p["q"] == ADRESSE
    assert (p["format"], p["addressdetails"], p["countrycodes"], p["limit"]) == (
        "jsonv2",
        "1",
        "de",
        "3",
    )
    assert (
        req.headers["User-Agent"]
        == "vesta-foerder-check/1.1 (+https://vesta-consult.de)"
    )


@pytest.mark.parametrize(
    "state, iso, code",
    [
        ("Nordrhein-Westfalen", "DE-NW", "nrw"),
        ("Nordrhein-Westfalen", None, "nrw"),
        ("Thüringen", None, "th"),
        ("Berlin", "DE-BE", "be"),
        ("Atlantis", None, None),
    ],
)
def test_geocode_bundesland(state, iso, code):
    client, _ = _nominatim([_eintrag(50.0, 7.0, state, iso)])
    assert ld.geocode(ADRESSE, client=client)[0].bundesland == code


def test_geocode_leer_unklar():
    client, _ = _nominatim([])
    treffer = ld.geocode(ADRESSE, client=client)
    with pytest.raises(ld.UnklareAdresse) as e:
        ld.waehle_treffer(treffer)
    assert e.value.kandidaten == []


def test_geocode_weit_auseinander_unklar():
    # zwei Treffer rund 5 km auseinander: nicht raten
    client, _ = _nominatim(
        [_eintrag(48.1000, 11.5000, "Bayern"), _eintrag(48.1450, 11.5000, "Bayern")]
    )
    with pytest.raises(ld.UnklareAdresse) as e:
        ld.waehle_treffer(ld.geocode(ADRESSE, client=client))
    assert len(e.value.kandidaten) == 2


def test_geocode_nah_beieinander_eindeutig():
    # zwei Treffer rund 30 m auseinander gelten als dieselbe Stelle
    client, _ = _nominatim(
        [_eintrag(48.1000, 11.5000, "Bayern"), _eintrag(48.10027, 11.5000, "Bayern")]
    )
    t = ld.waehle_treffer(ld.geocode(ADRESSE, client=client))
    assert t.lat == 48.1


def test_nach_utm():
    e, n = ld.nach_utm(48.0, 9.0, 25832)
    assert abs(e - 500000.0) < 0.01
    e33, _ = ld.nach_utm(52.0, 15.0, 25833)
    assert abs(e33 - 500000.0) < 0.01


@pytest.fixture
def cache(tmp_path, monkeypatch):
    ordner = tmp_path / "cache"
    monkeypatch.setattr(ld, "cache_ordner", lambda: ordner)
    return ordner


def _zaehlender_client(antwort):
    aufrufe: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        aufrufe.append(request)
        return antwort(request)

    return httpx.Client(transport=httpx.MockTransport(handler)), aufrufe


def test_groesse_per_range_get():
    client, aufrufe = _zaehlender_client(
        lambda r: httpx.Response(
            206, headers={"Content-Range": "bytes 0-0/79592730"}, content=b"<"
        )
    )
    assert (
        ld.groesse("https://beispiel.invalid/a/566_5516.gml", client=client) == 79592730
    )
    assert aufrufe[0].method == "GET"
    assert aufrufe[0].headers["Range"] == "bytes=0-0"


def test_groesse_ohne_range_und_ohne_laenge():
    client, _ = _zaehlender_client(lambda r: httpx.Response(200, content=b""))
    assert ld.groesse("https://beispiel.invalid/x.zip", client=client) is None


def test_groesse_kachel_fehlt():
    client, _ = _zaehlender_client(lambda r: httpx.Response(404))
    with pytest.raises(ld.KachelFehlt):
        ld.groesse("https://beispiel.invalid/x.gml", client=client)


def test_lade_cache_zweiter_aufruf_ohne_request(cache):
    inhalt = b"<CityModel/>"
    client, aufrufe = _zaehlender_client(
        lambda r: httpx.Response(
            200, headers={"Content-Length": str(len(inhalt))}, content=inhalt
        )
    )
    url = "https://beispiel.invalid/lod2/citygml/566_5516.gml"
    p1 = ld.lade(url, client=client, max_bytes=1000)
    assert len(aufrufe) == 1
    assert [p.read_bytes() for p in p1] == [inhalt]
    assert ld.ist_im_cache(url)
    p2 = ld.lade(url, client=client, max_bytes=1000)
    assert len(aufrufe) == 1
    assert p1 == p2
    assert all(cache in p.parents for p in p1)


def test_lade_zu_gross(cache):
    client, _ = _zaehlender_client(
        lambda r: httpx.Response(
            200, headers={"Content-Length": "300"}, content=b"x" * 300
        )
    )
    with pytest.raises(ld.ZuGross) as e:
        ld.lade("https://beispiel.invalid/gross.gml", client=client, max_bytes=100)
    assert e.value.bytes == 300
    assert not any(p.is_file() for p in cache.rglob("*"))


def test_lade_zu_gross_ohne_content_length(cache):
    # Server ohne Längenangabe (MV, SH): Abbruch beim Streamen
    def strom():
        for _ in range(10):
            yield b"x" * 50

    client, _ = _zaehlender_client(lambda r: httpx.Response(200, content=strom()))
    with pytest.raises(ld.ZuGross):
        ld.lade("https://beispiel.invalid/gross.xml", client=client, max_bytes=100)
    assert not any(p.is_file() for p in cache.rglob("*"))


def _zip(eintraege: dict[str, bytes]) -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        for name, daten in eintraege.items():
            z.writestr(name, daten)
    return puffer.getvalue()


def test_lade_zip_entpackt_nur_gml(cache):
    daten = _zip(
        {
            "LoD2_32_513_5402_2_bw/LoD2_32_513_5402_1_BW.gml": b"<a/>",
            "LoD2_32_513_5402_2_bw/LoD2_32_514_5402_1_BW.gml": b"<b/>",
            "meta.html": b"<html/>",
            "liesmich.pdf": b"%PDF",
        }
    )
    client, _ = _zaehlender_client(lambda r: httpx.Response(200, content=daten))
    pfade = ld.lade(
        "https://beispiel.invalid/LoD2_32_513_5402_2_bw.zip",
        client=client,
        max_bytes=10_000,
    )
    assert sorted(p.name for p in pfade) == [
        "LoD2_32_513_5402_1_BW.gml",
        "LoD2_32_514_5402_1_BW.gml",
    ]
    assert all(p.is_file() and cache in p.parents for p in pfade)


def test_zip_traversal_abgewiesen(cache, tmp_path):
    daten = _zip({"../x.gml": b"<boese/>"})
    client, _ = _zaehlender_client(lambda r: httpx.Response(200, content=daten))
    with pytest.raises(ValueError):
        ld.lade("https://beispiel.invalid/boese.zip", client=client, max_bytes=10_000)
    assert not (tmp_path / "x.gml").exists()
    assert not list(tmp_path.rglob("x.gml"))


def test_entpacke_zip_absoluter_pfad_abgewiesen(tmp_path):
    zip_pfad = tmp_path / "a.zip"
    zip_pfad.write_bytes(_zip({"/etc/x.gml": b"<boese/>"}))
    with pytest.raises(ValueError):
        ld.entpacke_zip(zip_pfad, tmp_path / "ziel")


def test_sh_url_aus_index(cache):
    index = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "data_link": "https://beispiel.invalid/LoD2_32_600_6000_1_SH.xml"
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [600000, 6000000],
                            [601000, 6000000],
                            [601000, 6001000],
                            [600000, 6001000],
                            [600000, 6000000],
                        ]
                    ],
                },
            },
            {
                "type": "Feature",
                "properties": {
                    "data_link": "https://beispiel.invalid/LoD2_32_601_6000_1_SH.xml"
                },
                "geometry": {
                    "type": "MultiPolygon",
                    "coordinates": [
                        [
                            [
                                [601000, 6000000],
                                [602000, 6000000],
                                [602000, 6001000],
                                [601000, 6001000],
                                [601000, 6000000],
                            ]
                        ]
                    ],
                },
            },
        ],
    }
    client, aufrufe = _zaehlender_client(
        lambda r: httpx.Response(200, content=json.dumps(index).encode())
    )
    assert ld.sh_url_aus_index(600500, 6000500, client=client).endswith(
        "600_6000_1_SH.xml"
    )
    assert ld.sh_url_aus_index(601500, 6000500, client=client).endswith(
        "601_6000_1_SH.xml"
    )
    assert len(aufrufe) == 1  # Index nur einmal geladen
    with pytest.raises(ld.KachelFehlt):
        ld.sh_url_aus_index(700000, 6000500, client=client)


def test_http_client_prueft_tls():
    with ld.http_client() as c:
        assert c.headers["User-Agent"].startswith("vesta-foerder-check/")


def test_cache_ordner_plattform():
    p = ld.cache_ordner()
    # macOS ~/Library/Caches/vesta/lod2, Linux ~/.cache/vesta/lod2, Windows …\vesta\Cache\lod2
    assert p.name == "lod2" and "vesta" in p.parts


# --- TLS-Rückfall: System-Zertifikatsspeicher nicht nutzbar (z. B. Claude-Code-Sandbox) -------

class _TlsKaputt(httpx.BaseTransport):
    def handle_request(self, request):
        raise httpx.ConnectError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed (OSStatus -26276)",
            request=request,
        )


class _NetzWeg(httpx.BaseTransport):
    def handle_request(self, request):
        raise httpx.ConnectError("[Errno 8] nodename nor servname provided", request=request)


def test_tls_rueckfall_auf_certifi(capsys):
    t = ld._TlsRueckfall([_TlsKaputt(), _TlsKaputt(), httpx.MockTransport(lambda r: httpx.Response(200, text="ok"))])
    with httpx.Client(transport=t) as c:
        assert c.get("https://x.test/a").text == "ok"
        assert c.get("https://x.test/b").text == "ok"
    assert "certifi" in capsys.readouterr().err


def test_kein_rueckfall_bei_anderem_netzfehler():
    t = ld._TlsRueckfall([_NetzWeg(), httpx.MockTransport(lambda r: httpx.Response(200))])
    with httpx.Client(transport=t) as c, pytest.raises(httpx.ConnectError):
        c.get("https://x.test/")


def test_http_client_nutzt_rueckfall():
    with ld.http_client() as c:
        assert isinstance(c._transport, ld._TlsRueckfall)


def test_tls_kontexte_ueberspringt_unlesbares(monkeypatch):
    import certifi

    monkeypatch.setattr(certifi, "where", lambda: "/gibt/es/nicht/cacert.pem")
    kontexte = ld._tls_kontexte()
    assert len(kontexte) >= 1
    assert all(isinstance(k, __import__("ssl").SSLContext) for k in kontexte)


def test_alle_tls_quellen_scheitern_meldet_tls():
    t = ld._TlsRueckfall([_TlsKaputt(), _TlsKaputt()])
    with httpx.Client(transport=t) as c, pytest.raises(httpx.ConnectError, match="CERTIFICATE"):
        c.get("https://x.test/")


def test_proxy_aus_umgebung(monkeypatch):
    for k in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(k, raising=False)
    assert ld._proxy_aus_umgebung() is None
    monkeypatch.setenv("https_proxy", "http://proxy.test:3128")
    assert ld._proxy_aus_umgebung() == "http://proxy.test:3128"


def test_http_client_nutzt_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.test:3128")
    with ld.http_client() as c:
        pools = [type(t._pool).__name__ for t in c._transport._transporte]
    assert pools and all(p == "HTTPProxy" for p in pools)
