---
name: vesta-foerder-check
description: Löst den Vesta Förder-Check aus — beantwortet, welche Bau-Förderprogramme (Bund/Land) für einen Mandanten in Frage kommen, wie sie sich kumulieren und wie hoch die Förderung grob ausfällt, und legt das Ergebnis als Dashboard (optional mit 3D-Modell des Gebäudes) im Projektordner ab. Trigger wenn der Nutzer "Förder-Check", "Welche Förderung", "Fördermittel für Sanierung/Neubau/Heizung", "passt KfW/BAFA/BEG", "Zuschuss für …", "Fördermittelanalyse" o.ä. sagt und ein Mandanten-/Gebäude-Profil beschreibt oder auf Projektunterlagen verweist. Extrahiert das Profil aus Freitext und Unterlagen, ruft den Vesta-A2A-Endpoint und bereitet die Empfehlung auf — IMMER mit Haftungsausschluss, nie als verbindliche Beratung.
---

# Vesta Förder-Check (externer A2A-Agent)

Du bist der Agent des Kunden. Deine Aufgabe: aus Freitext und Projektunterlagen ein **sauberes
strukturiertes Profil** bauen, optional ein 3D-Modell des Gebäudes vorbereiten und beides per A2A an
den Vesta-Customer-Agent senden. Die deterministische Logik und das Dashboard liegen bei Vesta.
Die Skripte liegen im Plugin unter `${CLAUDE_PLUGIN_ROOT}/scripts/` und laufen mit `uv run`
(Abhängigkeiten zieht uv via PEP 723 automatisch).

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

1. **Unterlagen sichten.** Nur den aktuellen Arbeitsordner (Projektordner) und Dateien, die der
   Nutzer ausdrücklich nennt — nicht die ganze Festplatte. Suche nach:
   - Profilangaben (Zielgruppe, Nutzung, Vorhaben, Bundesland), **Adresse** des Gebäudes,
     **Projektname**, **Investitionssumme**, **Anzahl Wohneinheiten**;
   - 3D-Dateien: `*.ifc`, `*.gml`, CityGML als `*.xml`, `*.zip` mit GML (höchstens zwei
     Ordnerebenen tief).
   Liegt `.vesta/foerder-check.json` im Projektordner, ist es ein weiterer Lauf zum selben Projekt
   (der Client hängt einen neuen Stand an).

2. **Profil bilden** — nur gültige Enum-Werte:
   - `zielgruppe` (1 Wert, **Pflicht**): privatperson · wohnungsunternehmen · kommune ·
     unternehmen · wohnungseigentuemergemeinschaft · contractor · investor ·
     projektentwickler · gemeinnuetzige_organisation
   - `assetklasse`: wohngebaeude · nichtwohngebaeude · buero · handel · logistik_industrie ·
     beherbergung · bildung_gesundheit · sonderbau · gemischt · unspezifisch (Default)
   - `vorhaben_ebene`: gebaeude (Default) · quartier · portfolio
   - `gegenstand` (mehrere, kommagetrennt): sanierung · neubau · heizung · einzelmassnahme ·
     anlagentechnik · gebaeudehuelle · fachplanung · kauf
   - `bundesland`: by·bw·be·bb·hb·hh·he·mv·ni·nrw·rp·sl·sn·st·sh·th

3. **GAP-DISZIPLIN — nichts erfinden.**
   - Rate **niemals** `zielgruppe` oder `bundesland`. Fehlt eine davon: **konkret nachfragen** und
     stoppen. Ergibt sich das Bundesland aus der geokodierten Adresse (Schritt 4), gilt es als
     belegt, nicht als geraten.
   - **Investitionssumme:** Übernimm als `--investitionssumme` nur eine Zahl, die ausdrücklich als
     Kosten des Vorhabens genannt ist. Stehen mehrere Kandidaten nebeneinander (brutto/netto,
     KG 300+400, Gesamtkosten, Kosten einzelner Gewerke), frag, welche gemeint ist. Nie schätzen,
     nie selbst addieren. Ohne Summe entfällt die Potenzialrechnung, das ist in Ordnung.
   - **Wohneinheiten:** Bei Wohngebäuden mit Investitionssumme frag nach `--anzahl-we`, wenn die
     Zahl fehlt (sonst rechnet Vesta mit 1 Wohneinheit und die Deckel fallen zu niedrig aus).
   - **Adresse:** Fehlt sie und liegt kein 3D-Modell vor, frag **einmal** danach, für die
     3D-Ansicht. Antwortet der Nutzer „ohne 3D“ oder nennt keine, mach ohne 3D weiter. Die
     Förderprüfung hängt nie am 3D.
   - `assetklasse`/`vorhaben_ebene` dürfen transparent auf den Default fallen.

4. **3D-Modell (optional).** Vorrang hat ein Modell aus den Unterlagen:
   - Datei vorhanden: `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/modell3d.py --modell <datei> --out <projektordner>/.vesta/szene.json`
   - sonst mit Adresse: `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/modell3d.py --adresse "<adresse>" --out <projektordner>/.vesta/szene.json`
     (amtliches LoD2-Modell des Landes, geladen erst jetzt, Kacheln landen im Nutzer-Cache).

   Exit-Codes von `modell3d.py`:
   - **0** — Szene geschrieben; die letzte Ausgabezeile nennt u. a. `bundesland` (für das Profil nutzbar).
     In Ländern ohne automatischen Download (HB, HH, HE, SL, SN, ST, TH) ist es eine **Lage-Szene**: Das
     Dashboard zeigt den Standort auf der Karte, ohne Gebäudemodell. Ohne Hausnummer in der Adresse wird kein
     Gebäude als „Ihr Gebäude“ markiert, nur die Umgebung gezeigt.
   - **3** — Adresse unklar (kein, mehrdeutiger oder nur ungenauer Treffer, etwa ohne die genannte
     Hausnummer): nenne die Kandidaten aus der Ausgabe und frag nach. Nicht raten.
   - **4** — Download über 200 MB: nenne die Größe und frag, ob geladen werden soll; bei Ja erneut
     mit `--erlaube-gross`.
   - **6** — Dateiformat nicht unterstützt: um einen Export als IFC oder CityGML bitten, ohne 3D weiter.
   - **2** — sonstiger Fehler: kurz erklären, ohne 3D weiter.

   Sag dem Nutzer, dass die Adresse für die Koordinaten an OpenStreetMap (Nominatim) und für das
   Modell an den Download-Server des Landes geht. An Vesta geht nur das fertige Modell (mit Lage,
   ohne Adresse).

5. **Senden.**
   `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/vesta_foerder_client.py empfehlung \`
   `  --zielgruppe <…> --assetklasse <…> --vorhaben-ebene <…> --gegenstand <a,b> --bundesland <xx> \`
   `  [--investitionssumme <eur>] [--anzahl-we <n>] [--szene <projektordner>/.vesta/szene.json] \`
   `  --projektordner <projektordner> [--projektname "<name>"]`

   Projektname: aus den Unterlagen, sonst lässt der Client den Ordnernamen stehen. Keine
   Personennamen als Projektname verwenden. Lehnt Vesta die Szene ab, wiederholt der Client den Lauf
   automatisch ohne 3D (Warnung auf stderr); die Förderprüfung hängt nie am 3D.
   Du bekommst JSON (`eligible[]`, `kumulierung[]`, `discovery_hinweise[]`, `ausgeschlossen[]`,
   ggf. `potenzial_gestapelt`, `haftungsausschluss`), und der Client legt das **Dashboard**
   `foerder-check-dashboard.html` im Projektordner ab.

6. **Antwort im Chat — kurz, ehrlich, geschichtet.** Das Dashboard trägt die Details; im Chat:
   - Zahl der passenden Programme und die wichtigsten (Name · Förderart). Förderhöhe NUR so
     belastbar wie `foerderhoehe.schaetzbar`: `ja` → `kurzform` als Obergrenze/Orientierung;
     `teilweise` → nur der Mechanismus; `nein` → „nicht bezifferbar".
   - Kumulierung in einem Satz (was sich ausschließt).
   - Mit Investitionssumme: das Potenzial **nur** als Potenzialrechnung, mit der angesetzten Summe
     und „keine Zusage".
   - Discovery-Hinweise als „zusätzlich bekannt, aber NICHT verifiziert".
   - Pfad zum Dashboard (im Browser öffnen, druckbar) und ob ein 3D-Modell dabei ist.

7. **Haftungsausschluss — IMMER am Ende.** Gib den vollständigen `haftungsausschluss.text`
   aus der Antwort **wörtlich und sichtbar** aus. Niemals weglassen, kürzen oder abschwächen.

## Wichtig
- Bei Auth-Fehler (401/403): Token/Vertrag klären (`/vesta-foerder-check:setup`); ggf. ist
  die Leistung `customer.foerder_check` im Rahmenvertrag noch nicht freigeschaltet.
- **Keine Zahlen-Halluzination:** Alle Werte stammen aus der Antwort. Bei Steuerinstrumenten
  (§ 35c, § 7b) zusätzlich darauf hinweisen, dass die Steuerwirkung vom individuellen Fall
  abhängt und steuerlich zu prüfen ist.
- Die Kennwerte im 3D-Modell (Grundfläche, Höhe …) stammen aus dem Gebäudemodell und dienen der
  Orientierung; für Anträge gelten die Flächen aus den Planunterlagen.
