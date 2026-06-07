#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx>=0.27"]
# ///
"""Vesta Quick-Check — externer A2A-Client.

Subcommands:
  card                 — Vesta-AgentCard + benötigtes Eingabe-Schema anzeigen
  validate <akte.json> — Akte lokal gegen das Vesta-Pflichtschema prüfen
  request-lca <akte.json> — Akte per A2A an den Vesta-customer-Agent senden

Konfiguration via Env (.env wird automatisch geladen, falls vorhanden):
  VESTA_A2A_URL       Default https://a2a.zukunftimmobilie.de/customer
  VESTA_CUSTOMER_TOKEN  Rahmenvertrag-Token
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

# Pflichtschema, gespiegelt aus agents/external_employee/agent_negotiation.py:VESTA_SCHEMA.
# (Discovery via `card` zeigt das Live-AgentCard zusätzlich.)
REQUIRED_FIELDS = [
    "nfa_m2 (Netto-Nutzfläche, m²)",
    "rsp_years (Referenz-Studien-Periode, a)",
    "components[].name (Bauteil-Bezeichnung)",
    "components[].area_m2 (Bauteilfläche, m²)",
    "components[].layers[].material (Material-Match-String)",
    "components[].layers[].quantity (Schichtdicke, m)",
    "operational[].energy_carrier (Energieträger-Key)",
    "operational[].annual_kwh_per_m2 (Endenergie, kWh/m²·a)",
    "operational[].purpose (heating/electricity/cooling)",
]


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def validate_payload(payload: dict[str, Any]) -> list[str]:
    """Prüft den Vesta-Payload gegen die Pflichtfelder.

    Returns: Liste konkreter Lücken-Beschreibungen (leer = vollständig).
    """
    gaps: list[str] = []

    if not _is_number(payload.get("nfa_m2")) or payload.get("nfa_m2", 0) <= 0:
        gaps.append("nfa_m2 fehlt oder ≤ 0 (Netto-Nutzfläche in m²)")
    if not _is_number(payload.get("rsp_years")) or payload.get("rsp_years", 0) <= 0:
        gaps.append("rsp_years fehlt oder ≤ 0 (Referenz-Studien-Periode in a)")

    components = payload.get("components")
    if not isinstance(components, list) or not components:
        gaps.append("components fehlt oder ist leer (mindestens ein Bauteil nötig)")
    else:
        for i, comp in enumerate(components):
            if not str(comp.get("name") or "").strip():
                gaps.append(f"components[{i}].name fehlt (Bauteil-Bezeichnung)")
            if not _is_number(comp.get("area_m2")) or comp.get("area_m2", 0) <= 0:
                gaps.append(f"components[{i}].area_m2 fehlt oder ≤ 0")
            layers = comp.get("layers")
            if not isinstance(layers, list) or not layers:
                gaps.append(f"components[{i}].layers fehlt oder leer")
                continue
            for j, layer in enumerate(layers):
                if not str(layer.get("material") or "").strip():
                    gaps.append(
                        f"components[{i}].layers[{j}].material fehlt "
                        f"(Material-Bezeichnung für Bauteil {comp.get('name', i)!r})"
                    )
                if (
                    not _is_number(layer.get("quantity"))
                    or layer.get("quantity", 0) <= 0
                ):
                    gaps.append(
                        f"components[{i}].layers[{j}].quantity fehlt oder ≤ 0 (Schichtdicke in m)"
                    )

    operational = payload.get("operational")
    if not isinstance(operational, list) or not operational:
        gaps.append(
            "operational fehlt oder leer — Betriebsenergie aus Energiekonzept/-doc nötig "
            "(energy_carrier, annual_kwh_per_m2, purpose)"
        )
    else:
        for k, op in enumerate(operational):
            if not str(op.get("energy_carrier") or "").strip():
                gaps.append(f"operational[{k}].energy_carrier fehlt")
            if not _is_number(op.get("annual_kwh_per_m2")):
                gaps.append(f"operational[{k}].annual_kwh_per_m2 fehlt (kWh/m²·a)")
            if not str(op.get("purpose") or "").strip():
                gaps.append(
                    f"operational[{k}].purpose fehlt (heating/electricity/cooling)"
                )

    return gaps


# ---------------------------------------------------------------------------
# A2A-Brücke (spiegelt agents/external_employee/server.py)
# ---------------------------------------------------------------------------


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
    """Nutzerweite Token-Ablage (vom /vesta-quick-check:setup-Command geschrieben)."""
    return Path.home() / ".config" / "vesta" / "quick-check.env"


def _config() -> tuple[str, str]:
    # Priorität: bereits gesetzte Env > Projekt-.env > ~/.config/vesta/quick-check.env
    _load_env_file(Path.cwd() / ".env")
    _load_env_file(_user_config_path())
    url = os.environ.get("VESTA_A2A_URL", DEFAULT_A2A_URL).rstrip("/")
    token = os.environ.get("VESTA_CUSTOMER_TOKEN", "").strip()
    return url, token


def _build_a2a_message(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "message": {
            "message_id": str(uuid.uuid4()),
            "role": "ROLE_USER",
            "parts": [{"data": {"payload": payload}, "media_type": "application/json"}],
        }
    }


def _extract_summary(response: dict[str, Any]) -> tuple[dict[str, Any], str, str]:
    """Liest die A2A-Antwort aus.

    Die Vesta-Antwort ist in ein ``{"task": {...}}``-Objekt gewrappt; das
    Ergebnis-Artifact ``lca_summary`` trägt einen DataPart mit ``building``.
    Returns: (summary-dict, report-html, status-zeile).
    """
    task = response.get("task", response)
    artifacts = task.get("artifacts") or []
    if not artifacts:
        raise RuntimeError("Vesta-Antwort enthält kein Artifact.")
    summary: dict[str, Any] = {}
    html = ""
    for part in artifacts[0].get("parts") or []:
        if isinstance(part.get("data"), dict):
            summary = part["data"]
        if isinstance(part.get("text"), str) and not html:
            html = part["text"]
    if not summary:
        raise RuntimeError("Kein DataPart im Vesta-Artifact.")
    status_line = ""
    msg = (task.get("status") or {}).get("message") or {}
    for part in msg.get("parts") or []:
        if isinstance(part.get("text"), str):
            status_line = part["text"]
            break
    return summary, html, status_line


def _kennwert_from_summary(summary: dict[str, Any]) -> float | None:
    """Liest den GWP-Kennwert (kg CO₂-eq/m²·a) defensiv aus dem Summary."""
    building = (
        summary.get("building")
        if isinstance(summary.get("building"), dict)
        else summary
    )
    for key in ("kennwert", "gwp_per_m2_nfa_per_year"):
        val = building.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return None


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
    print("\nBenötigte Pflichtfelder (Akte → Vesta-Payload):")
    for f in REQUIRED_FIELDS:
        print(f"  • {f}")
    print(
        "\nHinweis: Material-Strings müssen ÖkobauDat-matchbar sein "
        "(z.B. 'Beton C25/30', 'EPS-Hartschaum'). quantity = Schichtdicke in m."
    )
    return 0


def cmd_validate(akte_path: str) -> int:
    payload = json.loads(Path(akte_path).read_text(encoding="utf-8"))
    gaps = validate_payload(payload)
    if not gaps:
        print("[OK] Akte vollständig — bereit für request-lca.")
        return 0
    print("[UNVOLLSTÄNDIG] Bitte folgende Felder ergänzen:", file=sys.stderr)
    for g in gaps:
        print(f"  ✗ {g}", file=sys.stderr)
    return 1


def cmd_request_lca(akte_path: str) -> int:
    import httpx

    url, token = _config()
    if not token:
        print(
            "[FEHLER] Kein VESTA_CUSTOMER_TOKEN gefunden. "
            "Führe zuerst /vesta-quick-check:setup <token> aus.",
            file=sys.stderr,
        )
        return 2

    payload = json.loads(Path(akte_path).read_text(encoding="utf-8"))
    gaps = validate_payload(payload)
    if gaps:
        print("[ABBRUCH] Akte unvollständig — NICHT gesendet. Lücken:", file=sys.stderr)
        for g in gaps:
            print(f"  ✗ {g}", file=sys.stderr)
        return 1

    envelope = _build_a2a_message(payload)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "A2A-Version": "1.0",
    }
    try:
        with httpx.Client(
            timeout=httpx.Timeout(connect=10.0, read=240.0, write=30.0, pool=10.0)
        ) as client:
            resp = client.post(
                f"{url}/a2a/message:send", json=envelope, headers=headers
            )
    except httpx.HTTPError as exc:
        print(f"[FEHLER] A2A-Request fehlgeschlagen: {exc}", file=sys.stderr)
        return 2
    if resp.status_code in (401, 403):
        print(
            f"[FEHLER] Auth abgelehnt (HTTP {resp.status_code}) — Token/Vertrag prüfen.",
            file=sys.stderr,
        )
        return 2
    if resp.status_code >= 400:
        print(
            f"[FEHLER] Vesta lehnte ab (HTTP {resp.status_code}): {resp.text[:500]}",
            file=sys.stderr,
        )
        return 1

    summary, html, status_line = _extract_summary(resp.json())
    kennwert = _kennwert_from_summary(summary)
    print("=== Vesta LCA Quick-Check Ergebnis ===")
    if status_line:
        print(status_line)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if kennwert is not None:
        print(f"\nKennwert: {kennwert:.2f} kg CO₂-eq/(m²·a)")
    if html:
        out = Path(akte_path).with_suffix(".report.html")
        out.write_text(html, encoding="utf-8")
        print(f"Report gespeichert: {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vesta Quick-Check A2A-Client")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("card", help="Vesta-AgentCard + Pflichtschema anzeigen")
    p_val = sub.add_parser("validate", help="Akte lokal validieren")
    p_val.add_argument("akte")
    p_req = sub.add_parser("request-lca", help="Akte per A2A senden")
    p_req.add_argument("akte")
    args = parser.parse_args(argv)
    if args.cmd == "card":
        return cmd_card()
    if args.cmd == "validate":
        return cmd_validate(args.akte)
    if args.cmd == "request-lca":
        return cmd_request_lca(args.akte)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
