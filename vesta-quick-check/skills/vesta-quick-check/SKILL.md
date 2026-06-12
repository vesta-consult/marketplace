---
name: vesta-quick-check
description: Löst den Vesta LCA Quick-Check aus. Trigger wenn der Nutzer "Vesta-Quick-Check", "LCA-Check", "Ökobilanz an Vesta schicken" o.ä. sagt und im Projektordner IFC-Modelle und/oder Energie-/Bauteil-Dokumente liegen. Extrahiert Bauteile aus IFC, ergänzt Betriebsenergie aus Doc-Dateien, verhandelt das Schema mit dem Vesta-A2A-Endpoint und sendet die Akte.
---

# Vesta LCA Quick-Check (externer A2A-Agent)

Du bist der Agent des Kunden. Deine Aufgabe: aus den Projektdateien eine vollständige
Vesta-Akte bauen und per A2A an den Vesta-customer-Agent senden. Die Skripte liegen im
Plugin unter `${CLAUDE_PLUGIN_ROOT}/scripts/` und werden mit `uv run` ausgeführt
(Abhängigkeiten zieht uv via PEP-723 automatisch — kein Setup nötig).

## Voraussetzung
Es muss ein Token hinterlegt sein (`~/.config/vesta/quick-check.env`). Falls ein Lauf
mit „Kein VESTA_CUSTOMER_TOKEN gefunden" abbricht, weise auf `/vesta-quick-check:setup`
hin und stoppe.

## Ablauf (strikt in dieser Reihenfolge)

0. **Ergebnisordner anlegen.** Alle Outputs gehören in einen Tagesordner im
   Projektverzeichnis: `YYMMDD_vesta_quick_check/` (heutiges Datum, z.B.
   `260612_vesta_quick_check/`). Lege ihn an und schreibe `draft_akte.json` und
   `akte.json` dorthin — der Report landet automatisch daneben. Nichts lose ins
   Projekt-Root legen.

1. **Schema entdecken.**
   `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/vesta_a2a_client.py card`
   Lies die Pflichtfelder — das ist der zu erfüllende Vertrag.

2. **IFC extrahieren.** Für jede `.ifc`-Datei im Projektordner:
   `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/ifc_extract.py <datei.ifc> -o <ergebnisordner>/draft_akte.json`

3. **Akte vervollständigen.** Baue `<ergebnisordner>/akte.json` aus dem draft.
   Ergänze aus den übrigen Dateien (Energiekonzept, Bauteillisten, PDFs, Tabellen):
   - `nfa_m2`, `rsp_years` (aus Energie-/Projektdoku)
   - `operational[]` (energy_carrier, annual_kwh_per_m2, purpose) aus dem Energiekonzept
   - fehlende `area_m2` / `material` aus Bauteillisten
   - Material-Strings auf ÖkobauDat-matchbare Bezeichnungen normalisieren
     (z.B. „Stahlbeton" → „Beton C25/30" + separater Bewehrungsstahl; „EPS" → „EPS-Hartschaum").
   - Schichtdicken auf **Meter** bringen (IFC liefert oft mm → durch 1000 teilen).
   - **Stück-Bauteile (Fenster/Türen) NICHT umrechnen.** Layer mit
     `unit_basis: "piece"` aus dem Draft unverändert übernehmen: `quantity` bleibt
     die **Stückzahl**, `area_m2` bleibt weg. Nur der `material`-String darf
     verbessert werden (z.B. „Tür-001" → „Innentür Holz"). Niemals Stück in
     Dicke/Fläche übersetzen — das verfälscht die Bilanz.

4. **GAP-FEEDBACK — die wichtigste Regel.** Erfinde NIEMALS fehlende Werte.
   `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/vesta_a2a_client.py validate <ergebnisordner>/akte.json`
   Bei gemeldeten Lücken: gib sie dem Mitarbeiter als konkrete, umsetzbare Liste zurück
   (welches Feld, welches Bauteil, welche vermutete Quelldatei) und STOPPE.

5. **Senden.** Erst wenn `validate` „[OK]" meldet:
   `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/vesta_a2a_client.py request-lca <ergebnisordner>/akte.json`
   Präsentiere den Kennwert (kg CO₂-eq/m²·a) und den Report-Pfad.

## Wichtig
- Das rohe IFC verlässt den Rechner nie — nur `akte.json` geht per A2A raus.
- Bei Auth-Fehler (401/403): Token/Vertrag mit Vesta klären (`/vesta-quick-check:setup`).
