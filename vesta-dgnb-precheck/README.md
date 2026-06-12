# Vesta DGNB-Pre-Check — Claude-Code-Plugin (A2A)

Beantwortet in natürlicher Sprache **früh in der Planungsphase**, ob eine angestrebte
**DGNB-Zertifizierungsstufe** (Silber/Gold/Platin) für ein **Nutzungsprofil** erreichbar ist —
und liefert einen **priorisierten Maßnahmenkatalog**, was dafür zu erfüllen/umzusetzen ist.
Über den Vesta-A2A-Endpoint (Rahmenvertrag-Token). Die Bewertungslogik und der
DGNB-Kriterienkatalog liegen **server-seitig bei Vesta** (deterministisch über einen
sign-off-verifizierten Kern); das Plugin ist der dünne Client + der anfrage-extrahierende Agent.

> Unverbindliche Orientierung — **keine** Zertifizierungs-Zusage. Die verbindliche
> Zertifizierung trifft die DGNB-Zertifizierungsstelle; der Erfüllungsgrad ist eine Prognose.
> Jede Antwort trägt einen Haftungsausschluss.

## Installation

```
/plugin marketplace add vesta-consult/marketplace
/plugin install vesta-dgnb-precheck
/vesta-dgnb-precheck:setup <rahmenvertrag-token>
```

Den `vesta-frame-…`-Token erhältst du von Vesta (Rahmenvertrag). `setup` legt ihn nutzerweit
unter `~/.config/vesta/dgnb-precheck.env` ab — nie in ein Projekt-Repo committen.

## Nutzung

Einfach im Chat fragen, z.B.:

> „Wir planen ein Wohngebäude und wollen DGNB Gold erreichen — ist das machbar und was müssen
> wir dafür tun?"

Der Agent extrahiert die Anfrage (Nutzungsprofil + Zielstufe + ggf. grobe Punkte-Einschätzung),
ruft Vesta und bereitet die Einschätzung auf (erreichte Stufe + Gesamterfüllungsgrad +
priorisierter Maßnahmenkatalog + noch-nicht-bewertete Kriterien + Haftungsausschluss). Fehlt
die Zielstufe, fragt er nach, statt zu raten.

## Manuell (ohne Agent)

```bash
uv run scripts/vesta_dgnb_client.py card
uv run scripts/vesta_dgnb_client.py bewerten \
  --profil wohngebaeude --ziel-stufe gold --scores '{"env1.1": 70}'
```

`--scores` ist optional — ohne Punkte-Einschätzung liefert der Pre-Check aus dem Nullpunkt
heraus den vollständigen Maßnahmenkatalog für die Zielstufe.

Konfiguration via Env (oder `~/.config/vesta/dgnb-precheck.env`):
`VESTA_A2A_URL` (Default `https://a2a.zukunftimmobilie.de/customer`), `VESTA_CUSTOMER_TOKEN`.
