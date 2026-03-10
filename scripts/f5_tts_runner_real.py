from __future__ import annotations

import argparse
import inspect
import json
import shutil
import traceback
import wave
from glob import glob
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


def _resolve_model_runtime_assets(model_id: str) -> tuple[str, str | None, str | None]:
    """Resolve constructor-friendly model args for different F5 package variants."""
    if "/" not in model_id:
        return model_id, None, None

    try:
        from huggingface_hub import snapshot_download  # type: ignore
    except Exception as exc:  # pragma: no cover - runtime integration surface
        raise RuntimeError(
            "Model id looks like HuggingFace repo but huggingface_hub is unavailable. "
            "Install huggingface_hub in the runtime environment."
        ) from exc

    repo_dir = snapshot_download(repo_id=model_id)

    ckpt_patterns = ("*.safetensors", "*.ckpt", "*.pt", "*.bin")
    ckpt_candidates: list[str] = []
    for pattern in ckpt_patterns:
        ckpt_candidates.extend(glob(str(Path(repo_dir) / "**" / pattern), recursive=True))
    ckpt_candidates = [p for p in ckpt_candidates if "/optimizer" not in p and "/events" not in p]

    if not ckpt_candidates:
        raise RuntimeError(f"Could not find checkpoint file in HF repo: {model_id}")

    def _rank_ckpt(path: str) -> tuple[int, int, str]:
        name = Path(path).name.lower()
        score = 0
        if "ema" in name:
            score -= 3
        if "model" in name or "ckpt" in name:
            score -= 2
        if "step" in name:
            score += 1
        return (score, len(name), name)

    ckpt_file = sorted(ckpt_candidates, key=_rank_ckpt)[0]

    vocab_candidates = glob(str(Path(repo_dir) / "**" / "*vocab*.txt"), recursive=True)
    if not vocab_candidates:
        vocab_candidates = glob(str(Path(repo_dir) / "**" / "*.txt"), recursive=True)
    vocab_file = sorted(vocab_candidates, key=lambda x: (len(Path(x).name), Path(x).name.lower()))[0] if vocab_candidates else None

    # Common architecture for most published F5 checkpoints.
    model_arch = "F5TTS_v1_Base"
    return model_arch, ckpt_file, vocab_file


def _call_f5_api(model_id: str, ref_audio: Path, ref_text: str | None, target_text: str) -> tuple[Any, int]:
    from f5_tts.api import F5TTS  # type: ignore

    if not (ref_text or "").strip():
        raise RuntimeError(
            "Reference transcript is empty. For reliable Russian voice cloning, upload profile with transcript."
        )

    resolved_model, ckpt_file, vocab_file = _resolve_model_runtime_assets(model_id)
    print(
        "DEBUG: resolved_model={model} ckpt_file={ckpt} vocab_file={vocab}".format(
            model=resolved_model,
            ckpt=ckpt_file or "<none>",
            vocab=vocab_file or "<none>",
        )
    )

    init_signature = inspect.signature(F5TTS.__init__)
    init_params = set(init_signature.parameters.keys())

    ctor_attempts: list[dict[str, Any]] = []

    base_kwargs: dict[str, Any] = {}
    if "device" in init_params:
        base_kwargs["device"] = "cpu"
    if "ckpt_file" in init_params and ckpt_file:
        base_kwargs["ckpt_file"] = ckpt_file
    if "vocab_file" in init_params and vocab_file:
        base_kwargs["vocab_file"] = vocab_file

    model_field_candidates = ("model", "hf_repo_id", "model_id", "repo_id")
    for field in model_field_candidates:
        if field in init_params:
            ctor_attempts.append({**base_kwargs, field: resolved_model})

    # Final fallback: only supported base kwargs (for APIs that don't expose model selector).
    if not ctor_attempts and base_kwargs:
        ctor_attempts.append(base_kwargs)

    if not ctor_attempts:
        raise RuntimeError(
            "F5TTS.__init__ does not expose supported model arguments "
            f"(available={sorted(init_params)}). Cannot enforce requested model '{model_id}' / resolved '{resolved_model}'."
        )

    last_error: Exception | None = None
    tts = None
    for kwargs in ctor_attempts:
        try:
            tts = F5TTS(**kwargs)
            print("DEBUG: ctor_kwargs_keys=" + ",".join(sorted(kwargs.keys())))
            break
        except Exception as exc:  # pragma: no cover - runtime integration surface
            last_error = exc
            continue

    if tts is None:
        raise RuntimeError(
            f"Could not initialize F5TTS with requested model '{model_id}' "
            f"using supported init args {sorted(init_params)}: {last_error}"
        )

    print(f"DEBUG: F5TTS initialized class={tts.__class__.__name__} model_id={model_id}")

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
    used_infer_kwargs: dict[str, Any] | None = None
    for kwargs in infer_attempts:
        try:
            result = infer_method(**kwargs)
            used_infer_kwargs = kwargs
            break
        except TypeError as exc:
            infer_error = exc
            continue
    else:
        raise RuntimeError(f"Could not call F5TTS inference method with supported signatures: {infer_error}")

    if used_infer_kwargs is not None:
        print("DEBUG: infer_kwargs_keys=" + ",".join(sorted(used_infer_kwargs.keys())))

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

    print(
        "DEBUG: payload model_id={model} ref_audio={ref} ref_text_len={rlen} target_len={tlen}".format(
            model=model_id,
            ref=ref_audio,
            rlen=len((ref_text or "").strip()),
            tlen=len(target_text.strip()),
        )
    )

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
