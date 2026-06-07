#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
"""Vesta Förder-Check — externer A2A-Client (Plugin).

Schickt ein Mandanten-Profil per A2A an den Vesta-Customer-Agent (Leistung
`customer.foerder_check`) und gibt die Förderempfehlung zurück. Der Agent prüft
den Rahmenvertrag (Token), rechnet die Empfehlung deterministisch über den
primär-verifizierten Kern und protokolliert den Aufruf (Abrechnung).

Subcommands:
  card                 — Vesta-AgentCard (welche Leistungen/Skills) anzeigen
  empfehlung [flags]   — Profil senden → Förderempfehlung (JSON)

Konfiguration via Env (wird aus ~/.config/vesta/foerder-check.env geladen):
  VESTA_A2A_URL        Default https://a2a.zukunftimmobilie.de/customer
  VESTA_CUSTOMER_TOKEN Rahmenvertrag-Token (Format vesta-frame-…)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

DEFAULT_A2A_URL = "https://a2a.zukunftimmobilie.de/customer"
SKILL_ID = "customer.foerder_check"

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


def _build_a2a_message(profil: dict[str, Any]) -> dict[str, Any]:
    return {
        "message": {
            "message_id": str(uuid.uuid4()),
            "role": "ROLE_USER",
            "parts": [
                {
                    "data": {"skill": SKILL_ID, "profil": profil},
                    "media_type": "application/json",
                }
            ],
        }
    }


def _extract_empfehlung(response: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    """Liest die A2A-Antwort aus (Artifact ``foerder_empfehlung``).

    Returns: (empfehlung-dict, report-html, status-zeile). Der DataPart trägt die
    strukturierte Empfehlung, der text/html-Part das zusammenfassende Dokument.
    """
    task = response.get("task", response)
    state = (task.get("status") or {}).get("state")
    if state and state != "TASK_STATE_COMPLETED":
        # Fehlertext aus der Status-Message ziehen, falls vorhanden
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
    skills = card.get("skills") or []
    print("\nLeistungen:")
    for s in skills:
        print(f"  • {s.get('id')} — {s.get('name')}")
    print(
        "\nDiese Leistung: customer.foerder_check — Profilfelder: zielgruppe (Pflicht), "
        "assetklasse, vorhaben_ebene, gegenstand[], bundesland."
    )
    return 0


def cmd_empfehlung(args: argparse.Namespace) -> int:
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

    profil = {
        "zielgruppe": args.zielgruppe,
        "assetklasse": args.assetklasse,
        "vorhaben_ebene": args.vorhaben_ebene,
        "gegenstand": [
            g.strip() for g in (args.gegenstand or "").split(",") if g.strip()
        ],
        "bundesland": args.bundesland,
    }

    envelope = _build_a2a_message(profil)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "A2A-Version": "1.0",
    }
    try:
        with httpx.Client(
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0)
        ) as client:
            resp = client.post(
                f"{url}/a2a/message:send", json=envelope, headers=headers
            )
    except httpx.HTTPError as exc:
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
        print(
            f"[FEHLER] Vesta lehnte ab (HTTP {resp.status_code}): {resp.text[:500]}",
            file=sys.stderr,
        )
        return 1

    try:
        empfehlung, report_html, status_line = _extract_empfehlung(resp.json())
    except RuntimeError as exc:
        print(f"[FEHLER] {exc}", file=sys.stderr)
        return 1

    if status_line:
        print(status_line)
    # Strukturierte Antwort (der aufrufende Agent bereitet sie sprachlich auf).
    print(json.dumps(empfehlung, ensure_ascii=False, indent=2))
    haft = (empfehlung.get("haftungsausschluss") or {}).get("text")
    if haft:
        print("\n── Haftungsausschluss ──")
        print(haft)
    # Zusammenfassendes Dokument ablegen (vom Vesta-Agenten erzeugt, mit Haftungsausschluss).
    if report_html:
        out = Path(args.report or "foerder-check-report.html")
        out.write_text(report_html, encoding="utf-8")
        print(f"\nZusammenfassung als Dokument gespeichert: {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vesta Förder-Check A2A-Client")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("card", help="Vesta-AgentCard anzeigen")
    p = sub.add_parser("empfehlung", help="Profil senden → Förderempfehlung")
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
        "--report",
        default=None,
        help="Zielpfad für das HTML-Dokument (Default: foerder-check-report.html)",
    )
    args = parser.parse_args(argv)
    if args.cmd == "card":
        return cmd_card()
    if args.cmd == "empfehlung":
        return cmd_empfehlung(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
