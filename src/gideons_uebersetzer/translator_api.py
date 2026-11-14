"""Online-Notnagel: Übersetzung über die Mistral-API (nur nach bewusstem Einschalten).

WICHTIG (Privatsphäre): In diesem Modus wird der Buchtext an Mistral übertragen.
Er wird niemals automatisch aktiviert.
"""

from __future__ import annotations

import json
from typing import Callable

import requests

from .translator_base import CancelledError

CONNECT_TIMEOUT = 15
READ_TIMEOUT = 180


class ApiError(Exception):
    """API-Fehler mit deutscher, anzeigbarer Meldung."""


class ApiTranslator:
    def __init__(self, api_key: str, model: str, endpoint: str, temperature: float = 0.3):
        if not api_key:
            raise ApiError(
                "Es ist kein API-Schlüssel eingetragen. Bitte in den Einstellungen "
                "einen Mistral-API-Schlüssel hinterlegen oder den Offline-Modus verwenden."
            )
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.temperature = temperature

    def translate_stream(
        self,
        messages: list[dict],
        temperature: float | None = None,
        on_token: Callable[[str], None] | None = None,
        cancel_event=None,
    ) -> tuple[str, int]:
        """Übersetzt per Streaming und liefert (fertiger Text, gesendete Zeichen).

        Die Zeichenzahl ermöglicht eine nachvollziehbare Kostenschätzung.
        """
        chars_sent = sum(len(m.get("content", "")) for m in messages)
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "stream": True,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=headers,
                stream=True,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
        except requests.Timeout as exc:
            raise ApiError("Zeitüberschreitung bei der Verbindung zu Mistral. Bitte erneut versuchen.") from exc
        except requests.RequestException as exc:
            raise ApiError(f"Die Mistral-API ist nicht erreichbar: {exc}") from exc

        if response.status_code != 200:
            detail = ""
            try:
                detail = response.json().get("message", "") or response.text[:200]
            except ValueError:
                detail = response.text[:200]
            if response.status_code == 401:
                msg = "Der API-Schlüssel wurde von Mistral abgelehnt (HTTP 401). Bitte Schlüssel prüfen."
            elif response.status_code == 429:
                msg = "Zu viele Anfragen bei Mistral (HTTP 429). Bitte kurz warten und erneut versuchen."
            elif response.status_code >= 500:
                msg = f"Mistral-Serverproblem (HTTP {response.status_code}). Bitte später erneut versuchen."
            else:
                msg = f"API-Fehler (HTTP {response.status_code}): {detail}"
            response.close()
            raise ApiError(msg)

        parts: list[str] = []
        try:
            for raw_line in response.iter_lines(decode_unicode=True):
                if cancel_event is not None and cancel_event.is_set():
                    raise CancelledError("Übersetzung abgebrochen.")
                if not raw_line:
                    continue
                line = raw_line.strip()
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except ValueError:
                    continue
                choices = event.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                text = delta.get("content") or ""
                if text:
                    parts.append(text)
                    if on_token is not None:
                        on_token(text)
        except requests.Timeout as exc:
            raise ApiError("Zeitüberschreitung während der Übertragung von Mistral.") from exc
        except requests.RequestException as exc:
            raise ApiError(f"Die Verbindung zu Mistral wurde unterbrochen: {exc}") from exc
        finally:
            response.close()

        return "".join(parts).strip(), chars_sent

    def translate(self, messages: list[dict], cancel_event=None) -> tuple[str, int]:
        return self.translate_stream(messages, on_token=None, cancel_event=cancel_event)
