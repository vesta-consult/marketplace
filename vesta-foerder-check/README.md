# Vesta Förder-Check — Claude-Code-Plugin (A2A)

Fragt in natürlicher Sprache, **welche Bau-Förderprogramme (Bund/Land)** für einen
Mandanten in Frage kommen, wie sie sich **kumulieren** und wie hoch die **Förderung** grob
ausfällt — über den Vesta-A2A-Endpoint (Rahmenvertrag-Token). Die Rechen-/Haftungslogik liegt
server-seitig bei Vesta (deterministisch über einen primär-verifizierten Kern); das Plugin ist
der dünne Client + der Profil-extrahierende Agent.

> Unverbindliche Orientierung — **keine** Förder-, Rechts- oder Steuerberatung. Jede Antwort
> trägt einen Haftungsausschluss; Werte sind vor Antrag gegen die Primärquelle zu prüfen.

## Installation

```
/plugin marketplace add vesta-consult/marketplace
/plugin install vesta-foerder-check
/vesta-foerder-check:setup <rahmenvertrag-token>
```

Den `vesta-frame-…`-Token erhältst du von Vesta (Rahmenvertrag). `setup` legt ihn nutzerweit
unter `~/.config/vesta/foerder-check.env` ab — nie in ein Projekt-Repo committen.

## Nutzung

Einfach im Chat fragen, z.B.:

> „Welche Förderung gibt es für eine Privatperson in Berlin, die ein Wohngebäude energetisch
> sanieren will?"

Der Agent extrahiert das Profil (zielgruppe/assetklasse/vorhaben_ebene/gegenstand/bundesland),
ruft Vesta und bereitet die Empfehlung auf (passende Programme + Förderhöhe + Kumulierung +
bekannte-aber-unverifizierte Hinweise + Haftungsausschluss). Fehlt eine entscheidende Angabe
(z.B. Bundesland), fragt er nach, statt zu raten.

## Manuell (ohne Agent)

```bash
uv run scripts/vesta_foerder_client.py card
uv run scripts/vesta_foerder_client.py empfehlung \
  --zielgruppe privatperson --assetklasse wohngebaeude --gegenstand sanierung --bundesland be
```

Konfiguration via Env (oder `~/.config/vesta/foerder-check.env`):
`VESTA_A2A_URL` (Default `https://a2a.zukunftimmobilie.de/customer`), `VESTA_CUSTOMER_TOKEN`.
