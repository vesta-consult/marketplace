# Vesta DGNB-Vorcheck

Plugin für Claude Code aus dem [Vesta Marktplatz](../README.md). Der Vorcheck schätzt früh in der Planung, ob eine DGNB-Stufe (Silber, Gold, Platin) für ein Nutzungsprofil erreichbar ist, und liefert einen Maßnahmenkatalog, nach Wirkung sortiert. Kriterien und Bewertungslogik liegen bei Vesta, das Plugin ist der dünne Client.

Überblick, Ablauf, Datenschutz und Haftung stehen in der [Haupt-README](../README.md#dgnb-vorcheck).

> Prognose, keine Zusage einer Zertifizierung. Verbindlich bewertet nur die DGNB-Zertifizierungsstelle. Jede Antwort trägt einen Haftungshinweis.

## Einbinden

```
/plugin marketplace add vesta-consult/marketplace
/plugin install vesta-dgnb-precheck@vesta
/vesta-dgnb-precheck:setup <token>
```

Den Token (Format `vesta-frame-…`) bekommst du von Vesta mit dem Rahmenvertrag. `setup` legt ihn unter `~/.config/vesta/dgnb-precheck.env` ab, nicht im Projekt; in ein Repo gehört er nie. Voraussetzung: [uv](https://docs.astral.sh/uv/).

## Nutzung

Im Chat fragen, zum Beispiel:

> Wir planen ein Wohngebäude und wollen DGNB Gold erreichen. Ist das machbar, und was müssen wir dafür tun?

Der Agent nimmt Zielstufe, Nutzungsprofil (derzeit Wohngebäude) und, falls vorhanden, deine Punkte-Einschätzung je Kriterium auf. Fehlt die Zielstufe, fragt er nach. Punkte erfindet er nicht: Kriterien ohne Angabe bleiben „nicht bewertet“. Die Antwort enthält die erreichte Stufe, den Gesamterfüllungsgrad, ob die Zielstufe erreichbar ist, den Maßnahmenkatalog mit dem größten Hebel zuerst, die noch nicht bewerteten Kriterien und den Haftungshinweis.

## Ohne Agent

```bash
uv run scripts/vesta_dgnb_client.py card
uv run scripts/vesta_dgnb_client.py bewerten \
  --profil wohngebaeude --ziel-stufe gold --scores '{"env1.1": 70}'
```

`--scores` ist optional. Ohne Punkte-Einschätzung rechnet der Vorcheck vom Nullpunkt und liefert den vollständigen Maßnahmenkatalog für die Zielstufe.

Konfiguration über Umgebungsvariablen oder `~/.config/vesta/dgnb-precheck.env`:
`VESTA_A2A_URL` (Standard `https://a2a.zukunftimmobilie.de/customer`), `VESTA_CUSTOMER_TOKEN`.
