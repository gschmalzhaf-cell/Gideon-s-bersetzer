"""Offline-Übersetzung mit eingebettetem llama.cpp (GGUF, CUDA falls verfügbar)."""

from __future__ import annotations

import ctypes
import shutil
from pathlib import Path
from typing import Callable

from .translator_base import CancelledError


def cuda_available() -> bool:
    """Prüft, ob eine NVIDIA-GPU mit CUDA-Treiber erreichbar ist."""
    if shutil.which("nvidia-smi"):
        return True
    for dll in ("nvcuda.dll", "cudart64_13.dll", "cudart64_12.dll", "cudart64_11.dll", "cudart64_10.dll"):
        try:
            ctypes.CDLL(dll)
            return True
        except OSError:
            continue
    try:
        import llama_cpp

        return bool(llama_cpp.llama_supports_gpu_offload())
    except Exception:
        return False


class LocalTranslator:
    """Übersetzt lokal mit llama-cpp-python. Läuft komplett ohne Internet."""

    def __init__(self, model_path: str | Path, n_ctx: int = 8192, use_gpu: bool | None = None):
        from llama_cpp import Llama

        model_path = Path(model_path)
        if not model_path.is_file():
            raise FileNotFoundError(
                f"Das Übersetzungsmodell wurde nicht gefunden: {model_path}. "
                "Bitte zuerst über „Modell laden“ herunterladen."
            )
        self.model_path = model_path
        self.use_gpu = cuda_available() if use_gpu is None else use_gpu
        self.n_gpu_layers = -1 if self.use_gpu else 0
        self.llm = Llama(
            model_path=str(model_path),
            n_ctx=n_ctx,
            n_gpu_layers=self.n_gpu_layers,
            verbose=False,
        )

    @property
    def gpu_warning(self) -> str | None:
        if self.use_gpu:
            return None
        return (
            "Keine CUDA-GPU erkannt – die Übersetzung läuft auf der CPU. "
            "Das dauert deutlich länger (je nach Rechner mehrere Stunden für ein Buch)."
        )

    def translate_stream(
        self,
        messages: list[dict],
        temperature: float,
        on_token: Callable[[str], None] | None = None,
        cancel_event=None,
    ) -> str:
        """Übersetzt eine Nachrichtenkette und ruft on_token je Textstück ab (Live-Vorschau)."""
        source_chars = 0
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, str):
                source_chars += len(content)
            elif isinstance(content, list):
                source_chars += sum(len(item.get("text", "")) for item in content if isinstance(item, dict))
        max_tokens = max(1024, min(4096, int(source_chars * 1.5) + 512))
        parts: list[str] = []
        stream = self.llm.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            if cancel_event is not None and cancel_event.is_set():
                raise CancelledError("Übersetzung abgebrochen.")
            delta = chunk["choices"][0].get("delta", {})
            text = delta.get("content") or ""
            if text:
                parts.append(text)
                if on_token is not None:
                    on_token(text)
        return "".join(parts).strip()

    def translate(self, messages: list[dict], temperature: float, cancel_event=None) -> str:
        return self.translate_stream(messages, temperature, on_token=None, cancel_event=cancel_event)

    def close(self) -> None:
        try:
            del self.llm
        except Exception:
            pass
