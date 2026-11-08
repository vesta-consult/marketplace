---
description: Richtet den Vesta Förder-Check ein — legt den Rahmenvertrag-Token nutzerweit ab. Nutzung: /vesta-foerder-check:setup <token>
---

# Vesta Förder-Check — Setup

Der Nutzer übergibt seinen Vesta-Rahmenvertrag-Token als Argument: `$ARGUMENTS`

Aufgabe:
1. Wenn `$ARGUMENTS` leer ist, frage den Nutzer nach seinem Token (er hat ihn von
   Vesta erhalten, Format `vesta-frame-...`). Sende ihn NICHT an Vesta, speichere ihn nur.
2. Lege die Datei `~/.config/vesta/foerder-check.env` an (Verzeichnis bei Bedarf erstellen)
   mit folgendem Inhalt (Token aus dem Argument bzw. der Nutzerantwort einsetzen):

   ```
   VESTA_A2A_URL=https://agents.vesta-consult.de/customer
   VESTA_CUSTOMER_TOKEN=<token>
   ```

   Setze die Dateirechte restriktiv:
   ```bash
   mkdir -p ~/.config/vesta && chmod 700 ~/.config/vesta
   # Datei schreiben ...
   chmod 600 ~/.config/vesta/foerder-check.env
   ```
3. Bestätige: „Token gespeichert unter ~/.config/vesta/foerder-check.env. Du kannst jetzt
   in jedem Chat ‚Welche Förderung gibt es für …' fragen."
4. Weise darauf hin, den Token NIE in ein Projekt-Repo zu committen.
