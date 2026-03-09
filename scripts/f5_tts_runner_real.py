from __future__ import annotations

import argparse
import json
import shutil
import traceback
import wave
from pathlib import Path
from typing import Any


def _fail(message: str, *, details: str | None = None, code: int = 2) -> int:
    print(f"ERROR: {message}")
    if details:
        print(details)
    return code


def _load_payload(payload_path: Path) -> dict[str, Any]:
    raw = payload_path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Payload must be a JSON object.")
    return data


def _save_wav_fallback(output_path: Path, waveform: Any, sample_rate: int) -> None:
    # Minimal dependency fallback: write PCM16 mono via stdlib wave.
    if hasattr(waveform, "tolist"):
        samples = waveform.tolist()
    else:
        samples = waveform

    if isinstance(samples, list) and samples and isinstance(samples[0], list):
        samples = samples[0]

    pcm = bytearray()
    for sample in samples:
        value = float(sample)
        value = max(-1.0, min(1.0, value))
        int16 = int(value * 32767.0)
        pcm.extend(int16.to_bytes(2, byteorder="little", signed=True))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(pcm))


def _save_audio(output_path: Path, waveform: Any, sample_rate: int) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Some runtime versions may return raw WAV bytes instead of numeric arrays.
    if isinstance(waveform, (bytes, bytearray)):
        data = bytes(waveform)
        if data.startswith(b"RIFF"):
            output_path.write_bytes(data)
            return
        raise RuntimeError("Audio result is bytes but not a WAV stream (missing RIFF header).")

    # Some runtime versions may return an audio file path.
    if isinstance(waveform, str):
        src = Path(waveform)
        if src.exists():
            shutil.copyfile(src, output_path)
            return

    try:
        import soundfile as sf  # type: ignore

        sf.write(str(output_path), waveform, sample_rate)
        return
    except Exception:
        _save_wav_fallback(output_path, waveform, sample_rate)


def _validate_output_wav(output_path: Path) -> None:
    with wave.open(str(output_path), "rb") as wav_file:
        frame_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()

    if frame_rate <= 0:
        raise RuntimeError("Generated WAV has invalid sample rate.")

    duration_seconds = frame_count / frame_rate
    if duration_seconds < 0.5:
        raise RuntimeError(
            f"Generated WAV is too short ({duration_seconds:.2f}s). Check reference transcript/audio quality."
        )


def _call_f5_api(model_id: str, ref_audio: Path, ref_text: str | None, target_text: str) -> tuple[Any, int]:
    from f5_tts.api import F5TTS  # type: ignore

    if not (ref_text or "").strip():
        raise RuntimeError(
            "Reference transcript is empty. For reliable Russian voice cloning, upload profile with transcript."
        )

    ctor_attempts = [
        {"model": model_id, "device": "cpu"},
        {"model_name": model_id, "device": "cpu"},
        {"device": "cpu"},
        {},
    ]

    last_error: Exception | None = None
    tts = None
    for kwargs in ctor_attempts:
        try:
            tts = F5TTS(**kwargs)
            break
        except Exception as exc:  # pragma: no cover - runtime integration surface
            last_error = exc
            continue

    if tts is None:
        raise RuntimeError(f"Could not initialize F5TTS: {last_error}")

    infer_method = None
    for candidate in ("infer", "synthesize", "tts"):
        if hasattr(tts, candidate):
            infer_method = getattr(tts, candidate)
            break

    if infer_method is None:
        raise RuntimeError("F5TTS object does not expose a known inference method.")

    infer_attempts = [
        {
            "ref_file": str(ref_audio),
            "ref_text": ref_text or "",
            "gen_text": target_text,
        },
        {
            "reference_audio": str(ref_audio),
            "reference_text": ref_text or "",
            "text": target_text,
        },
        {
            "reference_audio_path": str(ref_audio),
            "reference_text": ref_text or "",
            "target_text": target_text,
        },
    ]

    infer_error: Exception | None = None
    for kwargs in infer_attempts:
        try:
            result = infer_method(**kwargs)
            break
        except TypeError as exc:
            infer_error = exc
            continue
    else:
        raise RuntimeError(f"Could not call F5TTS inference method with supported signatures: {infer_error}")

    # Common shapes observed in F5-based APIs: (wav, sr, *rest) or dict/object.
    if isinstance(result, tuple):
        if len(result) >= 2:
            return result[0], int(result[1])
        raise RuntimeError("F5-TTS result tuple is missing sample rate.")

    if isinstance(result, dict):
        if result.get("audio_path"):
            return str(result["audio_path"]), int(result.get("sample_rate") or result.get("sr") or 24000)
        wav = result.get("audio") or result.get("wav")
        sr = result.get("sample_rate") or result.get("sr") or 24000
        if wav is None:
            raise RuntimeError("F5-TTS result dict does not contain audio data.")
        return wav, int(sr)

    if hasattr(result, "audio"):
        sr = getattr(result, "sample_rate", 24000)
        return getattr(result, "audio"), int(sr)

    raise RuntimeError("Unsupported F5-TTS result format from API.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Real F5-TTS runner bridge")
    parser.add_argument("--payload", required=True, help="Path to payload JSON from adapter")
    args = parser.parse_args()

    payload_path = Path(args.payload)
    if not payload_path.exists():
        return _fail(f"Payload file not found: {payload_path}")

    try:
        payload = _load_payload(payload_path)
    except Exception as exc:
        return _fail("Invalid payload JSON.", details=str(exc))

    model_id = str(payload.get("model_id") or "").strip() or "Misha24-10/F5-TTS_RUSSIAN"
    ref_audio = Path(str(payload.get("reference_audio_path") or ""))
    output_wav = Path(str(payload.get("output_wav_path") or ""))
    target_text = str(payload.get("target_text") or "")
    ref_text_raw = payload.get("reference_transcript")
    ref_text = str(ref_text_raw) if ref_text_raw is not None else None

    if not ref_audio.exists():
        return _fail(f"Reference audio does not exist: {ref_audio}")
    if not target_text.strip():
        return _fail("Target text is empty.")
    if not str(output_wav):
        return _fail("Output path is missing in payload.")

    try:
        wav, sr = _call_f5_api(model_id=model_id, ref_audio=ref_audio, ref_text=ref_text, target_text=target_text)
        _save_audio(output_wav, wav, sr)
    except Exception as exc:  # pragma: no cover - runtime integration surface
        tb = traceback.format_exc()
        return _fail(f"Real F5-TTS execution failed: {exc}", details=tb)

    if not output_wav.exists() or output_wav.stat().st_size == 0:
        return _fail(f"Output WAV was not created correctly: {output_wav}")

    try:
        _validate_output_wav(output_wav)
    except Exception as exc:
        return _fail(f"Output WAV validation failed: {exc}")

    print(f"F5-TTS synthesis complete. model={model_id} output={output_wav} sr={sr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
