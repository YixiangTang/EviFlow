import json
from typing import Any

from .prompt import aiops2022_prompt, nezha_prompt, rcaeval_prompt

PROMPTS_BY_DATASET = {
    "aiops2022": aiops2022_prompt,
    "nezha": nezha_prompt,
    "RCAEval": rcaeval_prompt,
    "rcaeval": rcaeval_prompt,
}


def get_dataset_prompt(dataset: str | None, prompt_key: str) -> str:
    dataset_name = (dataset or "aiops2022").strip()
    try:
        prompt_map = PROMPTS_BY_DATASET[dataset_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported dataset: {dataset_name}") from exc
    return str(prompt_map[prompt_key])


def parse_json_response(content: str) -> dict[str, Any]:
    """Parse a JSON response, allowing an optional fenced code block wrapper."""
    normalized = content.strip()
    if normalized.startswith("```"):
        lines = normalized.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        normalized = "\n".join(lines).strip()
        if normalized.lower().startswith("json"):
            normalized = normalized[4:].lstrip()

    try:
        parsed = json.loads(normalized)
    except json.JSONDecodeError as exc:
        preview = normalized[:200].replace("\n", "\\n")
        raise ValueError(f"Invalid JSON response: {exc.msg}. Content preview: {preview}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Response must be a JSON object.")
    return parsed


def parse_structured_json_response(response: Any) -> dict[str, Any]:
    """Normalize structured-output results and fall back to raw JSON parsing when needed."""
    parsed = response.get("parsed") if isinstance(response, dict) else response
    if hasattr(parsed, "model_dump"):
        parsed = parsed.model_dump()
    if isinstance(parsed, dict):
        return parsed

    raw_message = response.get("raw") if isinstance(response, dict) else None
    raw_content = getattr(raw_message, "content", "")
    if isinstance(raw_content, str) and raw_content.strip():
        return parse_json_response(raw_content)

    parsing_error = response.get("parsing_error") if isinstance(response, dict) else None
    if parsing_error is not None:
        raise ValueError(f"Failed to parse structured JSON response: {parsing_error}") from parsing_error

    raise ValueError("Structured response did not contain a parsed JSON object.")
