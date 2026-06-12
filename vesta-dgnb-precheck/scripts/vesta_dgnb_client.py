#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
"""Vesta DGNB-Pre-Check — externer A2A-Client (Plugin).

Schickt eine Vorprüf-Anfrage (Nutzungsprofil + angestrebte DGNB-Stufe + optionale
Punkte-Einschätzung je Kriterium) per A2A an den Vesta-Customer-Agent (Leistung
``customer.dgnb_precheck``) und gibt die Bewertung zurück: gewichteter
Erfüllungsgrad, erreichte Stufe, ob das Ziel erreichbar ist, und ein nach
Erfüllungsgrad-Gewinn priorisierter Maßnahmenkatalog. Der Agent prüft den
Rahmenvertrag (Token), rechnet die Bewertung deterministisch über den
sign-off-verifizierten Kriterienkern und protokolliert den Aufruf (Abrechnung).

Subcommands:
  card                 — Vesta-AgentCard (welche Leistungen/Skills) anzeigen
  bewerten [flags]     — Anfrage senden → Bewertung (JSON)

Konfiguration via Env (wird aus ~/.config/vesta/dgnb-precheck.env geladen):
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
SKILL_ID = "customer.dgnb_precheck"

ZIEL_STUFEN = ["silber", "gold", "platin"]


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
    """Nutzerweite Token-Ablage (vom /vesta-dgnb-precheck:setup-Command geschrieben)."""
    return Path.home() / ".config" / "vesta" / "dgnb-precheck.env"


def _config() -> tuple[str, str]:
    # Priorität: bereits gesetzte Env > Projekt-.env > ~/.config/vesta/dgnb-precheck.env
    _load_env_file(Path.cwd() / ".env")
    _load_env_file(_user_config_path())
    url = os.environ.get("VESTA_A2A_URL", DEFAULT_A2A_URL).rstrip("/")
    token = os.environ.get("VESTA_CUSTOMER_TOKEN", "").strip()
    return url, token


def _build_a2a_message(anfrage: dict[str, Any]) -> dict[str, Any]:
    return {
        "message": {
            "message_id": str(uuid.uuid4()),
            "role": "ROLE_USER",
            "parts": [
                {
                    "data": {"skill": SKILL_ID, **anfrage},
                    "media_type": "application/json",
                }
            ],
        }
    }


def _extract_bewertung(response: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    """Liest die A2A-Antwort aus (Artifact ``dgnb_bewertung``).

    Returns: (bewertung-dict, report-html, status-zeile). Der DataPart trägt die
    strukturierte Bewertung, ein optionaler text/html-Part das Dokument.
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
    skills = card.get("skills") or []
    print("\nLeistungen:")
    for s in skills:
        print(f"  • {s.get('id')} — {s.get('name')}")
    print(
        "\nDiese Leistung: customer.dgnb_precheck — Felder: profil (Nutzungsprofil), "
        "ziel_stufe (silber|gold|platin, Pflicht), scores (optional: Punkte 0–100 je Kriterium)."
    )
    return 0


def cmd_bewerten(args: argparse.Namespace) -> int:
    import httpx

    url, token = _config()
    if not token:
        print(
            "[FEHLER] Kein VESTA_CUSTOMER_TOKEN gefunden. "
            "Führe zuerst /vesta-dgnb-precheck:setup <token> aus.",
            file=sys.stderr,
        )
        return 2

    if args.ziel_stufe not in ZIEL_STUFEN:
        print(
            f"[FEHLER] --ziel-stufe muss eine von {', '.join(ZIEL_STUFEN)} sein "
            f"(war: {args.ziel_stufe!r}).",
            file=sys.stderr,
        )
        return 1

    scores: dict[str, Any] = {}
    if args.scores:
        try:
            scores = json.loads(args.scores)
        except json.JSONDecodeError as exc:
            print(f"[FEHLER] --scores ist kein gültiges JSON: {exc}", file=sys.stderr)
            return 1
        if not isinstance(scores, dict):
            print(
                '[FEHLER] --scores muss ein JSON-Objekt {"kriterium_id": punkte} sein.',
                file=sys.stderr,
            )
            return 1

    anfrage = {
        "profil": args.profil,
        "ziel_stufe": args.ziel_stufe,
        "scores": scores,
    }

    envelope = _build_a2a_message(anfrage)
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
            "(ist customer.dgnb_precheck in deinem Rahmenvertrag freigeschaltet?).",
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
        bewertung, report_html, status_line = _extract_bewertung(resp.json())
    except RuntimeError as exc:
        print(f"[FEHLER] {exc}", file=sys.stderr)
        return 1

    if status_line:
        print(status_line)
    # Strukturierte Antwort (der aufrufende Agent bereitet sie sprachlich auf).
    print(json.dumps(bewertung, ensure_ascii=False, indent=2))
    haft = (bewertung.get("haftungsausschluss") or {}).get("text")
    if haft:
        print("\n── Haftungsausschluss ──")
        print(haft)
    if report_html:
        out = Path(args.report or "dgnb-precheck-report.html")
        out.write_text(report_html, encoding="utf-8")
        print(f"\nZusammenfassung als Dokument gespeichert: {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vesta DGNB-Pre-Check A2A-Client")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("card", help="Vesta-AgentCard anzeigen")
    p = sub.add_parser("bewerten", help="Anfrage senden → DGNB-Bewertung")
    p.add_argument(
        "--profil",
        default="wohngebaeude",
        help="Nutzungsprofil (Default: wohngebaeude)",
    )
    p.add_argument(
        "--ziel-stufe",
        dest="ziel_stufe",
        required=True,
        help="angestrebte DGNB-Stufe: silber | gold | platin",
    )
    p.add_argument(
        "--scores",
        default="",
        help="optionale Punkte-Einschätzung je Kriterium als JSON, z.B. '{\"env1.1\": 70}'",
    )
    p.add_argument(
        "--report",
        default=None,
        help="Zielpfad für ein HTML-Dokument (falls der Agent eines liefert)",
    )
    args = parser.parse_args(argv)
    if args.cmd == "card":
        return cmd_card()
    if args.cmd == "bewerten":
        return cmd_bewerten(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
