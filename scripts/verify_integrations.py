import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from time import perf_counter

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

from api.app.config import get_settings
from api.app.services.dependency_health import (
    check_database,
    check_deepgram,
    check_recording_storage,
    check_supabase_auth,
)


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    latency_ms: int
    detail: str


async def check_claude() -> CheckResult:
    settings = get_settings()
    started = perf_counter()
    if not settings.claude_code_oauth_token:
        return CheckResult("claude_agent_sdk", False, 0, "not configured")

    options = ClaudeAgentOptions(
        model=settings.claude_model,
        max_turns=1,
        tools=[],
        allowed_tools=[],
        setting_sources=[],
        system_prompt="Return the exact requested text and nothing else.",
        env={"CLAUDE_CODE_OAUTH_TOKEN": settings.claude_code_oauth_token},
    )
    result: ResultMessage | None = None
    try:
        async with asyncio.timeout(90):
            async for message in query(prompt="Reply exactly CONNECTION_OK", options=options):
                if isinstance(message, ResultMessage):
                    result = message
        ok = bool(
            result
            and not result.is_error
            and result.result
            and "CONNECTION_OK" in result.result
        )
        return CheckResult(
            "claude_agent_sdk",
            ok,
            round((perf_counter() - started) * 1000),
            "authenticated" if ok else "request failed",
        )
    except Exception:
        return CheckResult(
            "claude_agent_sdk",
            False,
            round((perf_counter() - started) * 1000),
            "connection failed",
        )


async def run(skip_claude: bool) -> int:
    settings = get_settings()
    checks = [
        check_database(settings),
        check_deepgram(settings),
        check_supabase_auth(settings),
        check_recording_storage(settings),
    ]
    results = list(await asyncio.gather(*checks))
    output = [asdict(result) for result in results]
    if not skip_claude:
        output.append(asdict(await check_claude()))
    print(json.dumps({"ok": all(item["ok"] for item in output), "checks": output}, indent=2))
    return 0 if all(item["ok"] for item in output) else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-claude", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.skip_claude)))


if __name__ == "__main__":
    main()
