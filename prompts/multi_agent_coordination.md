# Multi-Agent Coordination Prompts (Stopoda + Costraca)

## Setup
- Stopoda: http://localhost:8080 — primary executor
- Costraca: http://localhost:8081 — analyst & coordinator

---

## Prompt 1: Parallel Security Scan (Stopoda)

```
Führe einen Sicherheitsscan durch und erstelle einen Report für Costraca:

1. Scanne /home nach sensiblen Files (read-only, kein sudo).
2. Führe netstat -tulpn aus – liste alle offenen Ports und Prozesse.
3. Prüfe laufende Prozesse: ps aux | grep -E 'nc|ncat|socat|python|bash' – markiere verdächtige.
4. Exportiere Ergebnisse als JSON nach /tmp/stopoda_report.json.
5. Ausgabe: "Scan abgeschlossen. Report unter /tmp/stopoda_report.json"

KEINE destruktiven Aktionen. KEIN Netzwerkzugriff nach außen.
```

## Prompt 2: Threat Analysis Report (Costraca)

```
Analysiere den Stopoda-Report und erstelle ein professionelles Threat-Assessment:

1. Lese /tmp/stopoda_report.json (oder frage Stopoda via API nach dem Report).
2. Klassifiziere Findings nach MITRE ATT&CK-Kategorien.
3. Erstelle Risikobewertung: Critical / High / Medium / Low.
4. Schlage konkrete Mitigationsmaßnahmen vor.
5. Exportiere finalen Report als /tmp/costraca_threat_report.md.

Format: Executive Summary (3 Sätze) + Detailbefunde + Mitigations-Checkliste.
```

## Prompt 3: Koordinierter Backup (Costraca koordiniert Stopoda)

```
Koordiniere folgende Aufgaben:

COSTRACA-AUFGABE:
- Erstelle Backup-Plan basierend auf /tmp/stopoda_report.json.
- Validiere Zielverzeichnis /backup/sensitive/ (Schreibrechte prüfen).
- Warte auf meine Bestätigung: "BACKUP STARTEN"

STOPODA-DELEGIERUNG (nach meiner Bestätigung):
- Übergib Backup-Ausführungsbefehl an Stopoda per Sub-Agent.
- Monitoring: Fortschritt alle 30 Sekunden reporten.
- Abschluss: Prüfe Archiv-Integrität via tar -tzf.

Bei Fehler: Stopp + detailliertes Error-Log.
```

---

## Sicherheitsregeln für alle Prompts

```
SYSTEMWEITE GUARDRAILS (immer aktiv):

- Niemals: rm -rf, dd if=, mkfs, > /dev/sd*
- Niemals: Netzwerkverbindungen nach außen (wget/curl zu externen IPs)
- Niemals: sudo ohne explizite Benutzeranforderung
- Immer: confirm_human=true für destruktive Aktionen
- Immer: dry-run zuerst bei Dateioperationen
- Immer: Logging aller Aktionen nach /tmp/agent_audit.log
```
