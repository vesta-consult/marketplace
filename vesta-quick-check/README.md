# Vesta LCA Quick-Check — Claude-Code-Plugin

Löse einen LCA-Quick-Check aus deinem Projektordner aus. Dein Claude Code wird zum
Agenten, der IFC + Energiedaten extrahiert und per A2A mit Vesta verhandelt — das rohe
IFC verlässt deinen Rechner nicht.

## Voraussetzungen
- [Claude Code](https://code.claude.com)
- [uv](https://docs.astral.sh/uv/) (zieht die Python-Abhängigkeiten automatisch)

## Installation
```
/plugin marketplace add vesta-consult/marketplace
/plugin install vesta-quick-check
```

## Einrichtung (einmalig)
```
/vesta-quick-check:setup <dein-vesta-token>
```
Der Token (von Vesta erhalten, Format `vesta-frame-...`) wird unter
`~/.config/vesta/quick-check.env` abgelegt — nicht im Projekt.

## Nutzung
Leg deine Projektdateien (IFC-Modell + Energiekonzept + Bauteilliste …) in den Ordner.
Dann in Claude Code:

> „Mach den Vesta-Quick-Check für dieses Projekt."

Claude extrahiert die Daten, fragt fehlende Angaben bei dir nach (es erfindet nichts)
und sendet die fertige Akte. Ergebnis: Kennwert in kg CO₂-eq/(m²·a) + HTML-Report.

Ein vollständiges Beispiel liegt unter `examples/` (IFC + Energiekonzept + Bauteilliste).

## Datenschutz
Nur die strukturierte Akte (Bauteile, Mengen, Energie) geht per A2A an Vesta.
