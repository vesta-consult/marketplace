---
name: vesta-foerder-check
description: Löst den Vesta Förder-Check aus — beantwortet, welche Bau-Förderprogramme (Bund/Land) für einen Mandanten in Frage kommen, wie sie sich kumulieren und wie hoch die Förderung grob ausfällt. Trigger wenn der Nutzer "Förder-Check", "Welche Förderung", "Fördermittel für Sanierung/Neubau/Heizung", "passt KfW/BAFA/BEG", "Zuschuss für …" o.ä. sagt und ein Mandanten-/Gebäude-Profil beschreibt. Extrahiert das Profil aus Freitext, ruft den Vesta-A2A-Endpoint und bereitet die Empfehlung auf — IMMER mit Haftungsausschluss, nie als verbindliche Beratung.
---

# Vesta Förder-Check (externer A2A-Agent)

Du bist der Agent des Kunden. Deine Aufgabe: aus der Freitext-Schilderung ein
**sauberes strukturiertes Profil** bauen und per A2A an den Vesta-Customer-Agent senden;
die deterministische Logik liegt server-seitig bei Vesta. Das Skript liegt im Plugin unter
`${CLAUDE_PLUGIN_ROOT}/scripts/` und wird mit `uv run` ausgeführt (Abhängigkeiten zieht uv
via PEP-723 automatisch — kein Setup nötig).

## Positionierung (nicht verhandelbar)

Der Förder-Check ist eine **unverbindliche, automatisierte Orientierung** — **keine
Förder-, Rechts- oder Steuerberatung** und **keine Zusage einer Förderfähigkeit**. Formuliere
nie verbindlich („Sie bekommen"), sondern im Möglichkeits-/Prüf-Modus („kommt in Frage",
„laut Richtlinie möglich, vor Antrag prüfen").

## Voraussetzung
Es muss ein Token hinterlegt sein (`~/.config/vesta/foerder-check.env`). Bricht ein Lauf mit
„Kein VESTA_CUSTOMER_TOKEN gefunden" ab, weise auf `/vesta-foerder-check:setup <token>` hin und
stoppe.

## Ablauf (strikt in dieser Reihenfolge)

1. **Leistung prüfen (optional).**
   `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/vesta_foerder_client.py card`

2. **Profil aus Freitext extrahieren** — nur gültige Enum-Werte:
   - `zielgruppe` (1 Wert, **Pflicht**): privatperson · wohnungsunternehmen · kommune ·
     unternehmen · wohnungseigentuemergemeinschaft · contractor · investor ·
     projektentwickler · gemeinnuetzige_organisation
   - `assetklasse`: wohngebaeude · nichtwohngebaeude · buero · handel · logistik_industrie ·
     beherbergung · bildung_gesundheit · sonderbau · gemischt · unspezifisch (Default)
   - `vorhaben_ebene`: gebaeude (Default) · quartier · portfolio
   - `gegenstand` (mehrere, kommagetrennt): sanierung · neubau · heizung · einzelmassnahme ·
     anlagentechnik · gebaeudehuelle · fachplanung · kauf
   - `bundesland`: 2-Buchstaben-Code bw·by·be·bb·hb·hh·he·mv·ni·nrw·rp·sl·sn·st·sh·th

3. **GAP-DISZIPLIN — nichts erfinden.** Rate **niemals** `zielgruppe` oder `bundesland`,
   wenn die Schilderung sie nicht hergibt (beide verändern das Ergebnis stark — Land-Programme
   erscheinen nur mit Bundesland). Fehlt eine entscheidende Achse: **frag konkret nach** und
   stoppe. `assetklasse`/`vorhaben_ebene` dürfen transparent auf den Default fallen.

4. **Senden.**
   `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/vesta_foerder_client.py empfehlung \`
   `  --zielgruppe <…> --assetklasse <…> --vorhaben-ebene <…> --gegenstand <a,b> --bundesland <xx>`
   Du bekommst JSON: `eligible[]` (mit `massnahmen_fit`, `foerderhoehe`, ggf. `haftung`),
   `kumulierung[]`, `discovery_hinweise[]`, `haftungsausschluss`, `ausgeschlossen[]`.
   Zusätzlich legt der Client ein **zusammenfassendes Dokument** ab
   (`foerder-check-report.html`, vom Vesta-Agenten erzeugt, mit Haftungsausschluss).
   Mit `--report <pfad>` lässt sich der Zielpfad setzen.

5. **Aufbereiten — ehrlich und geschichtet.**
   - **Passende Programme**: Name · Ebene/Förderart · Maßnahmen-Fit. Förderhöhe NUR so
     belastbar wie `foerderhoehe.schaetzbar`: `ja` → `kurzform` als Obergrenze/Orientierung;
     `teilweise` → nur der Mechanismus, keine Euro-Pauschale; `nein` → ehrlich „nicht
     bezifferbar" (Zinsvorteil, AfA).
   - **Kumulierung**: kombinierbar / schließt sich aus / konditional — mit Quelle.
   - **`sign_off` offen** (`haftung`-Feld): als „vor Beratungsaussage prüfen" kenntlich machen.
   - **Discovery-Hinweise**: als „zusätzlich bekannt, aber NICHT verifiziert" führen, klar
     abgesetzt von den belastbaren Treffern, mit Primärquellen-Pointer.
   - **Dokument**: weise den Nutzer auf das gespeicherte `foerder-check-report.html` hin
     (öffenbar im Browser, druck-/PDF-fähig) — es fasst alles inkl. Haftungsausschluss zusammen.

6. **Haftungsausschluss — IMMER am Ende.** Gib den vollständigen `haftungsausschluss.text`
   aus der Antwort **wörtlich und sichtbar** aus. Niemals weglassen, kürzen oder abschwächen.

## Wichtig
- Bei Auth-Fehler (401/403): Token/Vertrag klären (`/vesta-foerder-check:setup`); ggf. ist
  die Leistung `customer.foerder_check` im Rahmenvertrag noch nicht freigeschaltet.
- **Keine Zahlen-Halluzination:** Alle Werte stammen aus der Antwort. Bei Steuerinstrumenten
  (§ 35c, § 7b) zusätzlich darauf hinweisen, dass die Steuerwirkung vom individuellen Fall
  abhängt und steuerlich zu prüfen ist.
