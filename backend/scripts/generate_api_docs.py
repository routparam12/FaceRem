#!/usr/bin/env python3
"""
Generates docs/API.md from the active FastAPI OpenAPI schema.
Usage:
    python backend/scripts/generate_api_docs.py
"""

from pathlib import Path
import sys

# Ensure backend root is on Python path
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app


def generate_markdown() -> str:
    schema = app.openapi()
    lines = [
        "# FaceAttend API Reference",
        "",
        "> Auto-generated from `app.openapi()` by `backend/scripts/generate_api_docs.py`. Do not edit manually.",
        "",
        f"**API Version:** {schema.get('info', {}).get('version', '0.1.0')}  ",
        f"**FastAPI Title:** {schema.get('info', {}).get('title', 'FaceAttend API')}",
        "",
        "## Endpoints Summary",
        "",
        "| Method | Path | Summary |",
        "| :--- | :--- | :--- |",
    ]

    paths = schema.get("paths", {})
    sorted_paths = sorted(paths.keys())

    for path in sorted_paths:
        for method, op in sorted(paths[path].items()):
            summary = op.get("summary") or op.get("description", "").split("\n")[0] or "-"
            lines.append(f"| `{method.upper()}` | `{path}` | {summary} |")

    lines.extend([
        "",
        "## Endpoint Details",
        "",
    ])

    for path in sorted_paths:
        for method, op in sorted(paths[path].items()):
            summary = op.get("summary") or op.get("description", "").split("\n")[0] or "-"
            desc = op.get("description", "").strip()
            op_id = op.get("operationId", "")

            lines.append(f"### `{method.upper()}` {path}")
            lines.append("")
            if summary and summary != "-":
                lines.append(f"**Summary:** {summary}  ")
            if op_id:
                lines.append(f"**Operation ID:** `{op_id}`  ")
            if desc and desc != summary:
                lines.append("")
                lines.append(desc)
                lines.append("")

            # Parameters
            params = op.get("parameters", [])
            if params:
                lines.append("#### Parameters")
                lines.append("")
                lines.append("| Name | In | Required | Type | Description |")
                lines.append("| :--- | :--- | :--- | :--- | :--- |")
                for p in params:
                    name = p.get("name", "")
                    p_in = p.get("in", "")
                    req = "Yes" if p.get("required") else "No"
                    p_schema = p.get("schema", {})
                    p_type = p_schema.get("type", p_schema.get("$ref", "string").split("/")[-1])
                    p_desc = p.get("description", "-")
                    lines.append(f"| `{name}` | `{p_in}` | {req} | `{p_type}` | {p_desc} |")
                lines.append("")

            # Request Body
            req_body = op.get("requestBody", {})
            if req_body:
                content = req_body.get("content", {})
                for mime, c_info in content.items():
                    schema_ref = c_info.get("schema", {}).get("$ref", "")
                    ref_name = schema_ref.split("/")[-1] if schema_ref else c_info.get("schema", {}).get("type", "object")
                    lines.append(f"**Request Body ({mime}):** `{ref_name}`  ")
                lines.append("")

            # Responses
            responses = op.get("responses", {})
            if responses:
                lines.append("#### Responses")
                lines.append("")
                lines.append("| Status Code | Description |")
                lines.append("| :--- | :--- |")
                for status_code, r_info in sorted(responses.items()):
                    r_desc = r_info.get("description", "-")
                    lines.append(f"| `{status_code}` | {r_desc} |")
                lines.append("")

            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def main():
    out_path = REPO_ROOT / "docs" / "API.md"
    content = generate_markdown()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated {out_path} ({len(content.splitlines())} lines)")


if __name__ == "__main__":
    main()

