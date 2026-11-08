#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
"""Vesta Förder-Check — externer A2A-Client (Plugin), Version 1.1.0.

Schickt ein Mandanten-Profil per A2A an den Vesta-Customer-Agent (Leistung
`customer.foerder_check`) und legt das Ergebnis als Dashboard im Projektordner ab.
Der Agent prüft den Rahmenvertrag (Token), rechnet die Empfehlung deterministisch
über den primär-verifizierten Kern und protokolliert den Aufruf (Abrechnung).

Optional gehen mit: eine 3D-Szene (vesta-szene/1, erzeugt von modell3d.py) und
Projekt-ID und -Name aus `<projektordner>/.vesta/foerder-check.json`. Unterlagen
und Adressen gehen nicht an Vesta.

Subcommands:
  card                 — Vesta-AgentCard (welche Leistungen/Skills) anzeigen
  empfehlung [flags]   — Profil senden → Empfehlung (JSON) + Dashboard (HTML)

Konfiguration via Env (wird aus ~/.config/vesta/foerder-check.env geladen):
  VESTA_A2A_URL        Default https://agents.vesta-consult.de/customer
  VESTA_CUSTOMER_TOKEN Rahmenvertrag-Token (Format vesta-frame-…)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

DEFAULT_A2A_URL = "https://agents.vesta-consult.de/customer"
SKILL_ID = "customer.foerder_check"
MAX_SZENE_B64 = 8_000_000
DASHBOARD_NAME = "foerder-check-dashboard.html"

ZIELGRUPPEN = [
    "privatperson",
    "wohnungsunternehmen",
    "kommune",
    "unternehmen",
    "wohnungseigentuemergemeinschaft",
    "contractor",
    "investor",
    "projektentwickler",
    "gemeinnuetzige_organisation",
]


def _load_env_file(path: Path) -> None:
    """Lädt eine KEY=VALUE-Datei in os.environ (ohne bestehende Werte zu überschreiben)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())


def _user_config_path() -> Path:
    """Nutzerweite Token-Ablage (vom /vesta-foerder-check:setup-Command geschrieben)."""
    return Path.home() / ".config" / "vesta" / "foerder-check.env"


def _config() -> tuple[str, str]:
    # Priorität: bereits gesetzte Env > Projekt-.env > ~/.config/vesta/foerder-check.env
    _load_env_file(Path.cwd() / ".env")
    _load_env_file(_user_config_path())
    url = os.environ.get("VESTA_A2A_URL", DEFAULT_A2A_URL).rstrip("/")
    token = os.environ.get("VESTA_CUSTOMER_TOKEN", "").strip()
    return url, token


# ── Profil, Projekt, Szene ────────────────────────────────────────────────────
def baue_profil(args: argparse.Namespace) -> dict[str, Any]:
    profil: dict[str, Any] = {
        "zielgruppe": args.zielgruppe,
        "assetklasse": args.assetklasse,
        "vorhaben_ebene": args.vorhaben_ebene,
        "gegenstand": [
            g.strip() for g in (args.gegenstand or "").split(",") if g.strip()
        ],
        "bundesland": args.bundesland,
    }
    if args.investitionssumme is not None:
        profil["investitionssumme_eur"] = float(args.investitionssumme)
    if args.anzahl_we is not None:
        profil["anzahl_we"] = int(args.anzahl_we)
    return profil


def _projekt_datei(ordner: Path) -> Path:
    return ordner / ".vesta" / "foerder-check.json"


def lade_oder_lege_projekt(ordner: Path, name: str | None) -> dict[str, Any]:
    """Liest die Projekt-ID aus dem Projektordner oder legt sie beim ersten Lauf an."""
    datei = _projekt_datei(ordner)
    projekt: dict[str, Any] | None = None
    if datei.exists():
        try:
            projekt = json.loads(datei.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            projekt = None
    if not projekt or not projekt.get("projekt_id"):
        projekt = {
            "projekt_id": str(uuid.uuid4()),
            "name": (name or ordner.resolve().name or "Projekt")[:120],
            "angelegt": _dt.datetime.now().isoformat(timespec="seconds"),
            "laeufe": [],
        }
    elif name:
        projekt["name"] = name[:120]
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text(
        json.dumps(projekt, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return projekt


def merke_lauf(ordner: Path, projekt: dict[str, Any], eintrag: dict[str, Any]) -> None:
    projekt.setdefault("laeufe", []).append(
        {"stand": _dt.datetime.now().isoformat(timespec="seconds"), **eintrag}
    )
    _projekt_datei(ordner).write_text(
        json.dumps(projekt, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def lade_szene(pfad: Path) -> dict[str, Any] | None:
    """Lädt eine Szene; zu große oder unlesbare Szenen werden nicht gesendet."""
    try:
        szene = json.loads(Path(pfad).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"[WARNUNG] Szene nicht lesbar ({exc}), Dashboard ohne 3D.", file=sys.stderr
        )
        return None
    try:
        json.dumps(szene, allow_nan=False)
    except ValueError:
        print("[WARNUNG] Szene ungültig (NaN oder Infinity), Dashboard ohne 3D.", file=sys.stderr)
        return None
    if len(str(szene.get("bin_gz_b64", ""))) > MAX_SZENE_B64:
        print(
            "[WARNUNG] Szene zu groß (über 8 MB), Dashboard ohne 3D. Radius verkleinern.",
            file=sys.stderr,
        )
        return None
    return szene


# ── A2A ───────────────────────────────────────────────────────────────────────
def _build_a2a_message(
    profil: dict[str, Any],
    *,
    szene: dict[str, Any] | None = None,
    projekt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {"skill": SKILL_ID, "profil": profil}
    if szene is not None:
        data["szene"] = szene
    if projekt is not None:
        data["projekt"] = projekt
    return {
        "message": {
            "message_id": str(uuid.uuid4()),
            "role": "ROLE_USER",
            "parts": [{"data": data, "media_type": "application/json"}],
        }
    }


def sende(url: str, token: str, envelope: dict[str, Any], *, transport: Any = None):
    import httpx

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "A2A-Version": "1.0",
    }
    with httpx.Client(
        timeout=httpx.Timeout(connect=10.0, read=180.0, write=60.0, pool=10.0),
        transport=transport,
    ) as client:
        return client.post(f"{url}/a2a/message:send", json=envelope, headers=headers)


def _extract_empfehlung(response: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    """Liest die A2A-Antwort aus (Artifact ``foerder_empfehlung``).

    Returns: (empfehlung-dict, dashboard-html, status-zeile).
    """
    task = response.get("task", response)
    state = (task.get("status") or {}).get("state")
    if state and state != "TASK_STATE_COMPLETED":
        msg = (task.get("status") or {}).get("message") or {}
        detail = ""
        for part in msg.get("parts") or []:
            if isinstance(part.get("text"), str):
                detail = part["text"]
                break
        raise RuntimeError(f"Vesta-Task nicht erfolgreich (state={state}): {detail}")
    artifacts = task.get("artifacts") or []
    if not artifacts:
        raise RuntimeError("Vesta-Antwort enthält kein Artifact.")
    data: dict[str, Any] = {}
    html = ""
    for part in artifacts[0].get("parts") or []:
        if isinstance(part.get("data"), dict) and not data:
            data = part["data"]
        if isinstance(part.get("text"), str) and not html:
            html = part["text"]
    if not data:
        raise RuntimeError("Kein DataPart im Vesta-Artifact.")
    status_line = ""
    msg = (task.get("status") or {}).get("message") or {}
    for part in msg.get("parts") or []:
        if isinstance(part.get("text"), str):
            status_line = part["text"]
            break
    return data, html, status_line


def cmd_card() -> int:
    import httpx

    url, _ = _config()
    print(f"Vesta-A2A-Endpoint: {url}\n")
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{url}/.well-known/agent-card.json")
            r.raise_for_status()
            card = r.json()
    except Exception as exc:  # noqa: BLE001
        print(f"[FEHLER] AgentCard nicht erreichbar: {exc}", file=sys.stderr)
        return 2
    print(f"Agent: {card.get('name')} — {card.get('description', '')[:120]}")
    print(f"Version: {card.get('version')}")
    print("\nLeistungen:")
    for s in card.get("skills") or []:
        print(f"  • {s.get('id')} — {s.get('name')}")
    print(
        "\nDiese Leistung: customer.foerder_check — Profilfelder: zielgruppe (Pflicht), "
        "assetklasse, vorhaben_ebene, gegenstand[], bundesland, investitionssumme_eur, anzahl_we."
    )
    return 0


def cmd_empfehlung(args: argparse.Namespace, *, transport: Any = None) -> int:
    import httpx

    url, token = _config()
    if not token:
        print(
            "[FEHLER] Kein VESTA_CUSTOMER_TOKEN gefunden. "
            "Führe zuerst /vesta-foerder-check:setup <token> aus.",
            file=sys.stderr,
        )
        return 2
    if not (args.zielgruppe or "").strip():
        print("[FEHLER] --zielgruppe ist Pflicht.", file=sys.stderr)
        return 1
    if args.zielgruppe not in ZIELGRUPPEN:
        print(
            f"[WARNUNG] zielgruppe {args.zielgruppe!r} ist kein bekannter Wert "
            f"({', '.join(ZIELGRUPPEN)}) — der Agent validiert streng (422 möglich).",
            file=sys.stderr,
        )

    ordner = Path(args.projektordner or Path.cwd())
    projekt = lade_oder_lege_projekt(ordner, args.projektname)
    szene = lade_szene(Path(args.szene)) if args.szene else None
    profil = baue_profil(args)
    projekt_kurz = {"id": projekt["projekt_id"], "name": projekt["name"]}
    # Die Förderprüfung hängt nie am 3D: Lehnt Vesta die Szene ab, einmal ohne Szene wiederholen.
    versuche = [szene, None] if szene is not None else [None]
    for i, sz in enumerate(versuche):
        envelope = _build_a2a_message(profil, szene=sz, projekt=projekt_kurz)
        letzter = i == len(versuche) - 1
        try:
            resp = sende(url, token, envelope, transport=transport)
        except httpx.HTTPError as exc:
            if not letzter:
                print(f"[WARNUNG] Übertragung mit 3D-Szene fehlgeschlagen ({exc}), neuer Versuch ohne 3D.", file=sys.stderr)
                continue
            print(f"[FEHLER] A2A-Request fehlgeschlagen: {exc}", file=sys.stderr)
            return 2
        if resp.status_code in (401, 403):
            print(
                f"[FEHLER] Auth abgelehnt (HTTP {resp.status_code}) — Token/Vertrag prüfen "
                "(ist customer.foerder_check in deinem Rahmenvertrag freigeschaltet?).",
                file=sys.stderr,
            )
            return 2
        if resp.status_code >= 400:
            if not letzter:
                print(f"[WARNUNG] Vesta lehnte die 3D-Szene ab (HTTP {resp.status_code}), neuer Versuch ohne 3D.", file=sys.stderr)
                continue
            print(f"[FEHLER] Vesta lehnte ab (HTTP {resp.status_code}): {resp.text[:500]}", file=sys.stderr)
            return 1
        try:
            empfehlung, dashboard_html, status_line = _extract_empfehlung(resp.json())
        except (RuntimeError, ValueError) as exc:
            if not letzter:
                print(f"[WARNUNG] Lauf mit 3D-Szene gescheitert ({exc}), neuer Versuch ohne 3D.", file=sys.stderr)
                continue
            print(f"[FEHLER] {exc}", file=sys.stderr)
            return 1
        szene = sz
        break

    if status_line:
        print(status_line)
    # Strukturierte Antwort (der aufrufende Agent fasst sie im Chat kurz zusammen).
    print(json.dumps(empfehlung, ensure_ascii=False, indent=2))
    haft = (empfehlung.get("haftungsausschluss") or {}).get("text")
    if haft:
        print("\n── Haftungsausschluss ──")
        print(haft)
    if dashboard_html:
        ziel = Path(args.dashboard) if args.dashboard else ordner / DASHBOARD_NAME
        if not ziel.is_absolute():
            ziel = Path.cwd() / ziel
        ziel.write_text(dashboard_html, encoding="utf-8")
        try:
            rel = str(ziel.relative_to(ordner.resolve()))
        except ValueError:
            rel = str(ziel)
        merke_lauf(
            ordner,
            projekt,
            {
                "dashboard": rel,
                "n_eligible": (empfehlung.get("anzahl") or {}).get("eligible"),
                "mit_3d": szene is not None,
            },
        )
        print(f"\nDashboard gespeichert: {ziel}")
        print(
            f"Projekt: {projekt['name']} ({projekt['projekt_id']}), Lauf {len(projekt['laeufe'])}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vesta Förder-Check A2A-Client")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("card", help="Vesta-AgentCard anzeigen")
    p = sub.add_parser("empfehlung", help="Profil senden → Empfehlung + Dashboard")
    p.add_argument("--zielgruppe", required=True)
    p.add_argument("--assetklasse", default="unspezifisch")
    p.add_argument("--vorhaben-ebene", dest="vorhaben_ebene", default="gebaeude")
    p.add_argument(
        "--gegenstand", default="", help="kommagetrennt, z.B. sanierung,heizung"
    )
    p.add_argument(
        "--bundesland", default=None, help="2-Buchstaben-Code (be, by, nrw …)"
    )
    p.add_argument(
        "--investitionssumme",
        type=float,
        default=None,
        help="ausdrücklich genannte Kosten des Vorhabens in Euro",
    )
    p.add_argument(
        "--anzahl-we",
        dest="anzahl_we",
        type=int,
        default=None,
        help="Anzahl Wohneinheiten",
    )
    p.add_argument(
        "--szene", default=None, help="3D-Szene aus modell3d.py (szene.json)"
    )
    p.add_argument(
        "--projektordner", default=None, help="Default: aktuelles Verzeichnis"
    )
    p.add_argument("--projektname", default=None)
    p.add_argument(
        "--dashboard",
        "--report",
        dest="dashboard",
        default=None,
        help=f"Zielpfad des Dashboards (Default: <projektordner>/{DASHBOARD_NAME})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "card":
        return cmd_card()
    if args.cmd == "empfehlung":
        return cmd_empfehlung(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
