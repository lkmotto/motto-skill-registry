#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List


def resolve_bin(name: str, fallbacks: List[str]) -> str:
    found = shutil.which(name)
    if found:
        return found
    for p in fallbacks:
        if Path(p).exists():
            return p
    return name


SMITHERY_BIN = resolve_bin(
    "smithery",
    [
        r"C:\Users\lkmot\AppData\Roaming\npm\smithery.cmd",
        r"C:\Users\lkmot\AppData\Roaming\npm\smithery",
    ],
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def run(args: List[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def parse_json_or_none(s: str) -> Any:
    try:
        return json.loads(s)
    except Exception:
        return None


def parse_tool_payload(stdout: str) -> Any:
    outer = parse_json_or_none(stdout)
    if not isinstance(outer, dict):
        return outer
    if isinstance(outer.get("structuredContent"), (dict, list)):
        return outer["structuredContent"]
    content = outer.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parsed = parse_json_or_none(item["text"])
                if parsed is not None:
                    return parsed
                return item["text"]
    return outer


def tool_call(connection_id: str, tool_name: str, args: Dict[str, Any]) -> Any:
    cp = run([SMITHERY_BIN, "tool", "call", connection_id, tool_name, json.dumps(args)], timeout=240)
    if cp.returncode != 0:
        raise RuntimeError((cp.stderr or cp.stdout).strip())
    outer = parse_json_or_none(cp.stdout) or {}
    if isinstance(outer, dict) and outer.get("isError"):
        raise RuntimeError(str(outer))
    return parse_tool_payload(cp.stdout)


def stack_guess(language: str, root_paths: List[str]) -> List[str]:
    lang = (language or "").lower()
    roots = {p.lower() for p in root_paths}
    out: List[str] = []
    if "typescript" in lang or "javascript" in lang or "node" in lang:
        out.append("node")
    if "python" in lang or "pyproject.toml" in roots or "requirements.txt" in roots:
        out.append("python")
    if "html" in lang:
        out.append("static-web")
    if "package.json" in roots:
        out.append("npm")
    if ".github" in roots:
        out.append("github-actions")
    if "dockerfile" in roots:
        out.append("docker")
    if not out and language:
        out.append(language.lower())
    return sorted(set(out))


def refresh_awareness(owner: str) -> Dict[str, Any]:
    repos_payload = tool_call(
        "github",
        "search_repositories",
        {"query": f"user:{owner}", "perPage": 100, "page": 1, "minimal_output": True},
    )
    items = repos_payload.get("items", []) if isinstance(repos_payload, dict) else []

    status_text = ""
    pharaoh_ready = False
    try:
        ph = tool_call("pharaoh-pharaoh-so", "pharaoh_account", {"action": "status"})
        status_text = ph if isinstance(ph, str) else json.dumps(ph)
        pharaoh_ready = "no github app installed" not in status_text.lower()
    except Exception as e:
        status_text = f"status_error: {e}"
        pharaoh_ready = False

    repos: List[Dict[str, Any]] = []
    for repo in items:
        if not isinstance(repo, dict):
            continue
        full_name = repo.get("full_name")
        name = repo.get("name")
        if not full_name or not name:
            continue
        try:
            tree = tool_call("github", "get_repository_tree", {"owner": owner, "repo": name, "recursive": False})
            nodes = tree.get("tree", []) if isinstance(tree, dict) else []
            root_paths = [n.get("path") for n in nodes if isinstance(n, dict) and isinstance(n.get("path"), str)]
        except Exception:
            root_paths = []
        repos.append(
            {
                "full_name": full_name,
                "description": repo.get("description"),
                "language": repo.get("language"),
                "default_branch": repo.get("default_branch"),
                "updated_at": repo.get("updated_at"),
                "private": repo.get("private", False),
                "root_paths": sorted(root_paths),
                "stack_guess": stack_guess(str(repo.get("language") or ""), root_paths),
            }
        )

    return {
        "generated_at": now_iso(),
        "owner": owner,
        "repo_count": len(repos),
        "pharaoh": {
            "ready": pharaoh_ready,
            "status": status_text,
            "next_step": None
            if pharaoh_ready
            else "Install Pharaoh GitHub App and reconnect current MCP connection to enable graph-based repo awareness.",
        },
        "repos": sorted(repos, key=lambda r: r["full_name"].lower()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh GitHub code awareness index for agent reuse.")
    parser.add_argument("--owner", default="lkmotto", help="GitHub owner/org (default: lkmotto)")
    parser.add_argument(
        "--out",
        default=r"C:\Users\lkmot\tools\github_awareness_index.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    data = refresh_awareness(args.owner)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
