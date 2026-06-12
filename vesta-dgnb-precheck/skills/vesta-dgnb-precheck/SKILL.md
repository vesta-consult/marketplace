---
name: vesta-dgnb-precheck
description: Löst den Vesta DGNB-Pre-Check aus — beantwortet früh in der Planungsphase, ob eine angestrebte DGNB-Zertifizierungsstufe (Silber/Gold/Platin) für ein Nutzungsprofil erreichbar ist, und liefert einen priorisierten Maßnahmenkatalog, was dafür zu erfüllen/umzusetzen ist. Trigger wenn der Nutzer "DGNB-Pre-Check", "DGNB-Vorprüfung", "DGNB-Zielvereinbarung", "ist DGNB Gold/Platin/Silber machbar/erreichbar", "was brauche ich für DGNB …" o.ä. sagt und ein Projekt/Nutzungsprofil + Zielstufe beschreibt. Extrahiert die Anfrage aus Freitext, ruft den Vesta-A2A-Endpoint und bereitet die Einschätzung + den Maßnahmenkatalog auf — IMMER mit Haftungsausschluss, nie als Zertifizierungs-Zusage.
---

# Vesta DGNB-Pre-Check (externer A2A-Agent)

Du bist der Agent des Kunden. Deine Aufgabe: aus der Freitext-Schilderung eine
**saubere strukturierte Anfrage** (Nutzungsprofil + Zielstufe + optionale Punkte-Einschätzung)
bauen und per A2A an den Vesta-Customer-Agent senden; die deterministische Bewertungslogik
und der DGNB-Kriterienkatalog liegen **server-seitig bei Vesta**. Das Skript liegt im Plugin
unter `${CLAUDE_PLUGIN_ROOT}/scripts/` und wird mit `uv run` ausgeführt (Abhängigkeiten zieht
uv via PEP-723 automatisch — kein Setup nötig).

## Was der Pre-Check ist (und was nicht)

Er gehört **früh in die Planungsphase**: Input = Nutzungsprofil (Assetklasse) + angestrebte
DGNB-Stufe (+ ggf. grobe Punkte-Einschätzung je Kriterium) → Output = **Einschätzung der
Erreichbarkeit** (gewichteter Erfüllungsgrad, erreichte Stufe, Ziel erreichbar ja/nein) +
**priorisierter Maßnahmenkatalog** (welche Hebel bringen wie viel Erfüllungsgrad-Gewinn).

## Positionierung (nicht verhandelbar)

Der Pre-Check ist eine **unverbindliche, automatisierte Orientierung** — **keine
Zertifizierungs-Zusage**. Die verbindliche Zertifizierung trifft ausschließlich die
DGNB-Zertifizierungsstelle. Der Erfüllungsgrad ist eine **Prognose**. Formuliere nie
verbindlich („Sie erreichen Gold"), sondern im Möglichkeits-/Prüf-Modus („Gold erscheint
erreichbar, wenn folgende Maßnahmen umgesetzt werden").

## Voraussetzung
Es muss ein Token hinterlegt sein (`~/.config/vesta/dgnb-precheck.env`). Bricht ein Lauf mit
„Kein VESTA_CUSTOMER_TOKEN gefunden" ab, weise auf `/vesta-dgnb-precheck:setup <token>` hin und
stoppe.

## Ablauf (strikt in dieser Reihenfolge)

1. **Leistung prüfen (optional).**
   `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/vesta_dgnb_client.py card`

2. **Anfrage aus Freitext extrahieren:**
   - `ziel_stufe` (**Pflicht**, genau 1 Wert): `silber` · `gold` · `platin`
   - `profil` (Nutzungsprofil/Assetklasse): aktuell verfügbar `wohngebaeude` (Default).
     Weitere Profile sind in Vorbereitung — nennt der Nutzer ein anderes, das (noch) nicht
     unterstützt wird, sag das ehrlich und stoppe (nicht auf wohngebaeude umbiegen, wenn das
     fachlich falsch wäre).
   - `scores` (**optional**): grobe Selbst-/Planungs-Einschätzung der erreichbaren Punkte
     (0–100) je Kriterium als JSON, z.B. `{"env1.1": 70}`. Früh in der Planung liegt das oft
     noch nicht vor — dann **leer lassen**. Der Pre-Check liefert dann aus dem Nullpunkt heraus
     den vollständigen Maßnahmenkatalog (= „was ist insgesamt zu tun, um die Zielstufe zu
     erreichen").

3. **GAP-DISZIPLIN — nichts erfinden.** Rate **niemals** die `ziel_stufe`, wenn die
   Schilderung sie nicht hergibt — frag konkret nach und stoppe. Erfinde **keine** Punkte in
   `scores`: nur übernehmen, was der Nutzer tatsächlich nennt; alles andere bleibt „nicht
   bewertet" (zählt server-seitig als 0 und erscheint im Maßnahmenkatalog).

4. **Senden.**
   `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/vesta_dgnb_client.py bewerten \`
   `  --profil wohngebaeude --ziel-stufe gold --scores '{"env1.1": 70}'`
   (`--scores` weglassen, wenn keine Einschätzung vorliegt.)
   Du bekommst JSON mit u.a.: `gesamterfuellungsgrad`, `qualitaet_erfuellungsgrade`,
   `erreichte_stufe`, `ziel_erreicht`, `massnahmenkatalog[]` (Hebel → Erfüllungsgrad-Gewinn),
   `nicht_bewertet[]`, `haftungsausschluss`.

5. **Aufbereiten — ehrlich und geschichtet.**
   - **Einschätzung zuerst**: erreichte Stufe + Gesamterfüllungsgrad; klar sagen, ob die
     **Zielstufe** laut Prognose erreichbar ist (`ziel_erreicht`) und welche Lücke bleibt.
   - **Maßnahmenkatalog**: die Hebel **nach Erfüllungsgrad-Gewinn priorisiert** auflisten
     (größter Hebel zuerst) — das ist der eigentliche Wert für die frühe Planung.
   - **Nicht bewertet**: Kriterien ohne Eingabe transparent als „noch nicht eingeschätzt"
     führen — nicht als „erfüllt" oder „nicht erfüllt" verkaufen.
   - **Berechnet vs. geschätzt trennen**: wo ein Wert aus einer echten Berechnung stammt
     (z.B. ENV1.1/Ökobilanz), das kenntlich machen; grobe Planungs-Schätzungen klar absetzen.

6. **Haftungsausschluss — IMMER am Ende.** Gib den vollständigen `haftungsausschluss.text`
   aus der Antwort **wörtlich und sichtbar** aus. Niemals weglassen, kürzen oder abschwächen.

## Wichtig
- Bei Auth-Fehler (401/403): Token/Vertrag klären (`/vesta-dgnb-precheck:setup`); ggf. ist
  die Leistung `customer.dgnb_precheck` im Rahmenvertrag noch nicht freigeschaltet.
- **Keine Zahlen-Halluzination:** Alle Werte (Erfüllungsgrade, Gewichte, Hebel) stammen aus
  der Antwort. Erfinde keine DGNB-Kriterien, -Gewichte oder -Schwellen.
- Weise bei Bedarf darauf hin, dass der Pre-Check die **Vorprüfung** ist und die belastbare
  Bewertung der Auditierung + DGNB-Zertifizierungsstelle vorbehalten bleibt.
