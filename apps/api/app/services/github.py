from __future__ import annotations

import os
import re
import asyncio
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

import httpx

CODE_EXTS = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".java", ".go", ".rs",
    ".php", ".rb", ".kt", ".swift", ".sql", ".md", ".json", ".yaml", ".yml",
    ".css", ".scss", ".html", ".vue", ".svelte", ".xml", ".toml"
}
IGNORE = {
    "node_modules", ".next", "dist", "build", "coverage", ".git", "venv", ".venv",
    "vendor", "target", "__pycache__", ".turbo", ".cache", "bin", "obj"
}
MAX_FILES = 80
MAX_FETCH = 60
MAX_FILE_BYTES = 80_000


def _language_from_path(path: str) -> str:
    ext = PurePosixPath(path).suffix.lower()
    return {
        ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript", ".jsx": "JavaScript",
        ".py": "Python", ".java": "Java", ".go": "Go", ".rs": "Rust", ".php": "PHP",
        ".rb": "Ruby", ".kt": "Kotlin", ".swift": "Swift", ".sql": "SQL", ".css": "CSS",
        ".scss": "SCSS", ".html": "HTML", ".vue": "Vue", ".svelte": "Svelte", ".md": "Markdown",
        ".json": "JSON", ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML", ".xml": "XML"
    }.get(ext, "Other")


class GitHubIngestor:
    def __init__(self) -> None:
        self.token = os.getenv("GITHUB_TOKEN", "")
        self.headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Codebase-Intelligence/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"

    @staticmethod
    def parse(url: str) -> tuple[str, str]:
        raw = url.strip()
        if not raw.startswith("http"):
            raw = f"https://github.com/{raw.lstrip('/')}"
        parsed = urlparse(raw)
        if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
            raise ValueError("Only public github.com repositories are supported.")
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) < 2:
            raise ValueError("Expected a URL like https://github.com/owner/repository")
        return parts[0], parts[1].removesuffix(".git")

    @staticmethod
    def keep(path: str) -> bool:
        parts = set(PurePosixPath(path).parts)
        filename = PurePosixPath(path).name.lower()
        if parts & IGNORE:
            return False
        if filename in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}:
            return False
        return PurePosixPath(path).suffix.lower() in CODE_EXTS or filename in {"Dockerfile", "Makefile"}

    async def analyze(self, url: str) -> dict[str, Any]:
        owner, repo = self.parse(url)
        async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
            repo_meta = await self._get_json(client, f"https://api.github.com/repos/{owner}/{repo}")
            branch = repo_meta.get("default_branch", "main")
            tree_data = await self._get_json(
                client,
                f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
            )
            raw_tree = tree_data.get("tree", [])
            files = [x["path"] for x in raw_tree if x.get("type") == "blob" and self.keep(x["path"])]
            files = files[:MAX_FILES]

            async def fetch_file(path: str) -> dict[str, Any] | None:
                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
                try:
                    response = await client.get(raw_url)
                    if response.status_code != 200:
                        return None
                    text = response.text[:MAX_FILE_BYTES]
                    return {
                        "path": path,
                        "text": text,
                        "language": _language_from_path(path),
                        "lines": max(1, text.count("\n") + 1),
                    }
                except httpx.HTTPError:
                    return None

            fetched = await asyncio.gather(*(fetch_file(path) for path in files[:MAX_FETCH]))
            contents = [item for item in fetched if item is not None]

            commits = await self._get_commits(client, owner, repo, branch)
            changes = await self._get_changes(client, owner, repo, commits)

        languages = self.language_breakdown(contents)
        technologies = self.detect_technologies(files, contents, repo_meta.get("language"))
        graph = self.build_dependency_graph(contents)
        return {
            "repo": {
                "owner": owner,
                "name": repo,
                "full_name": f"{owner}/{repo}",
                "url": f"https://github.com/{owner}/{repo}",
                "branch": branch,
                "private": bool(repo_meta.get("private")),
                "stars": repo_meta.get("stargazers_count", 0),
                "forks": repo_meta.get("forks_count", 0),
                "open_issues": repo_meta.get("open_issues_count", 0),
                "description": repo_meta.get("description") or "No repository description provided.",
                "topics": repo_meta.get("topics", []),
                "default_branch": branch,
            },
            "files": files,
            "contents": contents,
            "file_count": len(files),
            "indexed_files": len(contents),
            "total_lines": sum(item["lines"] for item in contents),
            "languages": languages,
            "technologies": technologies,
            "graph": graph,
            "commits": commits,
            "changes": changes,
            "analysis": self.make_analysis(contents, graph, technologies, languages, repo_meta),
            "tree_sha": tree_data.get("sha"),
        }

    async def _get_json(self, client: httpx.AsyncClient, url: str) -> dict[str, Any]:
        response = await client.get(url, headers=self.headers)
        if response.status_code == 403:
            raise ValueError("GitHub API rate limit reached. Add GITHUB_TOKEN to .env and retry.")
        if response.status_code == 404:
            raise ValueError("Repository not found or not publicly accessible.")
        response.raise_for_status()
        return response.json()

    async def _get_commits(self, client: httpx.AsyncClient, owner: str, repo: str, branch: str) -> list[dict[str, Any]]:
        try:
            data = await self._get_json(client, f"https://api.github.com/repos/{owner}/{repo}/commits?sha={branch}&per_page=8")
        except Exception:
            return []
        return [
            {
                "sha": c.get("sha", "")[:7],
                "message": (c.get("commit", {}).get("message") or "").split("\n")[0],
                "author": c.get("commit", {}).get("author", {}).get("name") or c.get("author", {}).get("login") or "Unknown",
                "date": c.get("commit", {}).get("author", {}).get("date"),
            }
            for c in data[:8]
        ]

    async def _get_changes(self, client: httpx.AsyncClient, owner: str, repo: str, commits: list[dict[str, Any]]) -> dict[str, Any]:
        if len(commits) < 2:
            return {"from": None, "to": None, "files": []}
        try:
            compare = await self._get_json(
                client,
                f"https://api.github.com/repos/{owner}/{repo}/compare/{commits[1]['sha']}...{commits[0]['sha']}",
            )
        except Exception:
            return {"from": commits[1], "to": commits[0], "files": []}
        files = []
        for item in compare.get("files", [])[:40]:
            files.append({
                "filename": item.get("filename"),
                "status": item.get("status"),
                "additions": item.get("additions", 0),
                "deletions": item.get("deletions", 0),
                "changes": item.get("changes", 0),
            })
        return {"from": commits[1], "to": commits[0], "files": files}

    @staticmethod
    def language_breakdown(contents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for item in contents:
            lang = item["language"]
            counts[lang] = counts.get(lang, 0) + 1
        total = sum(counts.values()) or 1
        return sorted(
            [{"name": name, "files": count, "share": round(count / total * 100, 1)} for name, count in counts.items()],
            key=lambda x: x["files"], reverse=True,
        )

    @staticmethod
    def detect_technologies(files: list[str], contents: list[dict[str, Any]], primary: str | None) -> list[str]:
        tech: set[str] = set()
        if primary:
            tech.add(primary)
        paths = "\n".join(files).lower()
        snippets = "\n".join(c["text"][:6000] for c in contents).lower()
        checks = {
            "Next.js": "next.config" in paths or 'from \"next/' in snippets or "from 'next/" in snippets,
            "React": any(f.endswith((".tsx", ".jsx")) for f in files) or "react" in snippets,
            "TypeScript": any(f.endswith((".ts", ".tsx")) for f in files),
            "Node.js": "package.json" in paths and ("express" in snippets or "node" in snippets),
            "Python": any(f.endswith(".py") for f in files),
            "FastAPI": "fastapi" in snippets,
            "Django": "django" in snippets,
            "PostgreSQL": "postgres" in snippets or "postgresql" in snippets,
            "MongoDB": "mongodb" in snippets or "mongoose" in snippets,
            "Prisma": "prisma" in snippets,
            "Redis": "redis" in snippets,
            "Docker": "dockerfile" in paths or "docker-compose" in paths or "docker" in snippets,
            "Tailwind": "tailwind" in snippets or "tailwind.config" in paths,
            "LangChain": "langchain" in snippets,
            "OpenAI": "openai" in snippets,
        }
        for name, enabled in checks.items():
            if enabled:
                tech.add(name)
        return sorted(tech)

    @staticmethod
    def build_dependency_graph(contents: list[dict[str, Any]]) -> dict[str, Any]:
        paths = {c["path"] for c in contents}
        nodes = [
            {
                "id": str(idx),
                "label": PurePosixPath(item["path"]).name,
                "path": item["path"],
                "language": item["language"],
            }
            for idx, item in enumerate(contents)
        ]
        node_by_path = {n["path"]: n["id"] for n in nodes}

        def resolve(source_path: str, raw: str) -> str | None:
            if not (raw.startswith(".") or raw.startswith("/")):
                return None
            base = PurePosixPath(source_path).parent
            candidate = str((base / raw).as_posix()).lstrip("/")
            variants = [candidate]
            suffixes = [".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".py", ".java", ".go", ".rs"]
            if not PurePosixPath(candidate).suffix:
                variants.extend(candidate + ext for ext in suffixes)
                variants.extend(candidate + "/index" + ext for ext in suffixes)
            for value in variants:
                if value in paths:
                    return value
            return None

        edges: list[dict[str, str]] = []
        for idx, item in enumerate(contents):
            text = item["text"]
            imports = re.findall(r"(?:from|import)\s+['\"]([^'\"]+)['\"]", text)
            imports += re.findall(r"(?:require\(|import\()[\s]*['\"]([^'\"]+)['\"]", text)
            for raw in imports:
                target_path = resolve(item["path"], raw)
                if target_path and target_path != item["path"]:
                    edges.append({"source": str(idx), "target": node_by_path[target_path], "kind": "import"})

        dedupe = {(e["source"], e["target"], e["kind"]): e for e in edges}
        edges = list(dedupe.values())

        degree = {n["id"]: 0 for n in nodes}
        for edge in edges:
            degree[edge["source"]] += 1
            degree[edge["target"]] += 1
        for n in nodes:
            n["degree"] = degree[n["id"]]
            n["module"] = str(PurePosixPath(n["path"]).parts[0]) if len(PurePosixPath(n["path"]).parts) > 1 else "/"

        module_names = sorted({n["module"] for n in nodes})
        layers = []
        for idx, module in enumerate(module_names):
            module_nodes = [n for n in nodes if n["module"] == module]
            layers.append({
                "id": f"layer-{idx}",
                "name": module,
                "files": len(module_nodes),
                "node_ids": [n["id"] for n in module_nodes[:20]],
            })
        return {"nodes": nodes, "edges": edges, "layers": layers}

    @staticmethod
    def make_analysis(contents: list[dict[str, Any]], graph: dict[str, Any], technologies: list[str], languages: list[dict[str, Any]], meta: dict[str, Any]) -> dict[str, Any]:
        directories: dict[str, int] = {}
        for item in contents:
            parent = str(PurePosixPath(item["path"]).parent)
            if parent == ".":
                parent = "/"
            directories[parent] = directories.get(parent, 0) + 1
        modules = sorted(
            [{"name": name, "files": count} for name, count in directories.items()],
            key=lambda x: x["files"], reverse=True,
        )[:24]
        entrypoints = [
            c["path"] for c in contents
            if PurePosixPath(c["path"]).name.lower() in {
                "main.py", "app.py", "server.py", "index.ts", "index.tsx", "main.ts", "main.tsx",
                "route.ts", "route.tsx", "app.ts", "app.tsx", "page.tsx", "manage.py"
            }
        ][:15]
        services = [m["name"] for m in modules if any(x in m["name"].lower() for x in ["service", "api", "server", "worker", "backend", "frontend", "route"])][:10]
        docs = [c["path"] for c in contents if c["path"].lower().endswith(("readme.md", ".md"))][:10]
        return {
            "summary": meta.get("description") or f"{meta.get('name', 'Repository')} contains {len(contents)} indexed source and documentation files.",
            "modules": modules,
            "entrypoints": entrypoints,
            "services": services,
            "docs": docs,
            "relationships": len(graph.get("edges", [])),
            "graph_nodes": len(graph.get("nodes", [])),
            "top_language": languages[0]["name"] if languages else meta.get("language") or "Unknown",
            "architecture_notes": [
                f"Detected {len(modules)} directory-level modules.",
                f"Found {len(graph.get('edges', []))} local import relationships.",
                f"Detected {len(entrypoints)} likely application entrypoints.",
            ],
        }
