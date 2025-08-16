# HUMAN-CODE.md

Purpose  
Write Python like a disciplined senior. Each rule raises trust and speed.

Human code activation  
- Read the task, tests, and code under change.  
- Write one failing test that proves the need.  
- State a three line plan. Wait for “Proceed”.  
- Touch the smallest surface that can pass the test.  
- Run ruff and pytest. Commit when green.

Human code thinking loop  
- Set the contract with tests.  
- Name the thing by its job.  
- Cut work into safe slices.  
- Prove progress with passing tests.  
- Remove clutter the moment it stops serving a need.

Ground rules  
1. Start with a test. Write the failing test first.  
2. Plan in three lines or less. Then code.  
3. One job per file.  
4. Name with intent. orders.py holds order logic, not helpers.  
5. Keep functions under twenty lines.  
6. Use early returns. Avoid deep nests.  
7. Pass plain data. Return plain data.  
8. Use the standard library first.  
9. Type‑hint every public function and boundary.  
10. Raise precise errors. Never mute exceptions.  
11. Log facts with fields. No feelings.  
12. Docstring only for public APIs. Leave internals bare.  
13. Delete dead code when tests turn green.  
14. Commit slices under three hundred lines.  
15. Run ruff and pytest before each push.

Patterns

Test first  
```python
# tests/test_total.py
def test_total_handles_empty():
    assert total([]) == 0
```

Minimal code to pass  
```python
# totals.py
from typing import Iterable

def total(items: Iterable[int]) -> int:
    return sum(items)
```

Validation and clear errors  
```python
# errors.py
class ConfigError(ValueError):
    pass
```

```python
# config.py
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigError

@dataclass(frozen=True)
class AppConfig:
    data_dir: Path

def load_config(env: dict[str, str]) -> AppConfig:
    raw = env.get('DATA_DIR')
    if not raw:
        raise ConfigError('DATA_DIR is missing')
    path = Path(raw)
    if not path.exists():
        raise ConfigError(f'data dir not found: {path}')
    return AppConfig(data_dir=path)
```

Logging facts  
```python
# logger.py
import logging

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = '%(asctime)s %(levelname)s %(name)s %(message)s'
        handler.setFormatter(logging.Formatter(fmt))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
```

```python
# service.py
from typing import Sequence
from .logger import get_logger

log = get_logger(__name__)

def compute_average(values: Sequence[float]) -> float:
    if not values:
        log.info('compute_average empty input size=0')
        return 0.0
    total = sum(values)
    avg = total / len(values)
    log.info('compute_average size=%d avg=%.4f', len(values), avg)
    return avg
```

CLI boundary  
```python
# cli.py
import argparse
from pathlib import Path

def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog='tool')
    parser.add_argument('--input', type=Path, required=True)
    return parser.parse_args(argv)
```

Concurrency that stays simple  
```python
# fetch.py
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable

def run_pool(tasks: Iterable[Callable[[], str]], max_workers: int = 8) -> list[str]:
    results: list[str] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = [ex.submit(t) for t in tasks]
        for fut in as_completed(futs):
            results.append(fut.result())
    return results
```

I/O boundary with plain data  
```python
# io_json.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding='utf-8'))

def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding='utf-8')
```

Project layout  
```
project/
  pyproject.toml
  src/
    app/
      __init__.py
      totals.py
      config.py
      errors.py
      io_json.py
      logger.py
      service.py
      cli.py
  tests/
    test_total.py
    test_config.py
```

Tooling

pyproject.toml  
```toml
[project]
name = "app"
version = "0.1.0"
requires-python = ">=3.11"

[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["E501"]  # let formatter handle wrapping

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"

[tool.mypy]
python_version = "3.11"
strict = true
warn_unused_ignores = true
```

Workflow

Before coding  
- Open a small task. Write one failing test.  
- State a three line plan. Example:  
  - Add total([]) case.  
  - Keep function pure.  
  - Log size and avg.  
- Wait for “Proceed”.

While coding  
- Keep each change below three hundred lines.  
- Keep functions under twenty lines.  
- Keep the public surface typed.  
- Keep state at the edges, not in helpers.  
- Keep prints out of libraries. Use logging.

Before push  
- Run ruff.  
- Run mypy.  
- Run pytest.  
- Delete dead code and comments that restate code.  
- Squash noise commits.

Commit style  
- Imperative mood.  
- Scope and change.  
- Link to ticket.  
- Examples:  
  - totals: handle empty input and add test  
  - config: validate DATA_DIR and raise ConfigError  
  - service: add average with structured logging

Review checklist  
- Tests prove the contract and edge cases.  
- Names read like intent, not mechanics.  
- Each file has one job.  
- Functions are small and pure.  
- No hidden I/O in pure code.  
- Errors are specific and helpful.  
- Logs carry fields a pager needs.  
- Types cover all public paths.  
- No TODO, no placeholder, no dead code.  
- ruff, mypy, and pytest are green.

Writing mode for all docs and PRs  
- Use short, direct sentences. Aim for 10–20 words.  
- Use active voice.  
- Use common words.  
- Use periods, commas, question marks, and colons for lists.  
- Vary sentence length. Avoid stacked clauses.  
- Link thoughts with and, but, so, then.  
- Prefer facts, numbers, and dates.  
- Ask at most one real question per page and answer it right away.  
- Do not use semicolons or em dashes.  
- Do not use corporate jargon, filler, or hedging.  
- Keep a formal, approachable tone.

Reading path  
- Python Crash Course, 3rd Ed., Eric Matthes, 2025. Basics and two projects.  
- Automate the Boring Stuff with Python, Al Sweigart, 2025. Daily tasks.  
- Effective Python, Brett Slatkin, 2025. Ninety tips for clean code.  
- Fluent Python, 2nd Ed., Luciano Ramalho, 2025. Advanced language features.  
- Python for Data Analysis, 3rd Ed., Wes McKinney, 2025. pandas with real data.  
- Data Science from Scratch, Joel Grus, 2025. ML math with plain Python.  
- Python Cookbook, Beazley and Jones, 2025. Recipes for common jobs.

Each line serves the goal. No filler. No TODO.