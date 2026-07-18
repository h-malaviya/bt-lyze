import asyncio
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from deepgram import DeepgramClient
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter


class DeepgramTranscriber:
    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("Deepgram API key is required")
        self._client = DeepgramClient(api_key=api_key)

    async def transcribe_url(
        self,
        audio_url: str,
        callback_url: str | None = None,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._transcribe_url, audio_url, callback_url)

    async def transcribe_file(self, audio_path: Path) -> dict[str, Any]:
        return await asyncio.to_thread(self._transcribe_file, audio_path)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=15),
        retry=retry_if_exception_type((OSError, TimeoutError)),
        reraise=True,
    )
    def _transcribe_url(self, audio_url: str, callback_url: str | None) -> dict[str, Any]:
        response = self._client.listen.v1.media.transcribe_url(
            url=audio_url,
            callback=callback_url,
            model="nova-3",
            smart_format=True,
            diarize=True,
            utterances=True,
            punctuate=True,
        )
        if hasattr(response, "model_dump"):
            return response.model_dump(mode="json")
        if hasattr(response, "to_dict"):
            return response.to_dict()
        raise TypeError("Deepgram returned an unsupported response type")

    def _transcribe_file(self, audio_path: Path) -> dict[str, Any]:
        response = self._client.listen.v1.media.transcribe_file(
            request=self._file_chunks(audio_path),
            model="nova-3",
            smart_format=True,
            diarize=True,
            utterances=True,
            punctuate=True,
        )
        if hasattr(response, "model_dump"):
            return response.model_dump(mode="json")
        if hasattr(response, "to_dict"):
            return response.to_dict()
        raise TypeError("Deepgram returned an unsupported response type")

    @staticmethod
    def _file_chunks(audio_path: Path) -> Iterator[bytes]:
        with audio_path.open("rb") as audio_file:
            while chunk := audio_file.read(1024 * 1024):
                yield chunk
