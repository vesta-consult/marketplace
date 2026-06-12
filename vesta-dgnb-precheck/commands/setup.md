---
description: Richtet den Vesta DGNB-Pre-Check ein — legt den Rahmenvertrag-Token nutzerweit ab. Nutzung: /vesta-dgnb-precheck:setup <token>
---

# Vesta DGNB-Pre-Check — Setup

Der Nutzer übergibt seinen Vesta-Rahmenvertrag-Token als Argument: `$ARGUMENTS`

Aufgabe:
1. Wenn `$ARGUMENTS` leer ist, frage den Nutzer nach seinem Token (er hat ihn von
   Vesta erhalten, Format `vesta-frame-...`). Sende ihn NICHT an Vesta, speichere ihn nur.
2. Lege die Datei `~/.config/vesta/dgnb-precheck.env` an (Verzeichnis bei Bedarf erstellen)
   mit folgendem Inhalt (Token aus dem Argument bzw. der Nutzerantwort einsetzen):

   ```
   VESTA_A2A_URL=https://a2a.zukunftimmobilie.de/customer
   VESTA_CUSTOMER_TOKEN=<token>
   ```

   Setze die Dateirechte restriktiv:
   ```bash
   mkdir -p ~/.config/vesta && chmod 700 ~/.config/vesta
   # Datei schreiben ...
   chmod 600 ~/.config/vesta/dgnb-precheck.env
   ```
3. Bestätige: „Token gespeichert unter ~/.config/vesta/dgnb-precheck.env. Du kannst jetzt
   in jedem Chat ‚DGNB-Pre-Check für … mit Ziel Gold' anfragen."
4. Weise darauf hin, den Token NIE in ein Projekt-Repo zu committen.
