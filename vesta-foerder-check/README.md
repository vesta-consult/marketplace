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

## Nutzung

Im Chat fragen, zum Beispiel:

> Welche Förderung gibt es für eine Privatperson in Berlin, die ein Wohngebäude energetisch sanieren will?

Der Agent bildet daraus ein Profil: Zielgruppe, Assetklasse, Ebene, Vorhaben, Bundesland. Fehlt eine Angabe, die das Ergebnis verändert, etwa das Bundesland, fragt er nach, statt zu raten. Die Antwort enthält die passenden Programme mit Förderhöhe, soweit bezifferbar, die Kumulierung, Quellen, bekannte, aber noch nicht verifizierte Programme und den Haftungshinweis. Zusätzlich legt der Client die Zusammenfassung als `foerder-check-report.html` ab.

## Ohne Agent

```bash
uv run scripts/vesta_foerder_client.py card
uv run scripts/vesta_foerder_client.py empfehlung \
  --zielgruppe privatperson --assetklasse wohngebaeude --gegenstand sanierung --bundesland be
```

Konfiguration über Umgebungsvariablen oder `~/.config/vesta/foerder-check.env`:
`VESTA_A2A_URL` (Standard `https://a2a.zukunftimmobilie.de/customer`), `VESTA_CUSTOMER_TOKEN`.
