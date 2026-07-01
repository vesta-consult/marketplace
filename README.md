# Vesta Marketplace — Claude-Code-Plugins (A2A)

Ein Marketplace für **alle** agentischen Dienste von **vesta sustainability consulting**.
Jedes Plugin ist ein **dünner Client**, der per A2A mit dem jeweiligen Vesta-Endpoint spricht
(Rahmenvertrag-Token). Die Rechen-/Haftungslogik und die kuratierten Daten liegen
**server-seitig** bei Vesta — dieses Repo enthält bewusst **keinen** Server-Code, keine
Datenbestände und keine Tokens.

## Installation

```
/plugin marketplace add vesta-consult/marketplace
/plugin install vesta-quick-check      # oder vesta-foerder-check
```

Danach den Rahmenvertrag-Token hinterlegen (von Vesta erhalten):
```
/vesta-quick-check:setup <token>
/vesta-foerder-check:setup <token>
```

## Plugins

| Plugin | Was | Eingabe |
|---|---|---|
| **vesta-quick-check** | EN-15978-Gebäude-Ökobilanz (kg CO₂-eq/m²·a) | IFC + Energiekonzept |
| **vesta-foerder-check** | Passende Bau-Förderprogramme (Bund/Land) inkl. Kumulierung + Förderhöhe | Mandanten-Profil (Freitext) |
| **vesta-dgnb-precheck** | DGNB-Zielvereinbarung (Silber/Gold/Platin): erreichbarer Erfüllungsgrad + priorisierter Maßnahmenkatalog | Nutzungsprofil + Zielstufe + Punkte-Einschätzung je Kriterium |

Welche Leistungen dein Token freischaltet, regelt dein Rahmenvertrag.

## Hinweis

Unverbindliche Orientierung — die Dienste ersetzen keine Rechts-, Steuer- oder
Fachberatung; jede Ausgabe trägt ihren eigenen Haftungshinweis.

— Kontakt: hannes.harter@vesta-consult.de
