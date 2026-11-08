#!/usr/bin/env bash
# Install fin-qa-eval and run the offline demo. No API keys.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
"$PYTHON" -m pip install -e ".[dev]"
"$PYTHON" -m fin_qa_eval validate
"$PYTHON" -m fin_qa_eval qc
"$PYTHON" -m fin_qa_eval grade --pred examples/predictions.jsonl
"$PYTHON" -m fin_qa_eval report --pred examples/predictions.jsonl --out examples/scoreboard.md
echo
echo "Planted bad samples are expected to fail QC (exit 1):"
set +e
"$PYTHON" -m fin_qa_eval qc --data data/fixtures/bad_samples.jsonl
code=$?
set -e
if [[ "$code" -ne 1 ]]; then
  echo "expected qc exit code 1, got $code" >&2
  exit 1
fi
echo "qc exit 1 as expected"
