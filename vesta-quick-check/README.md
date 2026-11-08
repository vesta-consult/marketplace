# Vesta Ökobilanz (Quick-Check)

Plugin für Claude Code aus dem [Vesta Marktplatz](../README.md). Der Quick-Check berechnet die Ökobilanz eines Gebäudes nach DIN EN 15978 mit Datensätzen aus der ÖKOBAUDAT. Dein Agent liest Bauteile und Energiedaten aus dem Projektordner und schickt Vesta nur die strukturierte Akte. Das IFC-Modell verlässt deinen Rechner nicht.

Überblick, Ablauf, Beispiel-Ergebnis, Datenschutz und Haftung stehen in der [Haupt-README](../README.md#ökobilanz-quick-check).

> Orientierung für Planung und Variantenvergleich, kein Nachweis für QNG oder eine Zertifizierung. Jede Antwort trägt einen Haftungshinweis.

## Einbinden

```
/plugin marketplace add vesta-consult/marketplace
/plugin install vesta-quick-check@vesta
/vesta-quick-check:setup <token>
```

Den Token (Format `vesta-frame-…`) bekommst du von Vesta mit dem Rahmenvertrag. `setup` legt ihn unter `~/.config/vesta/quick-check.env` ab, nicht im Projekt; in ein Repo gehört er nie. Voraussetzung: [uv](https://docs.astral.sh/uv/).

## Nutzung

Leg die Projektdateien in den Ordner: IFC-Modell, Energiekonzept, bei Bedarf eine Bauteilliste. Dann in Claude Code:

> Mach den Vesta-Quick-Check für dieses Projekt.

Der Agent zieht Bauteile, Schichten und Mengen aus dem IFC-Modell, ergänzt Netto-Nutzfläche, Betrachtungszeitraum und Endenergie aus den Dokumenten und prüft die Akte. Werte erfindet er nicht: Fehlen Angaben, listet er sie auf und sendet nichts. Ergebnis: Kennwert in kg CO₂-Äq./(m²·a), Bilanz je Modul und ein HTML-Report im Tagesordner `JJMMTT_vesta_quick_check/`.

Ein vollständiges Beispiel liegt unter [`examples/`](examples/): IFC-Modell, Energiekonzept und Bauteilliste.

## Datenschutz

An Vesta geht nur die Akte mit Bauteilen, Mengen und Energiewerten. Das IFC-Modell und deine Dokumente bleiben lokal.
