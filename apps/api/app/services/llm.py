from __future__ import annotations

import json
import os
import re
from typing import Any


class LLMService:
    """
    Codebase AI response service.

    Tries OpenAI first. If OpenAI is unavailable or quota is exhausted,
    automatically falls back to local repository reasoning.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()

    def _client(self):
        if not self.api_key:
            return None
        from openai import AsyncOpenAI
        return AsyncOpenAI(api_key=self.api_key)

    def _build_context(self, hits: list[dict[str, Any]], max_chars: int = 30000) -> str:
        parts = []
        total = 0

        for index, hit in enumerate(hits, start=1):
            path = hit.get("path", "unknown")
            chunk = hit.get("chunk", 0)
            score = hit.get("score", 0)
            text = hit.get("text", "")

            block = (
                f"[SOURCE {index}]\n"
                f"FILE: {path}\n"
                f"CHUNK: {chunk}\n"
                f"RELEVANCE: {score}\n"
                f"CODE:\n{text}\n"
            )

            if total + len(block) > max_chars:
                remaining = max_chars - total
                if remaining > 500:
                    parts.append(block[:remaining])
                break

            parts.append(block)
            total += len(block)

        return "\n---\n".join(parts)

    def _build_messages(self, question, context, repo_name, history):
        history_text = "\n".join(
            f"{item.get('role', 'user').upper()}: {item.get('text', '')}"
            for item in history[-8:]
            if item.get("text")
        )

        system_prompt = """
You are CODEBASE AI, a repository intelligence assistant.

Answer questions using ONLY the supplied repository evidence.

Rules:
- Never invent files, technologies, APIs, functions or architecture.
- Mention exact file paths whenever useful.
- Synthesize evidence instead of dumping snippets.
- For architecture questions explain relationships.
- For startup questions identify the actual startup chain.
- For technology questions use package files, imports and configs.
- If evidence is insufficient, explicitly say so.
- Do not use the same answer template for every question.
- Use conversation history for follow-up questions.
- Keep answers concise but technically useful.
"""

        user_prompt = f"""
Repository:
{repo_name}

Conversation history:
{history_text or "(No previous conversation)"}

Question:
{question}

Repository evidence:
{context}

Answer the question using the repository evidence.
"""

        return [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ]

    async def _openai_answer(self, question, hits, repo_name, history):
        client = self._client()
        if client is None:
            return None

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=self._build_messages(
                    question,
                    self._build_context(hits),
                    repo_name,
                    history,
                ),
                temperature=0.1,
                max_tokens=1200,
            )

            if not response.choices:
                return None

            answer = response.choices[0].message.content
            return answer.strip() if answer else None

        except Exception as exc:
            print(
                f"[CODEBASE AI] OpenAI unavailable: "
                f"{type(exc).__name__}: {exc}"
            )
            return None

    @staticmethod
    def _clean_path(path: str) -> str:
        return path.replace("\\", "/")

    @staticmethod
    def _file_name(path: str) -> str:
        return path.replace("\\", "/").split("/")[-1].lower()

    @staticmethod
    def _tokens(text: str) -> set[str]:
        stopwords = {
            "the", "and", "are", "what", "where", "which", "how",
            "does", "this", "that", "with", "from", "into", "used",
            "use", "main", "show", "tell", "give", "application",
            "repository", "repo",
        }
        return {
            token for token in re.findall(
                r"[a-zA-Z_][a-zA-Z0-9_]{2,}",
                text.lower(),
            )
            if token not in stopwords
        }

    @staticmethod
    def _question_type(question: str) -> str:
        q = question.lower()

        if any(x in q for x in (
            "entrypoint", "entry point", "startup", "bootstrap",
            "main server", "how does the application start",
        )):
            return "startup"

        if any(x in q for x in (
            "technology", "technologies", "tech stack", "stack",
            "framework", "language", "dependencies",
        )):
            return "technology"

        if any(x in q for x in (
            "api", "endpoint", "endpoints", "route", "routes",
        )):
            return "api"

        if any(x in q for x in (
            "database", "db", "mongodb", "mysql", "postgres",
            "schema", "model",
        )):
            return "database"

        if any(x in q for x in (
            "auth", "authentication", "login", "signup", "register",
            "jwt", "token",
        )):
            return "authentication"

        if any(x in q for x in ("dependency", "depends", "imports", "import")):
            return "dependency"

        if any(x in q for x in (
            "flow", "works", "workflow", "process", "how does", "explain",
        )):
            return "flow"

        return "general"

    @staticmethod
    def _detect_technology(path: str, text: str) -> list[str]:
        combined = path.lower() + "\n" + text.lower()
        technologies = []

        signatures = [
            ("Express.js", ["express", "express()"]),
            ("React", ["from 'react'", 'from "react"', "reactdom"]),
            ("Node.js", ["require(", "process.env", "package.json"]),
            ("Vite", ["vite.config", "vite/"]),
            ("Next.js", ["next.config", "next/", "next("]),
            ("MongoDB", ["mongoose", "mongodb"]),
            ("PostgreSQL", ["postgres", "postgresql", "pg"]),
            ("MySQL", ["mysql"]),
            ("Prisma", ["@prisma/client", "prisma"]),
            ("JWT", ["jsonwebtoken", "jwt"]),
            ("Axios", ["axios"]),
            ("Redux", ["redux", "@reduxjs"]),
            ("Tailwind CSS", ["tailwind"]),
            ("Python", [".py"]),
            ("FastAPI", ["fastapi", "from fastapi"]),
            ("Flask", ["flask"]),
            ("Django", ["django"]),
            ("TypeScript", [".ts", ".tsx"]),
            ("JavaScript", [".js", ".jsx"]),
            ("Docker", ["dockerfile", "docker-compose"]),
        ]

        for name, markers in signatures:
            if any(marker in combined for marker in markers):
                technologies.append(name)

        return technologies

    @staticmethod
    def _extract_imports(text: str) -> list[str]:
        imports = []
        patterns = [
            r"^\s*import\s+.+?\s+from\s+['\"]([^'\"]+)['\"]",
            r"^\s*import\s+['\"]([^'\"]+)['\"]",
            r"require\(\s*['\"]([^'\"]+)['\"]\s*\)",
            r"^\s*from\s+([a-zA-Z0-9_.-]+)\s+import",
        ]

        for line in text.splitlines():
            for pattern in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    if value not in imports:
                        imports.append(value)
                    break

        return imports[:12]

    @staticmethod
    def _extract_routes(text: str) -> list[str]:
        routes = []
        pattern = (
            r"(?:app|router)\.(get|post|put|patch|delete)"
            r"\s*\(\s*['\"]([^'\"]+)"
        )

        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = f"{match.group(1).upper()} {match.group(2)}"
            if value not in routes:
                routes.append(value)

        return routes[:20]

    @staticmethod
    def _has_startup_signal(path: str, text: str) -> bool:
        filename = path.lower().split("/")[-1]

        if filename in {
            "server.js", "server.ts", "server.jsx", "server.tsx",
            "main.py", "main.js", "main.ts", "index.js", "index.ts",
            "app.js", "app.ts",
        }:
            return True

        return any(signal in text for signal in (
            "app.listen(", "uvicorn.run(", "createapp(",
            "fastapi(", "root.render(", "ReactDOM.createRoot",
        ))

    def _local_startup_answer(self, hits):
        candidates = [
            hit for hit in hits
            if self._has_startup_signal(
                self._clean_path(str(hit.get("path", ""))),
                str(hit.get("text", "")),
            )
        ] or hits[:5]

        lines = ["**Main startup / entrypoint evidence:**", ""]

        for hit in candidates[:5]:
            path = self._clean_path(str(hit.get("path", "")))
            text = str(hit.get("text", ""))
            signals = []

            if "app.listen(" in text:
                signals.append("contains an Express/Node server listener")
            if "uvicorn" in text.lower():
                signals.append("contains a Uvicorn/FastAPI startup signal")
            if "express(" in text.lower():
                signals.append("initializes an Express application")

            if not signals:
                signals.append("was retrieved as relevant startup evidence")

            lines.append(f"- `{path}` — " + "; ".join(signals) + ".")

        lines += [
            "",
            "**Startup interpretation:**",
            "The retrieved evidence points to the files above as the "
            "startup layer. The exact launch command should be confirmed "
            "from package.json, README or deployment configuration.",
        ]

        return "\n".join(lines)

    def _local_api_answer(self, hits):
        route_files = {}

        for hit in hits:
            path = self._clean_path(str(hit.get("path", "")))
            text = str(hit.get("text", ""))
            routes = self._extract_routes(text)

            if (
                "route" in path.lower()
                or "routes" in path.lower()
                or "api" in path.lower()
                or "controller" in path.lower()
                or routes
            ):
                route_files.setdefault(path, []).extend(routes)

        if not route_files:
            return (
                "**API evidence found:**\n\n"
                + "\n".join(
                    f"- `{self._clean_path(str(hit.get('path', ''))).strip()}`"
                    for hit in hits[:6]
                )
                + "\n\nNo explicit route declaration was detected in "
                "the retrieved chunks."
            )

        lines = ["**Main API entrypoints / route files:**", ""]

        for path, routes in list(route_files.items())[:8]:
            lines.append(f"- `{path}`")
            unique_routes = list(dict.fromkeys(routes))
            for route in unique_routes[:8]:
                lines.append(f"  - `{route}`")

        lines += [
            "",
            "These files are the strongest API evidence returned for "
            "the question; routes are shown only when detected directly "
            "in the retrieved source.",
        ]

        return "\n".join(lines)

    def _local_technology_answer(self, hits):
        file_technologies = {}

        for hit in hits:
            path = self._clean_path(str(hit.get("path", "")))
            text = str(hit.get("text", ""))
            technologies = self._detect_technology(path, text)

            if technologies:
                file_technologies[path] = technologies

        if not file_technologies:
            return (
                "I couldn't confidently identify technologies from "
                "the retrieved repository evidence."
            )

        all_technologies = []
        for technologies in file_technologies.values():
            for technology in technologies:
                if technology not in all_technologies:
                    all_technologies.append(technology)

        lines = [
            "**Technologies detected from the repository:**",
            "",
            ", ".join(f"`{x}`" for x in all_technologies),
            "",
            "**Where they appear:**",
        ]

        for path, technologies in list(file_technologies.items())[:10]:
            lines.append(f"- `{path}` → " + ", ".join(technologies))

        return "\n".join(lines)

    def _local_dependency_answer(self, hits):
        lines = ["**Dependency evidence:**", ""]
        found = False

        for hit in hits[:10]:
            path = self._clean_path(str(hit.get("path", "")))
            imports = self._extract_imports(str(hit.get("text", "")))

            if not imports:
                continue

            found = True
            lines.append(f"### `{path}`")
            for item in imports:
                lines.append(f"- imports `{item}`")
            lines.append("")

        if not found:
            return (
                "No explicit import relationships were detected in "
                "the retrieved repository evidence."
            )

        return "\n".join(lines)

    def _local_auth_answer(self, hits):
        keywords = (
            "auth", "login", "register", "signup", "jwt",
            "token", "password", "bcrypt", "user",
        )

        matches = []

        for hit in hits:
            path = self._clean_path(str(hit.get("path", "")))
            text = str(hit.get("text", ""))
            lower = path.lower() + "\n" + text.lower()

            found = [k for k in keywords if k in lower]

            if found:
                matches.append((path, list(dict.fromkeys(found))))

        if not matches:
            return (
                "I couldn't find enough authentication-related evidence "
                "in the retrieved repository chunks."
            )

        lines = ["**Authentication-related files:**", ""]
        for path, signals in matches[:8]:
            lines.append(
                f"- `{path}` — signals: "
                + ", ".join(f"`{x}`" for x in signals)
            )

        return "\n".join(lines)

    def _local_general_answer(self, question, hits):
        lines = [
            f"Based on the indexed evidence, the most relevant files "
            f"for **{question}** are:",
            "",
        ]

        for hit in hits[:8]:
            path = self._clean_path(str(hit.get("path", "")))
            text = str(hit.get("text", ""))
            technologies = self._detect_technology(path, text)
            imports = self._extract_imports(text)
            routes = self._extract_routes(text)

            description = []

            if technologies:
                description.append("signals: " + ", ".join(technologies[:4]))
            if imports:
                description.append(f"{len(imports)} detected imports")
            if routes:
                description.append(f"{len(routes)} detected API routes")
            if not description:
                description.append("relevant repository evidence")

            lines.append(f"- `{path}` — " + "; ".join(description))

        lines += [
            "",
            "The local analysis engine is being used because the "
            "external LLM is unavailable. Claims are limited to indexed "
            "repository evidence.",
        ]

        return "\n".join(lines)

    def _local_answer(self, question, hits):
        intent = self._question_type(question)

        if intent == "startup":
            return self._local_startup_answer(hits)
        if intent == "api":
            return self._local_api_answer(hits)
        if intent == "technology":
            return self._local_technology_answer(hits)
        if intent == "dependency":
            return self._local_dependency_answer(hits)
        if intent == "authentication":
            return self._local_auth_answer(hits)

        return self._local_general_answer(question, hits)

    async def answer(
        self,
        question: str,
        hits: list[dict[str, Any]],
        repo_name: str = "this repository",
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:

        question = question.strip()
        history = history or []

        if not question:
            return {
                "answer": "Please enter a question about the repository.",
                "mode": "local",
            }

        if not hits:
            return {
                "answer": (
                    f"I couldn't find enough indexed evidence in "
                    f"`{repo_name}` to answer that reliably."
                ),
                "mode": "local",
            }

        ai_answer = await self._openai_answer(
            question=question,
            hits=hits,
            repo_name=repo_name,
            history=history,
        )

        if ai_answer:
            return {"answer": ai_answer, "mode": "llm"}

        return {
            "answer": self._local_answer(question, hits),
            "mode": "local",
        }

    async def file_summary(self, path: str, text: str, repo_name: str):
        client = None

        try:
            client = self._client()
        except Exception:
            client = None

        if client:
            prompt = f"""
Analyze this source file.

Repository: {repo_name}
File: {path}

Return JSON with exactly:
{{
  "responsibility": "short description",
  "summary": "developer-friendly explanation",
  "highlights": [
    "concrete observation",
    "concrete observation",
    "concrete observation"
  ]
}}

Use only the supplied source. Do not invent behavior.

SOURCE:
{text[:20000]}
"""

            try:
                response = await client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "Return valid JSON only."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    response_format={"type": "json_object"},
                )

                data = json.loads(
                    response.choices[0].message.content or "{}"
                )

                return {
                    "responsibility": data.get(
                        "responsibility",
                        f"Source file `{path}`.",
                    ),
                    "summary": data.get(
                        "summary",
                        "No summary was generated.",
                    ),
                    "highlights": data.get("highlights", []),
                }

            except Exception as exc:
                print(
                    f"[CODEBASE AI] File summary fallback: "
                    f"{type(exc).__name__}: {exc}"
                )

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        imports = self._extract_imports(text)
        routes = self._extract_routes(text)
        technologies = self._detect_technology(path, text)

        if routes:
            responsibility = f"`{path}` contains API route definitions."
        elif self._has_startup_signal(path, text):
            responsibility = f"`{path}` appears to participate in application startup."
        elif imports:
            responsibility = f"`{path}` contains code with external/internal dependencies."
        else:
            responsibility = f"`{path}` is a source/configuration file in `{repo_name}`."

        highlights = []

        if technologies:
            highlights.append(
                "Detected technologies: " + ", ".join(technologies[:8])
            )
        if imports:
            highlights.append(
                "Imports: " + ", ".join(f"`{x}`" for x in imports[:8])
            )
        if routes:
            highlights.append(
                "Routes: " + ", ".join(f"`{x}`" for x in routes[:8])
            )

        if not highlights:
            highlights.append(f"{len(lines)} non-empty lines were indexed.")

        return {
            "responsibility": responsibility,
            "summary": (
                f"The file contains approximately {len(lines)} non-empty "
                f"lines and {len(imports)} detected imports."
            ),
            "highlights": highlights,
        }
