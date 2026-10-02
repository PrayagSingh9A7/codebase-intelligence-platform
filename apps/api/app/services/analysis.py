from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any
import re


def impact_analysis(analysis_result: dict[str, Any], target: str) -> dict[str, Any]:
    contents = analysis_result.get("contents", [])
    graph = analysis_result.get("graph", {})
    needle = target.strip().lower()
    if not needle:
        needle = analysis_result.get("analysis", {}).get("entrypoints", [""])[0].lower()

    matched = [c for c in contents if needle in c["path"].lower() or needle in c["text"].lower()]
    matched_paths = {m["path"] for m in matched[:8]}
    direct: list[dict[str, Any]] = []
    for edge in graph.get("edges", []):
        src = graph["nodes"][int(edge["source"])]
        dst = graph["nodes"][int(edge["target"])]
        if dst["path"] in matched_paths:
            direct.append({"file": src["path"], "risk": "High", "reason": f"Imports or references {dst['path']}."})
    for item in matched[:5]:
        if not any(d["file"] == item["path"] for d in direct):
            direct.append({"file": item["path"], "risk": "High", "reason": "Direct match for the requested symbol or path."})
    direct = direct[:10]
    return {
        "target": target,
        "score": min(96, 38 + len(direct) * 8),
        "level": "High" if len(direct) >= 5 else "Moderate" if direct else "Low",
        "matched_files": list(matched_paths),
        "affected": direct,
        "notes": [
            "Impact is inferred from repository-local imports and textual symbol matches.",
            "Review transitive runtime behavior and external service contracts before changing a high-risk target.",
        ],
    }


def _flow_explanation(name: str, selected: list[dict[str, Any]]) -> str:
    paths = [c["path"] for c in selected[:5]]
    if name.startswith("Request"):
        return f"Likely request path inferred from route/controller/handler signals. Start with {paths[0]} and follow imports into the remaining files."
    if name.startswith("Data"):
        return f"Likely persistence path inferred from model/schema/database signals. The indexed files suggest a chain beginning around {paths[0]}."
    if name.startswith("Async"):
        return f"Likely background-processing path inferred from queue/worker/job signals. The strongest indexed nodes are {', '.join(paths[:3])}."
    return "Repository-local flow inferred from the strongest matching source files."


def build_flows(result: dict[str, Any]) -> list[dict[str, Any]]:
    contents = result.get("contents", [])
    flows = []
    patterns = [
        ("Request / API flow", ["route", "controller", "api", "handler", "endpoint"]),
        ("Data / persistence flow", ["repository", "model", "schema", "prisma", "database", "db"]),
        ("Async / worker flow", ["queue", "worker", "job", "consumer", "redis"]),
    ]
    for name, keywords in patterns:
        selected = [c for c in contents if any(k in c["path"].lower() or k in c["text"].lower() for k in keywords)][:6]
        if selected:
            flows.append({
                "name": name,
                "explanation": _flow_explanation(name, selected),
                "steps": [
                    {"id": str(i + 1).zfill(2), "label": PurePosixPath(c["path"]).name, "detail": c["path"]}
                    for i, c in enumerate(selected)
                ],
            })
    if not flows:
        selected = contents[:5]
        flows.append({"name": "Repository discovery flow", "explanation": "No conventional API/database/worker pattern was strong enough to infer a named runtime flow. These files are the highest-signal source files available for manual tracing.", "steps": [{"id": str(i + 1).zfill(2), "label": PurePosixPath(c["path"]).name, "detail": c["path"]} for i, c in enumerate(selected)]})
    return flows[:4]


def docs(result: dict[str, Any]) -> dict[str, Any]:
    repo = result["repo"]
    analysis = result["analysis"]
    languages = ", ".join(x["name"] for x in result.get("languages", [])[:6]) or "Undetected"
    technologies = ", ".join(result.get("technologies", [])) or "No frameworks detected"
    return {
        "title": f"{repo['full_name']} — Architecture Notes",
        "summary": analysis["summary"],
        "sections": [
            {"title": "Repository overview", "body": f"{repo['full_name']} · {repo['branch']} · {repo['stars']} stars · {repo['forks']} forks"},
            {"title": "Technology stack", "body": technologies},
            {"title": "Languages", "body": languages},
            {"title": "Entrypoints", "body": "\n".join(analysis.get("entrypoints", [])) or "No conventional entrypoints detected."},
            {"title": "Modules", "body": "\n".join(f"{m['name']} — {m['files']} files" for m in analysis.get("modules", [])[:12])},
        ],
    }
