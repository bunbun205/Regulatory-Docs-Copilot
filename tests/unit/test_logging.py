import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_logging_emits_pure_json_and_honours_level() -> None:
    code = (
        "from app.core.logging import configure_logging\n"
        "configure_logging('debug')\n"
        "import structlog\n"
        "structlog.get_logger('test').debug('debug-line', answer=42)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line for line in result.stderr.splitlines() if line.strip()]
    payload = json.loads(lines[-1])
    assert payload["event"] == "debug-line"
    assert payload["level"] == "debug"
    assert payload["answer"] == 42
