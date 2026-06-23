# EviFlow

EviFlow is a multi-stage root cause analysis workflow for microservice systems. It combines signal extraction from metrics, logs, and traces, then uses an LLM-guided workflow to rank the most likely faulty components.

## Repository layout

- `run.py`: end-to-end inference entrypoint.
- `src/`: workflow construction, prompt definitions, anomaly extraction, and RCA nodes.
- `config/`: dataset metadata, keyword lists, component lists, and LLM client configuration.
- `preprocess/`: dataset preprocessing scripts for AIOPS2022, Nezha, and RCAEval.
- `data/`: placeholder directory for local raw inputs or user-managed auxiliary files.
- `outputs/`: generated prediction files at runtime. Ignored by git.
- `artifacts/`: optional workflow graph exports. Ignored by git.

## Prerequisites

- Python 3.10+
- Access to an OpenAI-compatible API or Gemini API
- Preprocessed dataset files placed under `processed_data/`

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure environment variables:

```bash
cp .env.example .env
```

At minimum, set:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_BASE_URL` when using a non-default OpenAI-compatible endpoint

## Data layout

Runtime expects preprocessed inputs under:

```text
processed_data/
  aiops2022/
  nezha/
  RCAEval/
```

Each dataset/date directory should contain the files used by the workflow, including `labels.csv`, metric CSVs, log CSVs, and trace CSVs.

This repository includes a reduced sample at `processed_data/aiops2022/2022-05-01/`. It keeps the original directory layout, but only one CSV per modality subtree and the first 10 data rows per file.

## Run inference

```bash
python run.py --dataset aiops2022 --date 2022-05-05
```

Optional flags:

- `--parallel-workers N`: run multiple cases concurrently
- `--max-cases N`: limit the number of evaluated timestamps
- `--export-graph`: export workflow diagrams into `artifacts/`
- `--output-dir DIR`: override the output directory

Predictions are written to:

```text
outputs/<dataset>/<date>/output.csv
```

## Evaluate predictions

```bash
python src/evaluate.py --dataset aiops2022 --date 2022-05-05
```

The evaluator checks `outputs/` first, then falls back to the legacy `src/output/` layout for backward compatibility.

## Notes

- This repository does not include dataset artifacts or generated outputs.
- LLM credentials must be provided through environment variables, not source code.
- `src/output/` and Python cache directories were intentionally removed from version control to keep the repository clean and reproducible.
