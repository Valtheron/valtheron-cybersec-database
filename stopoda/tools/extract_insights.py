"""
extract_insights.py – Stopoda custom tool
Analysiert YouTube-Transkripte mit Claude API:
  1. Extrahiert Hard Facts (Zahlen, Daten, Fakten)
  2. Identifiziert visionäre Claims
  3. Mappt Insights auf ein Zielprodukt (z.B. Valtheron Agentic Workspace)
  4. Generiert Marketing-Konzept

Usage:
  python3 extract_insights.py --transcript transcript.txt --product "Valtheron Agentic Workspace" --out marketing_pitch.md
  python3 extract_insights.py --url https://youtu.be/... --product "..." --out pitch.md
"""

import argparse
import os
import sys
import json
from pathlib import Path
from datetime import datetime


# ──────────────────────────────────────────────────────────────────────────────
# Claude API
# ──────────────────────────────────────────────────────────────────────────────

def _get_claude_client():
    try:
        import anthropic
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY nicht gesetzt.")
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        raise RuntimeError("anthropic SDK fehlt. Installieren: pip install anthropic")


def _call_claude(client, system: str, user: str, model: str = "claude-sonnet-4-6") -> str:
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}]
    )
    return response.content[0].text


# ──────────────────────────────────────────────────────────────────────────────
# Schritt 1: Hard Facts extrahieren
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_HARD_FACTS = """Du bist ein Business-Analyst. Deine Aufgabe:
Extrahiere aus dem gegebenen Transkript ALLE messbaren, belegbaren Hard Facts.

Format pro Fact:
- [FACT] Aussage (Quelle: direkte Wiedergabe aus Transkript)

Kategorien:
- Zahlen & Statistiken
- Zeitangaben & Prognosen
- Historische Vergleiche
- Marktdaten
- Business-Metriken

Nur was direkt im Text steht. Keine Interpretation."""

def extract_hard_facts(client: object, transcript: str) -> str:
    print("[1/3] Extrahiere Hard Facts ...")
    return _call_claude(client, SYSTEM_HARD_FACTS,
                        f"Transkript:\n\n{transcript}")


# ──────────────────────────────────────────────────────────────────────────────
# Schritt 2: Visionäre Aussagen + Belege
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_VISION = """Du bist ein strategischer Analyst. Deine Aufgabe:
1. Identifiziere die 5-8 wichtigsten visionären Kernthesen des Transkripts.
2. Bestätige/belege jede These mit historischen oder wissenschaftlichen Parallelen die du kennst.
3. Bewerte den Reifegrad: Spekulativ / Plausibel / Belegt

Format:
## These: [Kurztitel]
**Originalaussage:** "..."
**Beleg/Bestätigung:** [historische Parallele, Forschung, Marktdaten]
**Reifegrad:** Spekulativ | Plausibel | Belegt
"""

def extract_vision(client: object, transcript: str, hard_facts: str) -> str:
    print("[2/3] Analysiere visionäre Aussagen ...")
    return _call_claude(client, SYSTEM_VISION,
                        f"Transkript:\n\n{transcript}\n\nBereits extrahierte Hard Facts:\n{hard_facts}")


# ──────────────────────────────────────────────────────────────────────────────
# Schritt 3: Marketing-Konzept generieren
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_MARKETING = """Du bist ein Senior Marketing Stratege und Copywriter.

Deine Aufgabe: Erstelle ein vollständiges Marketing-Konzept auf Deutsch.

Du bekommst:
- Hard Facts aus einem Video mit zwei Visionären
- Ihre visionären Thesen
- Den Namen + Features des Zielprodukts

Das Marketing-Konzept soll:
1. Die Thesen der Visionäre als Beweis nutzen (Social Proof durch Expert Framing)
2. Die Hard Facts als Markt-Kontext einsetzen
3. Die Features des Produkts als direkte Antwort auf die identifizierten Probleme positionieren
4. In mehreren Formaten geliefert werden:
   - Executive Summary (3 Sätze)
   - Problem-Narrative (warum jetzt?)
   - Produktpositionierung (Value Proposition)
   - 5 Headline-Varianten für Landing Page
   - 3 Social Media Posts (LinkedIn)
   - Investor/Partner Pitch Paragraph

Stil: Direkt, mutig, ohne Buzzword-Bingo. Substanz vor Style."""

def generate_marketing(client: object, product_name: str, product_features: str,
                       hard_facts: str, vision_analysis: str) -> str:
    print("[3/3] Generiere Marketing-Konzept ...")
    prompt = f"""Produkt: {product_name}

Produkt-Features:
{product_features}

Hard Facts aus Video:
{hard_facts}

Visionäre Thesen & Belege:
{vision_analysis}

Erstelle das vollständige Marketing-Konzept auf Deutsch."""
    return _call_claude(client, SYSTEM_MARKETING, prompt)


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline
# ──────────────────────────────────────────────────────────────────────────────

VALTHERON_FEATURES = """
Valtheron Agentic Workspace – Central Control Room für autonome AI-Agenten:

KERN-FEATURES:
- 290 autonome AI-Agenten in 10 Kategorien (Trading, Security, Development, QA, Documentation, Deployment, Analyst, Support, Integration, Monitoring)
- Emergency Kill-Switch: sofortiger Stopp aller Agenten-Operationen
- AES-256-GCM Verschlüsselung für alle sensiblen Daten
- Multi-Faktor-Authentifizierung (TOTP) + Role-Based Access Control
- Vollständiger Audit-Log mit CSV-Export
- Kanban Task-Board (5-Stage Workflow) für Agenten-Tasks
- Real-time Chat mit Claude, OpenAI oder Ollama (lokal, keine Cloud-Abhängigkeit)
- WebSocket Real-time Kommunikation
- 6-Stunden automatische Backups mit 10-Rotations-Retention
- 475+ Tests, 87.8% Code Coverage, OWASP Top 10 Compliant
- Docker Compose + GitHub Actions CI/CD
- Läuft vollständig lokal (kein Cloud-Lock-in, keine laufenden API-Kosten)

ZIELGRUPPE:
- Entrepreneurs die Software mit AI-Agenten bauen
- Security-Teams die Agenten-Operationen absichern müssen
- Kleine/mittlere Teams die 10x produktiver werden wollen ohne 10x mehr Menschen einzustellen
- Gründer die "team of agents" statt "team of employees" aufbauen
"""


def run_pipeline(transcript: str, product_name: str, product_features: str,
                 output_path: str | None = None) -> str:

    client = _get_claude_client()

    hard_facts = extract_hard_facts(client, transcript)
    vision = extract_vision(client, transcript, hard_facts)
    marketing = generate_marketing(client, product_name, product_features,
                                   hard_facts, vision)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    result = f"""# Marketing-Konzept: {product_name}
*Generiert: {timestamp}*

---

## TEIL 1: Hard Facts aus Quell-Video

{hard_facts}

---

## TEIL 2: Visionäre Thesen & Validierung

{vision}

---

## TEIL 3: Marketing-Konzept

{marketing}
"""

    if output_path:
        Path(output_path).write_text(result, encoding="utf-8")
        print(f"\n✓ Gespeichert: {output_path}")

    return result


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="YouTube Insight → Marketing-Konzept Pipeline")
    parser.add_argument("--transcript", help="Pfad zur Transkript-Datei (.txt)")
    parser.add_argument("--url", help="YouTube URL (wird mit youtube_stt.py transkribiert)")
    parser.add_argument("--product", default="Valtheron Agentic Workspace",
                        help="Produktname für das Marketing-Konzept")
    parser.add_argument("--features", default=None,
                        help="Pfad zu Features-Datei (default: Valtheron Agentic Workspace)")
    parser.add_argument("--out", default=None,
                        help="Output-Datei (.md). Default: stdout")
    parser.add_argument("--lang", default="de",
                        help="Sprache für youtube_stt Fallback (default: de)")
    args = parser.parse_args()

    # Transkript laden
    if args.transcript:
        transcript = Path(args.transcript).read_text(encoding="utf-8")
    elif args.url:
        # Fallback: youtube_stt.py aufrufen
        import subprocess
        stt_path = Path(__file__).parent / "youtube_stt.py"
        result = subprocess.run(
            ["python3", str(stt_path), args.url, "--text-only", "--lang", args.lang],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Fehler bei STT: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        transcript = result.stdout
    else:
        print("Fehler: --transcript oder --url erforderlich.", file=sys.stderr)
        sys.exit(1)

    # Features laden
    if args.features:
        product_features = Path(args.features).read_text(encoding="utf-8")
    else:
        product_features = VALTHERON_FEATURES

    # Pipeline ausführen
    output = run_pipeline(transcript, args.product, product_features, args.out)

    if not args.out:
        print(output)


if __name__ == "__main__":
    main()
