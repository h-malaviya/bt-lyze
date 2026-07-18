import argparse
import asyncio
import json

from api.app.config import get_settings
from worker.integrations.claude_sdk import ClaudeAnalyzer
from worker.integrations.deepgram import DeepgramTranscriber

SAMPLE_AUDIO_URL = "https://dpgr.am/spacewalk.wav"
SAMPLE_INTERVIEW = """
Interviewer: How would you make a background job idempotent?
Candidate: I would give each job a stable idempotency key. Before doing the side effect, the worker
would claim that key in a database transaction with a unique constraint. Retries would read the
existing result. I would also make state transitions explicit and test a crash between the external
call and the final commit.
Interviewer: What tradeoff does that create?
Candidate: It adds storage and coordination latency, but prevents duplicate effects. For high-volume
work I would expire keys only after the business retry window and monitor constraint conflicts.
"""


async def run(skip_deepgram: bool, skip_claude: bool) -> int:
    settings = get_settings()
    checks: dict[str, object] = {}

    if not skip_deepgram:
        deepgram = DeepgramTranscriber(settings.deepgram_api_key)
        response = await deepgram.transcribe_url(SAMPLE_AUDIO_URL)
        channels = response.get("results", {}).get("channels", [])
        transcript = ""
        if channels:
            alternatives = channels[0].get("alternatives", [])
            if alternatives:
                transcript = alternatives[0].get("transcript", "")
        checks["deepgram_transcription"] = {
            "ok": bool(transcript),
            "characters": len(transcript),
        }

    if not skip_claude:
        analyzer = ClaudeAnalyzer(
            oauth_token=settings.claude_code_oauth_token,
            model=settings.claude_model,
        )
        evaluation = await analyzer.analyze(SAMPLE_INTERVIEW)
        checks["claude_structured_evaluation"] = {
            "ok": True,
            "overall_score": evaluation.overall_score,
            "recommendation": evaluation.recommendation,
            "categories": len(evaluation.scores.model_dump()),
            "token_usage": evaluation.token_usage.model_dump(mode="json"),
        }

    ok = all(bool(item.get("ok")) for item in checks.values() if isinstance(item, dict))
    print(json.dumps({"ok": ok, "checks": checks}, indent=2))
    return 0 if ok else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-deepgram", action="store_true")
    parser.add_argument("--skip-claude", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.skip_deepgram, args.skip_claude)))


if __name__ == "__main__":
    main()
