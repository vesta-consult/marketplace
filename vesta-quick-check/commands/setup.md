---
description: Richtet den Vesta-Quick-Check ein — legt den Rahmenvertrag-Token nutzerweit ab. Nutzung: /vesta-quick-check:setup <token>
---

# Vesta Quick-Check — Setup

Der Nutzer übergibt seinen Vesta-Rahmenvertrag-Token als Argument: `$ARGUMENTS`

Aufgabe:
1. Wenn `$ARGUMENTS` leer ist, frage den Nutzer nach seinem Token (er hat ihn von
   Vesta erhalten, Format `vesta-frame-...`). Sende ihn NICHT an Vesta, speichere ihn nur.
2. Lege die Datei `~/.config/vesta/quick-check.env` an (Verzeichnis bei Bedarf erstellen)
   mit folgendem Inhalt (Token aus dem Argument bzw. der Nutzerantwort einsetzen):

   ```
   VESTA_A2A_URL=https://a2a.zukunftimmobilie.de/customer
   VESTA_CUSTOMER_TOKEN=<token>
   ```

   Setze die Dateirechte restriktiv:
   ```bash
   mkdir -p ~/.config/vesta && chmod 700 ~/.config/vesta
   # Datei schreiben ...
   chmod 600 ~/.config/vesta/quick-check.env
   ```
3. Bestätige: „Token gespeichert unter ~/.config/vesta/quick-check.env. Du kannst jetzt
   in jedem Projektordner ‚Mach den Vesta-Quick-Check' sagen."
4. Weise darauf hin, den Token NIE in ein Projekt-Repo zu committen.
