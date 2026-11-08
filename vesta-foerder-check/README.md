# Vesta Förder-Check

Plugin für Claude Code aus dem [Vesta Marktplatz](../README.md). Der Förder-Check prüft, welche Förderprogramme von Bund und Ländern für ein Vorhaben in Frage kommen, wie sie sich kombinieren lassen und wie hoch die Förderung grob ausfällt. Gerechnet wird bei Vesta, das Plugin ist der dünne Client.

Überblick, Ablauf, Beispiel-Ergebnis, Datenschutz und Haftung stehen in der [Haupt-README](../README.md#förder-check).

> Unverbindliche Orientierung, keine Förder-, Rechts- oder Steuerberatung und keine Zusage einer Förderung. Jede Antwort trägt einen Haftungshinweis. Werte vor dem Antrag an der Primärquelle prüfen.

## Einbinden

```
/plugin marketplace add vesta-consult/marketplace
/plugin install vesta-foerder-check@vesta
/vesta-foerder-check:setup <token>
```

Den Token (Format `vesta-frame-…`) bekommst du von Vesta mit dem Rahmenvertrag. `setup` legt ihn unter `~/.config/vesta/foerder-check.env` ab, nicht im Projekt; in ein Repo gehört er nie. Voraussetzung: [uv](https://docs.astral.sh/uv/).

Aktualisieren: `/plugin marketplace update vesta`.

## Nutzung

Im Projektordner fragen, zum Beispiel:

> Welche Förderung gibt es für unser Vorhaben? Die Unterlagen liegen hier im Ordner.

oder ohne Unterlagen:

> Welche Förderung gibt es für eine Privatperson in Berlin, die ein Wohngebäude energetisch sanieren will?

Der Agent bildet ein Profil aus Zielgruppe, Assetklasse, Ebene, Vorhaben und Bundesland, bei Bedarf mit Investitionssumme und Zahl der Wohneinheiten. Fehlt eine Angabe, die das Ergebnis verändert, etwa das Bundesland, fragt er nach, statt zu raten.

## Ergebnis: Dashboard

Der Client legt `foerder-check-dashboard.html` im Projektordner ab, eine Datei zum Öffnen im Browser und zum Drucken:

- passende Programme nach Ebene, mit Förderart, Maßnahmenbezug und Förderhöhe, soweit bezifferbar; je Programm Eckwerte, Boni, Quellen und Prüfstand
- Kumulierung als Matrix: kombinierbar, schließt sich aus, konditional
- Förderpotenzial als Potenzialrechnung, wenn eine Investitionssumme genannt ist
- bekannte, aber nicht verifizierte Programme, deutlich abgesetzt
- ausgeschlossene Programme mit Grund und der vollständige Haftungsausschluss

Jeder weitere Lauf im selben Ordner gehört zum selben Projekt: `.vesta/foerder-check.json` hält Projekt-ID, Name und die Liste der Stände.

## 3D-Modell

Liegt in den Unterlagen ein Gebäudemodell (IFC oder CityGML), zeigt das Dashboard es in der Ansicht „Gebäude“. Sonst lädt das Plugin für die Adresse das amtliche LoD2-Modell des Landes, erst wenn es gebraucht wird:

| Automatisch | Bayern, Nordrhein-Westfalen, Baden-Württemberg, Berlin, Brandenburg, Mecklenburg-Vorpommern, Niedersachsen, Schleswig-Holstein, Rheinland-Pfalz |
|---|---|
| Noch nicht automatisch | Bremen, Hamburg, Hessen, Saarland, Sachsen, Sachsen-Anhalt, Thüringen (Dashboard ohne 3D, mit Hinweis auf das Portal des Landes) |

Geladene Kacheln bleiben im Nutzer-Cache (unter macOS `~/Library/Caches/vesta/lod2`, unter Linux `~/.cache/vesta/lod2`, unter Windows im lokalen AppData). Über 200 MB fragt der Agent vorher. Die Kennwerte im Modell dienen der Orientierung, für Anträge gelten die Flächen aus den Planunterlagen.

Von Hand:

```bash
uv run scripts/modell3d.py --adresse "Straße 1, 80331 München" --out szene.json
uv run scripts/modell3d.py --modell gebaeude.ifc --out szene.json
```

## Datenschutz

- An Vesta gehen das Profil, Projekt-ID und Projektname und, falls vorhanden, das 3D-Modell mit seiner Lage. Die Adresse und die Unterlagen selbst gehen nicht an Vesta.
- Für den Download geht die Adresse an OpenStreetMap Nominatim (Koordinaten) und an den Download-Server des Landes.
- Als Projektname keine Personennamen verwenden.

## Ohne Agent

```bash
uv run scripts/vesta_foerder_client.py card
uv run scripts/vesta_foerder_client.py empfehlung \
  --zielgruppe privatperson --assetklasse wohngebaeude --gegenstand sanierung --bundesland be \
  [--investitionssumme 150000] [--anzahl-we 1] [--szene szene.json] [--projektname "Name"]
```

Konfiguration über Umgebungsvariablen oder `~/.config/vesta/foerder-check.env`:
`VESTA_A2A_URL` (Standard `https://agents.vesta-consult.de/customer`), `VESTA_CUSTOMER_TOKEN`.
