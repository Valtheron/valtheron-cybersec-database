"""
youtube_stt.py – Stopoda custom tool
YouTube transcript extraction + German speech-to-text (local, offline-first).

Strategie (Fallback-Kette):
  1. youtube-transcript-api  → direkt aus YouTube Untertiteln (schnell, kein Download)
  2. yt-dlp + faster-whisper → Audio herunterladen, lokal transkribieren (privat, kein Cloud)

Kein API-Key, kein Cloud. Vollständig lokal.
"""

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────────────
# Hilfsfunktionen
# ──────────────────────────────────────────────────────────────────────────────

def _check_dep(module: str) -> bool:
    import importlib
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


def _extract_video_id(url: str) -> str:
    """Extrahiert die YouTube Video-ID aus verschiedenen URL-Formaten."""
    import re
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    raise ValueError(f"Keine Video-ID in URL gefunden: {url}")


# ──────────────────────────────────────────────────────────────────────────────
# Methode 1 – YouTube Transcript API (bevorzugt, kein Download)
# ──────────────────────────────────────────────────────────────────────────────

def fetch_youtube_transcript(url: str, preferred_langs: list[str] = None) -> dict:
    """
    Ruft das Transkript direkt von YouTube ab (falls Untertitel verfügbar).
    preferred_langs: Liste von Sprach-Codes z.B. ['de', 'en']
    Gibt None zurück wenn keine Untertitel verfügbar.
    """
    if not _check_dep("youtube_transcript_api"):
        return {
            "success": False,
            "error": "youtube-transcript-api nicht installiert. "
                     "Installieren mit: pip install youtube-transcript-api",
            "method": "youtube_transcript_api",
        }

    from youtube_transcript_api import (
        YouTubeTranscriptApi,
        TranscriptsDisabled,
        NoTranscriptFound,
    )

    if preferred_langs is None:
        preferred_langs = ["de", "en", "en-US", "de-DE"]

    try:
        video_id = _extract_video_id(url)
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        # Versuch: manuelle Untertitel zuerst (höhere Qualität)
        transcript = None
        for lang in preferred_langs:
            try:
                transcript = transcript_list.find_manually_created_transcript([lang])
                transcript_type = "manual"
                break
            except Exception:
                pass

        # Fallback: auto-generierte Untertitel
        if transcript is None:
            for lang in preferred_langs:
                try:
                    transcript = transcript_list.find_generated_transcript([lang])
                    transcript_type = "auto-generated"
                    break
                except Exception:
                    pass

        if transcript is None:
            # Letzter Versuch: nimm was verfügbar ist und übersetze
            available = list(transcript_list)
            if available:
                transcript = available[0]
                transcript_type = f"auto-translated from {transcript.language_code}"
            else:
                return {
                    "success": False,
                    "error": "Keine Untertitel verfügbar für dieses Video.",
                    "method": "youtube_transcript_api",
                }

        raw = transcript.fetch()
        segments = [
            {
                "start": round(seg["start"], 2),
                "duration": round(seg["duration"], 2),
                "text": seg["text"].strip(),
            }
            for seg in raw
        ]
        full_text = " ".join(s["text"] for s in segments)

        return {
            "success": True,
            "method": "youtube_transcript_api",
            "transcript_type": transcript_type,
            "language": transcript.language_code,
            "video_id": video_id,
            "url": url,
            "segments": segments,
            "full_text": full_text,
            "word_count": len(full_text.split()),
            "extracted_at": datetime.utcnow().isoformat() + "Z",
        }

    except TranscriptsDisabled:
        return {
            "success": False,
            "error": "Untertitel für dieses Video deaktiviert.",
            "method": "youtube_transcript_api",
        }
    except NoTranscriptFound:
        return {
            "success": False,
            "error": "Kein passendes Transkript gefunden.",
            "method": "youtube_transcript_api",
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "method": "youtube_transcript_api",
        }


# ──────────────────────────────────────────────────────────────────────────────
# Methode 2 – yt-dlp + faster-whisper (lokal, kein Cloud, beste Qualität DE)
# ──────────────────────────────────────────────────────────────────────────────

def transcribe_with_whisper(
    url: str,
    model_size: str = "medium",
    language: str = "de",
    output_dir: str | None = None,
) -> dict:
    """
    Lädt Audio via yt-dlp herunter und transkribiert lokal mit faster-whisper.

    model_size: tiny | base | small | medium | large-v3
      - 'medium' empfohlen für Deutsch (gute Balance Qualität/Speed)
      - 'large-v3' für maximale Genauigkeit

    language: ISO 639-1 Code z.B. 'de', 'en'
    """
    missing = []
    if not _check_dep("yt_dlp"):
        missing.append("yt-dlp (pip install yt-dlp)")
    if not _check_dep("faster_whisper"):
        missing.append("faster-whisper (pip install faster-whisper)")

    if missing:
        return {
            "success": False,
            "error": f"Fehlende Abhängigkeiten: {', '.join(missing)}",
            "method": "yt_dlp_whisper",
        }

    import yt_dlp
    from faster_whisper import WhisperModel

    use_temp = output_dir is None
    work_dir = tempfile.mkdtemp(prefix="valtheron_stt_") if use_temp else output_dir
    audio_path = os.path.join(work_dir, "audio.%(ext)s")

    try:
        video_id = _extract_video_id(url)

        # ── 1. Audio-Download via yt-dlp ──────────────────────────────────────
        print(f"[yt-dlp] Audio wird heruntergeladen: {url}", file=sys.stderr)
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": audio_path,
            "quiet": True,
            "no_warnings": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "wav",
                    "preferredquality": "192",
                }
            ],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "unknown")
            duration = info.get("duration", 0)
            uploader = info.get("uploader", "unknown")

        wav_file = os.path.join(work_dir, "audio.wav")
        if not os.path.exists(wav_file):
            # Fallback: suche nach heruntergeladenem Audio-File
            for f in os.listdir(work_dir):
                if f.startswith("audio."):
                    wav_file = os.path.join(work_dir, f)
                    break

        # ── 2. Lokale Transkription mit faster-whisper ────────────────────────
        print(
            f"[faster-whisper] Modell '{model_size}' wird geladen, "
            f"Sprache: {language} ...",
            file=sys.stderr,
        )
        # device="cpu" für maximale Kompatibilität; "cuda" wenn GPU verfügbar
        device = "cuda" if _has_cuda() else "cpu"
        compute_type = "int8" if device == "cpu" else "float16"

        model = WhisperModel(model_size, device=device, compute_type=compute_type)

        segments_gen, info_obj = model.transcribe(
            wav_file,
            language=language,
            beam_size=5,
            vad_filter=True,            # Voice Activity Detection – filtert Stille
            vad_parameters={"min_silence_duration_ms": 500},
        )

        segments = []
        full_text_parts = []
        for seg in segments_gen:
            text = seg.text.strip()
            segments.append(
                {
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": text,
                }
            )
            full_text_parts.append(text)
            print(f"  [{seg.start:.1f}s → {seg.end:.1f}s] {text}", file=sys.stderr)

        full_text = " ".join(full_text_parts)

        return {
            "success": True,
            "method": "yt_dlp_whisper",
            "model": model_size,
            "device": device,
            "language_detected": info_obj.language,
            "language_probability": round(info_obj.language_probability, 3),
            "video_id": video_id,
            "video_title": title,
            "uploader": uploader,
            "duration_seconds": duration,
            "url": url,
            "segments": segments,
            "full_text": full_text,
            "word_count": len(full_text.split()),
            "extracted_at": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "method": "yt_dlp_whisper",
        }
    finally:
        if use_temp:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)


def _has_cuda() -> bool:
    try:
        import ctypes
        ctypes.CDLL("libcuda.so.1")
        return True
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Haupt-Funktion – Automatische Fallback-Strategie
# ──────────────────────────────────────────────────────────────────────────────

def extract_transcript(
    url: str,
    prefer_whisper: bool = False,
    whisper_model: str = "medium",
    language: str = "de",
    output_dir: str | None = None,
) -> dict:
    """
    Extrahiert Transkript mit automatischer Fallback-Strategie:
      - Standard:      youtube-transcript-api → yt-dlp + faster-whisper
      - prefer_whisper: yt-dlp + faster-whisper direkt (ignoriert YT-Untertitel)

    Args:
        url:            YouTube URL
        prefer_whisper: True = immer Whisper nutzen (höhere Qualität)
        whisper_model:  Whisper Modellgröße ('medium' empfohlen)
        language:       Audio-Sprache ('de' für Deutsch)
        output_dir:     Optionaler Pfad für Audio-Cache (None = temp dir)
    """
    result = None

    if not prefer_whisper:
        print("[1/2] Versuche YouTube Transcript API ...", file=sys.stderr)
        result = fetch_youtube_transcript(url, preferred_langs=[language, "de", "en"])
        if result["success"]:
            print("[OK] Transkript via YouTube Transcript API gefunden.", file=sys.stderr)
            return result
        print(f"[WARN] Transcript API fehlgeschlagen: {result.get('error')}", file=sys.stderr)

    print("[2/2] Starte lokale Transkription mit yt-dlp + faster-whisper ...", file=sys.stderr)
    result = transcribe_with_whisper(
        url,
        model_size=whisper_model,
        language=language,
        output_dir=output_dir,
    )
    return result


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="YouTube Transcript / Speech-to-Text (lokal, privat)"
    )
    parser.add_argument("url", help="YouTube URL")
    parser.add_argument(
        "--whisper",
        action="store_true",
        help="Immer faster-whisper nutzen (ignoriert YT-Untertitel)",
    )
    parser.add_argument(
        "--model",
        default="medium",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        help="Whisper Modellgröße (Standard: medium)",
    )
    parser.add_argument(
        "--lang",
        default="de",
        help="Audio-Sprache ISO 639-1 (Standard: de)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Ausgabedatei für JSON-Transkript (Standard: stdout)",
    )
    parser.add_argument(
        "--audio-cache",
        default=None,
        help="Verzeichnis für Audio-Cache (Standard: temp dir)",
    )
    parser.add_argument(
        "--text-only",
        action="store_true",
        help="Nur den Volltext ausgeben (kein JSON)",
    )
    args = parser.parse_args()

    result = extract_transcript(
        url=args.url,
        prefer_whisper=args.whisper,
        whisper_model=args.model,
        language=args.lang,
        output_dir=args.audio_cache,
    )

    if args.text_only and result.get("success"):
        output = result["full_text"]
    else:
        output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"[OK] Transkript gespeichert: {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
