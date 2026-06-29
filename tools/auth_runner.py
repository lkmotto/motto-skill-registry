#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen


def now_utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def resolve_bin(name: str, fallbacks: List[str]) -> str:
    found = shutil.which(name)
    if found:
        return found
    for p in fallbacks:
        if os.path.exists(p):
            return p
    return name


SMITHERY_BIN = resolve_bin(
    "smithery",
    [
        r"C:\Users\lkmot\AppData\Roaming\npm\smithery.cmd",
        r"C:\Users\lkmot\AppData\Roaming\npm\smithery",
    ],
)
DOPPLER_BIN = resolve_bin(
    "doppler", [r"C:\Users\lkmot\AppData\Local\Programs\doppler\doppler.exe"]
)
BW_BIN = resolve_bin(
    "bw",
    [
        r"C:\Users\lkmot\AppData\Roaming\npm\bw.cmd",
        r"C:\Users\lkmot\AppData\Roaming\npm\bw",
    ],
)
NETLIFY_BIN = resolve_bin(
    "netlify",
    [
        r"C:\Users\lkmot\AppData\Roaming\npm\netlify.cmd",
        r"C:\Users\lkmot\AppData\Roaming\npm\netlify.ps1",
    ],
)
NETLIFY_DEFAULT_CLIENT_ID = (
    "d6f37de6614df7ae58664cfca524744d73807a377f5ee71f1a254f78412e3750"
)


def run_cmd(args: List[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def parse_json_or_none(value: str) -> Optional[dict]:
    try:
        return json.loads(value)
    except Exception:
        return None


def parse_tool_call_payload(stdout: str) -> dict:
    outer = parse_json_or_none(stdout) or {}
    structured = outer.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    content = outer.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parsed = parse_json_or_none(text)
                    if isinstance(parsed, dict):
                        return parsed
    return {}


def parse_tool_call_any(stdout: str) -> Any:
    outer = parse_json_or_none(stdout)
    if not isinstance(outer, dict):
        return outer
    structured = outer.get("structuredContent")
    if structured is not None:
        return structured
    result = outer.get("result")
    if result is not None:
        return result
    content = outer.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parsed = parse_json_or_none(text)
                    if parsed is not None:
                        return parsed
    return outer


def bitwarden_status() -> Optional[dict]:
    cp = run_cmd([BW_BIN, "status", "--raw"], timeout=30)
    if cp.returncode != 0:
        return None
    return parse_json_or_none(cp.stdout)


def bitwarden_get_item_by_name(name: str) -> Optional[dict]:
    cp = run_cmd([BW_BIN, "list", "items", "--search", name, "--raw"], timeout=60)
    if cp.returncode != 0:
        return None
    arr = parse_json_or_none(cp.stdout)
    if not isinstance(arr, list):
        return None
    exact = [
        x
        for x in arr
        if isinstance(x, dict)
        and str(x.get("name", "")).strip().lower() == name.strip().lower()
    ]
    if exact:
        return exact[0]
    return arr[0] if arr else None


def bitwarden_get_item_by_id(item_id: str) -> Optional[dict]:
    cp = run_cmd([BW_BIN, "get", "item", item_id, "--raw"], timeout=60)
    if cp.returncode != 0:
        return None
    obj = parse_json_or_none(cp.stdout)
    return obj if isinstance(obj, dict) else None


def bitwarden_extract_field(item: dict, field: str) -> Optional[str]:
    low = field.strip().lower()
    login = item.get("login") if isinstance(item, dict) else None
    if isinstance(login, dict):
        if low == "username":
            v = login.get("username")
            return str(v) if v else None
        if low == "password":
            v = login.get("password")
            return str(v) if v else None
        if low == "totp":
            cp = run_cmd(
                [BW_BIN, "get", "totp", item.get("id", ""), "--raw"], timeout=30
            )
            if cp.returncode == 0:
                t = cp.stdout.strip()
                return t if t else None

    fields = item.get("fields")
    if isinstance(fields, list):
        for f in fields:
            if isinstance(f, dict) and str(f.get("name", "")).strip().lower() == low:
                v = f.get("value")
                return str(v) if v is not None else None
    return None


def resolve_bitwarden_value(expr: str) -> Optional[str]:
    # Supported:
    # - bw:item:<item_name>:<field_name>
    # - bw:id:<item_id>:<field_name>
    if not expr.startswith("bw:"):
        return None
    parts = expr.split(":")
    if len(parts) < 4:
        return None
    mode = parts[1].strip().lower()
    target = parts[2].strip()
    field = ":".join(parts[3:]).strip()
    if not target or not field:
        return None

    st = bitwarden_status()
    if not st:
        return None
    state = str(st.get("status", "")).lower()
    if state not in ("unlocked", "locked", "unauthenticated"):
        return None
    if state in ("locked", "unauthenticated"):
        # Caller may have BW_SESSION set in env; bw commands can still work if unlocked in another shell is exported here.
        # We proceed and let command execution decide.
        pass

    item = None
    if mode == "item":
        item = bitwarden_get_item_by_name(target)
    elif mode == "id":
        item = bitwarden_get_item_by_id(target)
    else:
        return None

    if not isinstance(item, dict):
        return None
    return bitwarden_extract_field(item, field)


@dataclass
class RunnerContext:
    dry_run: bool
    verbose: bool

    def log(self, msg: str) -> None:
        print(msg)

    def debug(self, msg: str) -> None:
        if self.verbose:
            print(msg)


class SmitheryAdapter:
    def __init__(self, ctx: RunnerContext):
        self.ctx = ctx

    def _run(self, args: List[str], timeout: int = 90) -> subprocess.CompletedProcess:
        cmd = [SMITHERY_BIN] + args
        self.ctx.debug(f"[smithery] {' '.join(cmd)}")
        return run_cmd(cmd, timeout=timeout)

    def get_connection(self, connection_id: str) -> dict:
        cp = self._run(["mcp", "get", connection_id], timeout=60)
        if cp.returncode != 0:
            raise RuntimeError(
                f"smithery mcp get failed for {connection_id}: {cp.stderr.strip()}"
            )
        payload = parse_json_or_none(cp.stdout)
        if not isinstance(payload, dict):
            raise RuntimeError(
                f"Unable to parse connection payload for {connection_id}"
            )
        return payload

    def add_connection(
        self,
        connection_id: str,
        mcp_url: str,
        force: bool = False,
        headers: Optional[dict] = None,
    ) -> None:
        args = ["mcp", "add", mcp_url, "--id", connection_id]
        if force:
            args.append("--force")
        if headers:
            args.extend(["--headers", json.dumps(headers)])
        if self.ctx.dry_run:
            self.ctx.log(f"[dry-run] smithery {' '.join(args)}")
            return
        cp = self._run(args, timeout=120)
        if cp.returncode != 0:
            raise RuntimeError(
                f"smithery mcp add failed for {connection_id}: {cp.stderr.strip()}"
            )

    def remove_connection(self, connection_id: str) -> None:
        args = ["mcp", "remove", connection_id]
        if self.ctx.dry_run:
            self.ctx.log(f"[dry-run] smithery {' '.join(args)}")
            return
        cp = self._run(args, timeout=60)
        if cp.returncode != 0:
            raise RuntimeError(
                f"smithery mcp remove failed for {connection_id}: {cp.stderr.strip()}"
            )

    def update_headers(self, connection_id: str, headers: dict) -> None:
        args = ["mcp", "update", connection_id, "--headers", json.dumps(headers)]
        if self.ctx.dry_run:
            redacted = {k: "***" for k in headers}
            self.ctx.log(
                f"[dry-run] smithery mcp update {connection_id} --headers {json.dumps(redacted)}"
            )
            return
        cp = self._run(args, timeout=60)
        if cp.returncode != 0:
            raise RuntimeError(
                f"smithery mcp update headers failed for {connection_id}: {cp.stderr.strip()}"
            )

    def is_authorized_for_tools(self, connection_id: str) -> Tuple[bool, str]:
        cp = self._run(
            ["tool", "list", connection_id, "--flat", "--limit", "1"], timeout=60
        )
        combined = (cp.stdout or "") + "\n" + (cp.stderr or "")
        txt = combined.lower()
        if cp.returncode != 0:
            return False, combined.strip() or f"tool list failed rc={cp.returncode}"
        if "requires authorization" in txt or "auth_required" in txt:
            return False, combined.strip()
        return True, combined.strip()

    def tool_call(
        self,
        connection_id: str,
        tool_name: str,
        args: Optional[dict] = None,
        timeout: int = 120,
    ) -> Any:
        payload = args or {}
        cp = self._run(
            ["tool", "call", connection_id, tool_name, json.dumps(payload)],
            timeout=timeout,
        )
        if cp.returncode != 0:
            msg = (cp.stderr or cp.stdout or "").strip()
            raise RuntimeError(
                f"smithery tool call failed {connection_id}.{tool_name}: {msg}"
            )
        outer = parse_json_or_none(cp.stdout) or {}
        if isinstance(outer, dict) and outer.get("isError"):
            raise RuntimeError(f"{connection_id}.{tool_name} returned error: {outer}")
        return parse_tool_call_any(cp.stdout)

    def open_setup_url(self, setup_url: str) -> None:
        if self.ctx.dry_run:
            self.ctx.log(f"[dry-run] open {setup_url}")
            return
        opened = webbrowser.open(setup_url)
        if not opened:
            self.ctx.log(
                f"[warn] Could not auto-open browser. Visit manually: {setup_url}"
            )

    def poll_until_state_change(
        self,
        connection_id: str,
        from_state: str,
        timeout_sec: int,
        interval_sec: int,
    ) -> dict:
        deadline = time.time() + timeout_sec
        latest = self.get_connection(connection_id)
        while time.time() < deadline:
            status = latest.get("status", {}) or {}
            state = status.get("state")
            if state != from_state:
                return latest
            time.sleep(interval_sec)
            latest = self.get_connection(connection_id)
        return latest


class GmailAdapter:
    CODE_PATTERNS = [
        re.compile(r"\b\d{6}\b"),
        re.compile(r"\b\d{4,8}\b"),
        re.compile(r"\b[A-Z0-9]{5,10}\b"),
    ]
    URL_PATTERN = re.compile(r"https?://[^\s)>\"]+")

    def __init__(self, ctx: RunnerContext):
        self.ctx = ctx
        self._seen_message_ids: set = set()

    def fetch_messages(
        self,
        gmail_connection_id: str,
        query: str,
        max_results: int = 10,
        verbose: bool = False,
    ) -> List[dict]:
        args = {
            "query": query,
            "max_results": max_results,
            "verbose": verbose,
            "include_payload": False,
        }
        cmd = [
            SMITHERY_BIN,
            "tool",
            "call",
            gmail_connection_id,
            "fetch_emails",
            json.dumps(args),
        ]
        cp = run_cmd(cmd, timeout=120)
        if cp.returncode != 0:
            raise RuntimeError(f"Gmail fetch_emails failed: {cp.stderr.strip()}")
        payload = parse_tool_call_payload(cp.stdout)
        messages = payload.get("messages")
        if isinstance(messages, list):
            return messages
        return []

    @staticmethod
    def _sender_allowed(sender: str, allowlist: List[str]) -> bool:
        if not allowlist:
            return True
        sender_l = (sender or "").lower()
        return any(part.lower() in sender_l for part in allowlist)

    def parse_latest_otp(
        self,
        messages: List[dict],
        sender_allowlist: Optional[List[str]] = None,
        code_regex: Optional[str] = None,
    ) -> Optional[dict]:
        allowlist = sender_allowlist or []
        custom_re = re.compile(code_regex) if code_regex else None
        sortable = []
        for m in messages:
            ts = m.get("messageTimestamp") or ""
            sortable.append((ts, m))
        sortable.sort(reverse=True, key=lambda x: x[0])

        for _, msg in sortable:
            message_id = msg.get("messageId")
            if not message_id or message_id in self._seen_message_ids:
                continue
            sender = msg.get("sender", "")
            if not self._sender_allowed(sender, allowlist):
                continue
            preview = msg.get("preview") or {}
            body = (preview.get("body") or "") + "\n" + (preview.get("subject") or "")

            code = None
            if custom_re:
                found = custom_re.findall(body)
                if found:
                    code = found[0]
            if not code:
                for pat in self.CODE_PATTERNS:
                    found = pat.findall(body)
                    if found:
                        code = found[0]
                        break

            links = self.URL_PATTERN.findall(body)
            self._seen_message_ids.add(message_id)
            if code or links:
                return {
                    "message_id": message_id,
                    "sender": sender,
                    "timestamp": msg.get("messageTimestamp"),
                    "subject": preview.get("subject"),
                    "code": code,
                    "link": links[0] if links else None,
                    "confidence": "high" if code else "medium",
                }
        return None


class DopplerAdapter:
    def __init__(self, ctx: RunnerContext):
        self.ctx = ctx

    def set_secret(self, project: str, config: str, key: str, value: str) -> None:
        args = [
            DOPPLER_BIN,
            "secrets",
            "set",
            key,
            value,
            "--project",
            project,
            "--config",
            config,
            "--no-interactive",
        ]
        if self.ctx.dry_run:
            self.ctx.log(
                f"[dry-run] doppler secrets set {key} *** --project {project} --config {config}"
            )
            return
        cp = run_cmd(args, timeout=60)
        if cp.returncode != 0:
            raise RuntimeError(
                f"doppler secrets set failed for {key}: {cp.stderr.strip()}"
            )
        self.ctx.debug(cp.stdout.strip())


def rewrite_url_with_query_params(url: str, params: Dict[str, str]) -> str:
    parsed = urlparse(url)
    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    q.update(params)
    updated = parsed._replace(query=urlencode(q))
    return urlunparse(updated)


def resolve_value(
    value_expr: str, recipe: dict, runtime_values: Optional[dict] = None
) -> Optional[str]:
    if value_expr is None:
        return None
    if value_expr.startswith("env:"):
        return os.getenv(value_expr.split(":", 1)[1])
    if value_expr.startswith("literal:"):
        return value_expr.split(":", 1)[1]
    if value_expr.startswith("doppler:"):
        # format: doppler:project:config:KEY
        parts = value_expr.split(":")
        if len(parts) != 4:
            return None
        _, project, config, key = parts
        cp = run_cmd(
            [
                DOPPLER_BIN,
                "secrets",
                "get",
                key,
                "--project",
                project,
                "--config",
                config,
                "--plain",
            ],
            timeout=60,
        )
        if cp.returncode != 0:
            return None
        return cp.stdout.strip()
    if value_expr.startswith("bw:"):
        return resolve_bitwarden_value(value_expr)
    if value_expr.startswith("credentials:") or value_expr.startswith("credential:"):
        if not runtime_values:
            return None
        _, key = value_expr.split(":", 1)
        return runtime_values.get(f"credentials.{key}")
    if value_expr.startswith("acquisition:"):
        if not runtime_values:
            return None
        _, key = value_expr.split(":", 1)
        lookup = f"acquisition.{key.replace(':', '.')}"
        return runtime_values.get(lookup)
    if value_expr.startswith("collector:"):
        if not runtime_values:
            return None
        _, key = value_expr.split(":", 1)
        return runtime_values.get(key) or runtime_values.get(f"collector.{key}")
    return value_expr


def resolve_credentials(recipe: dict) -> Dict[str, str]:
    out: Dict[str, str] = {}
    cfg = recipe.get("credentials") or {}
    if not isinstance(cfg, dict):
        return out
    for key in ("username", "password", "totp", "email"):
        expr = cfg.get(key)
        if isinstance(expr, str) and expr.strip():
            v = resolve_value(expr.strip(), recipe)
            if isinstance(v, str) and v:
                out[key] = v
    return out


def get_setup_url(status: dict) -> Optional[str]:
    return status.get("setupUrl") or status.get("authorizationUrl")


def apply_input_required(
    recipe: dict,
    conn: dict,
    smithery: SmitheryAdapter,
    ctx: RunnerContext,
    runtime_values: Optional[dict] = None,
) -> None:
    status = conn.get("status") or {}
    missing = status.get("missing") or {}
    input_values = recipe.get("input_values") or {}

    missing_headers = missing.get("headers") or []
    missing_query = missing.get("query") or []

    if missing_headers:
        header_map = {}
        provided = input_values.get("headers") or {}
        for h in missing_headers:
            v = resolve_value(
                str(provided.get(h, "")), recipe, runtime_values=runtime_values
            )
            if not v:
                if ctx.dry_run:
                    ctx.log(
                        f"[dry-run] missing header value for '{h}', using placeholder"
                    )
                    v = "REQUIRED_VALUE"
                else:
                    raise RuntimeError(
                        f"Missing header value for input_required header '{h}'"
                    )
            header_map[h] = v
        smithery.update_headers(recipe["connection_id"], header_map)

    if missing_query:
        provided_q = input_values.get("query") or {}
        q_map = {}
        for q in missing_query:
            v = resolve_value(
                str(provided_q.get(q, "")), recipe, runtime_values=runtime_values
            )
            if not v:
                if ctx.dry_run:
                    ctx.log(
                        f"[dry-run] missing query value for '{q}', using placeholder"
                    )
                    v = "REQUIRED_VALUE"
                else:
                    raise RuntimeError(
                        f"Missing query value for input_required query '{q}'"
                    )
            q_map[q] = v
        current_url = conn.get("mcpUrl")
        if not current_url:
            raise RuntimeError(
                "Connection missing mcpUrl while handling input_required query fields."
            )
        rewritten = rewrite_url_with_query_params(current_url, q_map)
        ctx.log(
            f"[info] Rebuilding connection URL with required query params for {recipe['connection_id']}"
        )
        smithery.remove_connection(recipe["connection_id"])
        smithery.add_connection(recipe["connection_id"], rewritten, force=True)


def resolve_doppler_value(
    recipe: dict, otp_result: Optional[dict], runtime_values: Optional[dict] = None
) -> Optional[str]:
    doppler_cfg = recipe.get("doppler") or {}
    if "value" in doppler_cfg and isinstance(doppler_cfg["value"], str):
        return resolve_value(
            doppler_cfg["value"], recipe, runtime_values=runtime_values
        )
    value_env = doppler_cfg.get("value_env")
    if isinstance(value_env, str) and value_env:
        return os.getenv(value_env)
    if doppler_cfg.get("value_from_otp") and otp_result:
        if otp_result.get("code"):
            return otp_result["code"]
        if otp_result.get("link"):
            return otp_result["link"]
    return None


def find_key_like_values(obj: Any, path: str = "") -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            out.extend(find_key_like_values(v, p))
        return out
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(find_key_like_values(v, f"{path}[{i}]"))
        return out
    if isinstance(obj, str):
        s = obj.strip()
        p = path.lower()
        if len(s) >= 20 and (
            "key" in p
            or "token" in p
            or s.startswith(("sk_", "pk_", "cmp_", "cp_", "api_"))
        ):
            out.append((path, s))
    return out


def load_netlify_seed_token() -> Optional[str]:
    appdata = os.getenv("APPDATA")
    if not appdata:
        return None
    cfg_path = Path(appdata) / "netlify" / "Config" / "config.json"
    if not cfg_path.exists():
        return None
    try:
        payload = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    user_id = payload.get("userId")
    users = payload.get("users") if isinstance(payload.get("users"), dict) else {}
    user = users.get(user_id) if isinstance(users, dict) else None
    auth = user.get("auth") if isinstance(user, dict) else None
    token = auth.get("token") if isinstance(auth, dict) else None
    if not isinstance(token, str) or not token:
        return None
    # Read tool may redact with asterisks in output; ensure we never use an obviously redacted token literal.
    if set(token) == {"*"}:
        return None
    return token


def netlify_api_call(method_name: str, payload: dict, timeout: int = 120) -> Any:
    cp = run_cmd(
        [NETLIFY_BIN, "api", method_name, "--data", json.dumps(payload)],
        timeout=timeout,
    )
    if cp.returncode != 0:
        msg = (cp.stderr or cp.stdout).strip()
        raise RuntimeError(f"netlify api {method_name} failed: {msg}")
    out = parse_json_or_none(cp.stdout)
    if out is not None:
        return out
    return cp.stdout.strip()


def netlify_authorize_ticket(ticket_id: str, seed_token: str) -> None:
    req = Request(
        url=f"https://api.netlify.com/api/v1/oauth/tickets/{ticket_id}/authorize",
        data=b"{}",
        method="POST",
        headers={
            "Authorization": f"Bearer {seed_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(req, timeout=30) as resp:
            if getattr(resp, "status", 200) not in (200, 201, 204):
                raise RuntimeError(
                    f"ticket authorize returned status {getattr(resp, 'status', 'unknown')}"
                )
    except Exception as e:
        raise RuntimeError(f"netlify ticket authorize failed: {e}") from e


def collect_composio_project_api_key(
    smithery: SmitheryAdapter, connection_id: str
) -> dict:
    mode = "project_api_key_regenerate"
    provider = "composio"

    project_list = smithery.tool_call(connection_id, "org.owner.project.list.list", {})
    items = []
    if isinstance(project_list, dict):
        for k in ("items", "data", "projects", "result"):
            if isinstance(project_list.get(k), list):
                items = project_list[k]
                break
    elif isinstance(project_list, list):
        items = project_list
    if not items:
        raise RuntimeError(f"{provider}.{mode}: no projects returned")

    selected = items[0]
    project_id = selected.get("nano_id") or selected.get("nanoId") or selected.get("id")
    project_name = selected.get("name")
    if not project_id:
        raise RuntimeError(f"{provider}.{mode}: project id missing")

    rotated = smithery.tool_call(
        connection_id,
        "org.owner.project.regenerate_api_key.create",
        {"nano_id": project_id},
        timeout=180,
    )
    candidates = find_key_like_values(rotated)
    if not candidates:
        raise RuntimeError(f"{provider}.{mode}: no key-like value in rotate response")
    candidates.sort(
        key=lambda x: (
            0 if ("api" in x[0].lower() and "key" in x[0].lower()) else 1,
            len(x[1]),
        )
    )
    key_path, key_value = candidates[0]
    return {
        "provider": provider,
        "mode": mode,
        "value": key_value,
        "path": key_path,
        "meta": {
            "project_id": str(project_id),
            "project_name": str(project_name or ""),
        },
    }


def collect_netlify_oauth_ticket_token(
    recipe: dict, runtime_values: Optional[dict] = None
) -> dict:
    acq = recipe.get("acquisition") or {}
    params = acq.get("params") if isinstance(acq.get("params"), dict) else {}
    provider = "netlify"
    mode = "oauth_ticket_exchange"
    client_id = str(params.get("client_id") or NETLIFY_DEFAULT_CLIENT_ID)
    message = str(params.get("message") or f"auth-runner-{now_utc_iso()}")

    seed_token_expr = params.get("seed_token")
    seed_token = None
    if isinstance(seed_token_expr, str) and seed_token_expr.strip():
        seed_token = resolve_value(
            seed_token_expr.strip(), recipe, runtime_values=runtime_values
        )
    if not seed_token:
        seed_token = load_netlify_seed_token()
    if not seed_token:
        raise RuntimeError(
            f"{provider}.{mode}: missing seed token source (configure acquisition.params.seed_token or local netlify login)"
        )

    created = netlify_api_call(
        "createTicket", {"client_id": client_id, "message": message}
    )
    if not isinstance(created, dict):
        raise RuntimeError(
            f"{provider}.{mode}: createTicket returned non-object payload"
        )
    ticket_id = created.get("id")
    if not isinstance(ticket_id, str) or not ticket_id:
        raise RuntimeError(f"{provider}.{mode}: createTicket did not return ticket id")

    netlify_authorize_ticket(ticket_id, seed_token)
    exchanged = netlify_api_call("exchangeTicket", {"ticket_id": ticket_id})
    if not isinstance(exchanged, dict):
        raise RuntimeError(
            f"{provider}.{mode}: exchangeTicket returned non-object payload"
        )
    token = (
        exchanged.get("access_token")
        or exchanged.get("token")
        or exchanged.get("accessToken")
    )
    if not isinstance(token, str) or not token:
        raise RuntimeError(
            f"{provider}.{mode}: exchangeTicket did not return access token"
        )

    return {
        "provider": provider,
        "mode": mode,
        "value": token,
        "path": "access_token",
        "meta": {
            "ticket_id": ticket_id,
            "token_length": str(len(token)),
            "token_sha256_12": hashlib.sha256(token.encode("utf-8")).hexdigest()[:12],
        },
    }


def get_acquisition_config(recipe: dict) -> dict:
    acq = recipe.get("acquisition")
    if isinstance(acq, dict) and acq:
        return acq
    # Backward compatibility with legacy `collector` block.
    collector = recipe.get("collector")
    if isinstance(collector, dict):
        ctype = str(collector.get("type", "")).strip().lower()
        if ctype == "composio_regenerate_api_key":
            return {"provider": "composio", "mode": "project_api_key_regenerate"}
    return {}


def run_acquisition(
    recipe: dict,
    smithery: SmitheryAdapter,
    connection_id: str,
    runtime_values: Optional[dict] = None,
) -> dict:
    acq = get_acquisition_config(recipe)
    if not acq:
        return {}
    provider = str(acq.get("provider", "")).strip().lower()
    mode = str(acq.get("mode", "")).strip().lower()

    if provider == "composio" and mode in (
        "project_api_key_regenerate",
        "regenerate_api_key",
    ):
        return collect_composio_project_api_key(smithery, connection_id)
    if provider == "netlify" and mode in ("oauth_ticket_exchange", "ticket_exchange"):
        return collect_netlify_oauth_ticket_token(recipe, runtime_values=runtime_values)
    raise RuntimeError(f"Unsupported acquisition provider/mode: {provider}/{mode}")


def run_service_recipe(
    recipe: dict,
    ctx: RunnerContext,
    smithery: SmitheryAdapter,
    gmail: GmailAdapter,
    doppler: DopplerAdapter,
) -> Tuple[bool, str]:
    service_name = recipe.get("name") or recipe.get("connection_id")
    connection_id = recipe["connection_id"]
    mcp_url = recipe.get("mcp_url")
    poll_timeout = int(recipe.get("auth", {}).get("poll_timeout_sec", 300))
    poll_interval = int(recipe.get("auth", {}).get("poll_interval_sec", 4))
    acq_cfg = get_acquisition_config(recipe)
    requires_connected_connection = not (
        isinstance(acq_cfg, dict)
        and acq_cfg.get("requires_connected_connection") is False
    )

    ctx.log(f"\n=== [{service_name}] start @ {now_utc_iso()} ===")

    conn = None
    try:
        conn = smithery.get_connection(connection_id)
    except Exception:
        if not mcp_url:
            return False, f"{connection_id}: not found and no mcp_url provided"
        ctx.log(f"[info] connection {connection_id} missing; creating")
        smithery.add_connection(connection_id, mcp_url)
        conn = smithery.get_connection(connection_id)

    loop_guard = 0
    otp_result = None
    runtime_values: Dict[str, str] = {}
    creds = resolve_credentials(recipe)
    for ck, cv in creds.items():
        runtime_values[f"credentials.{ck}"] = cv
    if creds:
        masked = {k: ("***" if v else "") for k, v in creds.items()}
        ctx.log(f"[credentials] resolved: {json.dumps(masked)}")
    simulated_nonconnected = False
    while loop_guard < 12:
        loop_guard += 1
        status = conn.get("status") or {}
        state = status.get("state")
        ctx.log(f"[state] {connection_id}: {state}")

        if state == "connected":
            break

        if state == "auth_required":
            setup_url = get_setup_url(status)
            if not setup_url:
                return False, f"{connection_id}: auth_required without setupUrl"
            smithery.open_setup_url(setup_url)
            if ctx.dry_run:
                ctx.log("[dry-run] simulated auth_required flow complete")
                simulated_nonconnected = True
                break

            gmail_cfg = recipe.get("gmail") or {}
            gmail_conn = gmail_cfg.get("connection_id")
            if gmail_conn:
                messages = gmail.fetch_messages(
                    gmail_connection_id=gmail_conn,
                    query=gmail_cfg.get(
                        "query", "subject:(verification OR code OR otp) newer_than:1d"
                    ),
                    max_results=int(gmail_cfg.get("max_results", 10)),
                    verbose=False,
                )
                otp_result = gmail.parse_latest_otp(
                    messages,
                    sender_allowlist=gmail_cfg.get("sender_allowlist") or [],
                    code_regex=gmail_cfg.get("code_regex"),
                )
                if otp_result:
                    code = otp_result.get("code")
                    link = otp_result.get("link")
                    ctx.log(
                        f"[otp] found from {otp_result.get('sender')}: code={code if code else '-'} link={'yes' if link else 'no'}"
                    )

            conn = smithery.poll_until_state_change(
                connection_id=connection_id,
                from_state="auth_required",
                timeout_sec=poll_timeout,
                interval_sec=poll_interval,
            )
            continue

        if state == "input_required":
            apply_input_required(
                recipe, conn, smithery, ctx, runtime_values=runtime_values
            )
            if ctx.dry_run:
                ctx.log("[dry-run] simulated input_required flow complete")
                simulated_nonconnected = True
                break
            conn = smithery.get_connection(connection_id)
            continue

        if state == "error":
            return False, f"{connection_id}: connection error state"

        conn = smithery.get_connection(connection_id)
        time.sleep(max(poll_interval, 2))

    final_state = (conn.get("status") or {}).get("state")
    if (
        final_state != "connected"
        and not (ctx.dry_run and simulated_nonconnected)
        and requires_connected_connection
    ):
        return False, f"{connection_id}: did not reach connected (final={final_state})"
    if final_state != "connected" and not requires_connected_connection:
        ctx.log(
            f"[warn] proceeding without connected state for {connection_id} (final={final_state})"
        )

    if not ctx.dry_run:
        if requires_connected_connection:
            authorized, auth_msg = smithery.is_authorized_for_tools(connection_id)
            if not authorized:
                return (
                    False,
                    f"{connection_id}: connected state but not authorized for tools ({auth_msg})",
                )
            auth_probe_tool = recipe.get("auth_probe_tool")
            if isinstance(auth_probe_tool, str) and auth_probe_tool.strip():
                try:
                    smithery.tool_call(connection_id, auth_probe_tool.strip(), {})
                except Exception as e:
                    return (
                        False,
                        f"{connection_id}: connected state but auth probe failed ({e})",
                    )
        if acq_cfg:
            collected = run_acquisition(
                recipe, smithery, connection_id, runtime_values=runtime_values
            )
            value = collected.get("value")
            if isinstance(value, str) and value:
                runtime_values["key"] = value  # legacy alias for collector:key
                runtime_values["acquisition.value"] = value
                runtime_values["acquisition.provider"] = str(
                    collected.get("provider") or ""
                )
                runtime_values["acquisition.mode"] = str(collected.get("mode") or "")
                runtime_values["acquisition.path"] = str(collected.get("path") or "")
                meta = (
                    collected.get("meta")
                    if isinstance(collected.get("meta"), dict)
                    else {}
                )
                for mk, mv in meta.items():
                    runtime_values[f"acquisition.meta.{mk}"] = str(mv)
                ctx.log(
                    f"[acquisition] captured secret via {runtime_values.get('acquisition.provider')}/"
                    f"{runtime_values.get('acquisition.mode')} path={runtime_values.get('acquisition.path')}"
                )

    doppler_cfg = recipe.get("doppler") or {}
    if doppler_cfg:
        project = doppler_cfg.get("project")
        config = doppler_cfg.get("config")
        secret_key = doppler_cfg.get("secret_key")
        if project and config and secret_key:
            value = resolve_doppler_value(
                recipe, otp_result, runtime_values=runtime_values
            )
            if value:
                doppler.set_secret(
                    project=project, config=config, key=secret_key, value=value
                )
                ctx.log(f"[doppler] upserted {secret_key} in {project}/{config}")
            else:
                ctx.log(f"[doppler] skipped {secret_key}: no resolved value source")

    ctx.log(f"=== [{service_name}] done ===")
    if final_state == "connected":
        return True, f"{connection_id}: connected"
    return True, f"{connection_id}: {final_state} (acquisition-capable)"


def load_recipes(path: str) -> List[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    services = data.get("services")
    if not isinstance(services, list):
        raise ValueError("Recipe file must contain 'services' list.")
    return services


def main() -> int:
    parser = argparse.ArgumentParser(
        description="API-first Auth Runner (Smithery + Gmail + Doppler)"
    )
    parser.add_argument("--recipes", required=True, help="Path to recipe JSON file")
    parser.add_argument(
        "--service", action="append", help="Run only specific service name(s)"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute mutating actions (default is dry-run)",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose logs")
    args = parser.parse_args()

    ctx = RunnerContext(dry_run=not args.live, verbose=args.verbose)
    smithery = SmitheryAdapter(ctx)
    gmail = GmailAdapter(ctx)
    doppler = DopplerAdapter(ctx)

    try:
        services = load_recipes(args.recipes)
    except Exception as e:
        print(f"Failed loading recipe file: {e}", file=sys.stderr)
        return 2

    selected = set(args.service or [])
    if selected:
        services = [
            s
            for s in services
            if (s.get("name") in selected) or (s.get("connection_id") in selected)
        ]

    if not services:
        print("No services to run.")
        return 1

    ok = 0
    fail = 0
    for recipe in services:
        try:
            success, msg = run_service_recipe(recipe, ctx, smithery, gmail, doppler)
            if success:
                ok += 1
                print(f"[ok] {msg}")
            else:
                fail += 1
                print(f"[fail] {msg}")
        except Exception as e:
            fail += 1
            print(f"[fail] {recipe.get('name', recipe.get('connection_id'))}: {e}")

    print(f"\nSummary: ok={ok} fail={fail} dry_run={ctx.dry_run}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
