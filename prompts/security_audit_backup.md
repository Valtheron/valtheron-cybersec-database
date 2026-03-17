# Security Audit & Backup Prompt (ReAct-Style, Human-in-Loop)

## Usage
Paste this prompt into Stopoda (localhost:8080) for a safe, step-by-step audit.

---

```
Security Audit & Backup Task (Step-by-Step mit Safety):

1. Scan only (read-only):
   Durchsuche /home rekursiv nach sensiblen Files.
   Patterns: '.pem', '.key', '.ssh/', '.env', 'password', 'secret', '.gpg', '.p12', 'credentials', 'id_rsa', 'id_ed25519'.
   Ignoriere: .git/, __pycache__/, node_modules/, Downloads/, .cache/.

2. Liste detailliert:
   Für jeden Treffer ausgeben: Vollpfad, Dateigröße, last modified, Dateiberechtigungen, erste 50 Bytes als HEX-Preview (keine Klartextsecrets!).
   KEINE Löschung, KEINE Änderung, KEINE Netzwerkverbindungen.

3. Risiko-Bewertung:
   Klassifiziere jeden Fund: high / medium / low.
   - high: SSH-Keys, private Certs, GPG-Keys
   - medium: .env-Files, Passwort-Dateien
   - low: Config-Files mit Credentials-Hinweisen

4. Backup-Vorschlag:
   Erstelle Plan: tar.gz pro Risiko-Kategorie nach /backup/sensitive/YYYY-MM-DD/.
   Führe zuerst rsync --dry-run aus und zeige Output.
   Erstelle Zielordner nur nach Bestätigung.

5. STOP – Warte auf Bestätigung:
   Zeige vollständigen Report.
   Frage explizit: "Bestätige Backup-Ausführung mit: JA + Zielordner: /backup/sensitive-files-HEUTE"
   Bei JA: Führe Backup aus.
   Bei NEIN oder Timeout: Stoppe vollständig und logge Entscheidung.

Tools: file_search, shell (ls/find/stat/rsync/tar).
Kein sudo. Kein Netzwerkzugriff. Privacy first.
```

---

## Warum dieser Prompt funktioniert

| Feature | Beschreibung |
|---|---|
| ReAct-Style | Atomisierte Steps – Agent denkt, handelt, berichtet |
| Human-in-Loop | Explizite JA-Bestätigung vor jeder Aktion |
| Dry-Run first | rsync --dry-run zeigt was passiert, bevor es passiert |
| Privacy-safe | Preview nur als HEX, keine Klartextsecrets |
| Patterns | Security-fokussiert: Keys, Certs, Env-Files |
| No sudo | Minimale Rechte – kein Systemzugriff |
