#!/usr/bin/env python3
"""Stage an authenticated X home-feed snapshot for an agent-generated briefing.

The script is intentionally read-only with respect to X. It invokes xbird (preferred)
or Bird, normalizes the For You and Following timelines, and uses a two-phase
prepare/commit state transition so a failed agent turn does not silently consume a feed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

VERSION = 1
RUN_ID_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")
DEFAULT_CONFIG: dict[str, Any] = {
    "forYouCount": 200,
    "followingCount": 100,
    "includeFollowing": True,
    "retentionDays": 30,
    "archiveDays": 14,
    "pendingReuseHours": 24,
    "commandTimeoutSeconds": 180,
    "xCli": None,
    "briefingProfile": {
        "mission": "Keep me current on consequential AI developments without making me browse X.",
        "prioritize": [
            "new model releases, capability changes, context limits, pricing, quotas, and access changes",
            "coding agents, agent harnesses, computer use, orchestration, memory, evaluation, and reliability",
            "open-source repositories, useful tools, reproducible demos, and implementation details",
            "benchmarks and evaluations with enough methodology to judge the result",
            "inference, training, hardware, local AI, APIs, and developer infrastructure",
            "security incidents, policy or platform changes, and ecosystem shifts with practical consequences",
            "technical analysis or research that changes what I should build, buy, test, or learn next"
        ],
        "deprioritize": [
            "memes, engagement bait, personality drama, tribal discourse, vague predictions, and recycled takes",
            "launch repetition without additional facts, affiliate promotion, and demos with no inspectable evidence",
            "raw popularity when the item has little practical or technical substance"
        ],
        "mustKnowMax": 7,
        "worthSkimmingMax": 8,
        "watchlistMax": 3,
        "targetReadingMinutes": 8,
        "verifyTopClaimsWhenToolsPermit": True
    }
}


class FeedError(RuntimeError):
    pass


def load_x_credentials() -> None:
    """Load only AUTH_TOKEN and CT0 from the private local credentials file."""
    configured = os.environ.get("X_AI_BRIEF_CREDENTIALS")
    credential_path = Path(configured).expanduser() if configured else Path.home() / ".config" / "x-ai-brief" / "credentials.env"
    if not credential_path.exists():
        return
    try:
        for line in credential_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key in {"AUTH_TOKEN", "CT0"} and value:
                os.environ.setdefault(key, value)
    except OSError as exc:
        raise FeedError(f"Cannot read X credentials from {credential_path}: {exc}") from exc


@dataclass(frozen=True)
class Paths:
    config: Path
    base: Path
    state: Path
    pending: Path
    runs: Path
    abandoned: Path
    lock: Path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(dt: datetime | None = None) -> str:
    value = dt or utc_now()
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def paths() -> Paths:
    home = Path.home()
    state_root = Path(os.environ.get("OPENCLAW_STATE_DIR", home / ".openclaw")).expanduser()
    base = Path(os.environ.get("X_AI_BRIEF_STATE_DIR", state_root / "state" / "x-ai-brief")).expanduser()
    config = Path(os.environ.get("X_AI_BRIEF_CONFIG", home / ".config" / "x-ai-brief" / "config.json")).expanduser()
    return Paths(
        config=config,
        base=base,
        state=base / "state.json",
        pending=base / "pending",
        runs=base / "runs",
        abandoned=base / "abandoned",
        lock=base / ".lock",
    )


def ensure_dirs(p: Paths) -> None:
    p.base.mkdir(parents=True, exist_ok=True)
    p.pending.mkdir(parents=True, exist_ok=True)
    p.runs.mkdir(parents=True, exist_ok=True)
    p.abandoned.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FeedError(f"Cannot read valid JSON from {path}: {exc}") from exc


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def load_config(p: Paths) -> dict[str, Any]:
    config = deep_merge(DEFAULT_CONFIG, load_json(p.config, {}))
    for key in ("forYouCount", "followingCount", "retentionDays", "archiveDays", "pendingReuseHours", "commandTimeoutSeconds"):
        value = config.get(key)
        if not isinstance(value, int) or value < 0:
            raise FeedError(f"Config field {key} must be a non-negative integer")
    if config["forYouCount"] < 1:
        raise FeedError("forYouCount must be at least 1")
    return config


class FileLock:
    def __init__(self, path: Path, stale_seconds: int = 900) -> None:
        self.path = path
        self.stale_seconds = stale_seconds
        self.acquired = False

    def __enter__(self) -> "FileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(json.dumps({"pid": os.getpid(), "createdAt": iso_z()}))
                self.acquired = True
                return self
            except FileExistsError:
                try:
                    age = time.time() - self.path.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age > self.stale_seconds:
                    try:
                        self.path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                raise FeedError(f"Another x-ai-brief operation is active ({self.path})")
        raise FeedError("Could not acquire state lock")

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.acquired:
            try:
                self.path.unlink()
            except FileNotFoundError:
                pass


def load_state(p: Paths) -> dict[str, Any]:
    state = load_json(p.state, {"version": VERSION, "seen": {}, "lastCommittedAt": None})
    if not isinstance(state, dict):
        raise FeedError("State file must contain a JSON object")
    if not isinstance(state.get("seen"), dict):
        state["seen"] = {}
    state["version"] = VERSION
    return state


def prune_state(state: dict[str, Any], retention_days: int) -> None:
    cutoff = utc_now().timestamp() - retention_days * 86400
    seen = state.get("seen", {})
    state["seen"] = {
        str(tweet_id): timestamp
        for tweet_id, timestamp in seen.items()
        if (parsed := parse_time(timestamp)) is not None and parsed.timestamp() >= cutoff
    }


def prune_run_files(p: Paths, archive_days: int) -> None:
    cutoff = time.time() - archive_days * 86400
    for directory in (p.runs, p.abandoned):
        for candidate in directory.glob("*.json"):
            try:
                if candidate.stat().st_mtime < cutoff:
                    candidate.unlink()
            except FileNotFoundError:
                pass


def find_reusable_pending(p: Paths, hours: int) -> Path | None:
    cutoff = time.time() - hours * 3600
    candidates: list[Path] = []
    for candidate in p.pending.glob("*.json"):
        try:
            if candidate.stat().st_mtime >= cutoff:
                candidates.append(candidate)
        except FileNotFoundError:
            pass
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def find_executable(name: str) -> str | None:
    discovered = shutil.which(name)
    if discovered:
        return discovered
    user_local = Path.home() / ".local" / "bin" / name
    if user_local.is_file() and os.access(user_local, os.X_OK):
        return str(user_local)
    return None


def cli_command(config: dict[str, Any]) -> list[str]:
    configured = config.get("xCli") or os.environ.get("X_AI_BRIEF_CLI")
    if isinstance(configured, str) and configured.strip():
        parts = configured.strip().split()
        if find_executable(parts[0]) or (Path(parts[0]).is_file() and os.access(parts[0], os.X_OK)):
            return parts
        raise FeedError(f"Configured X CLI is not executable: {parts[0]}")
    for name in ("xbird", "bird"):
        binary = find_executable(name)
        if binary:
            return [binary]
    raise FeedError(
        "Neither xbird nor bird is on PATH. Install xbird, then run `xbird check` and `xbird whoami`."
    )


def sanitize_error(text: str, limit: int = 1200) -> str:
    # Cookie values should never be printed by the clients, but redact common secret forms defensively.
    value = re.sub(r"(?i)(auth_token|ct0)([=:]\s*)[^\s,;]+", r"\1\2[REDACTED]", text)
    value = value.strip()
    return value[-limit:] if len(value) > limit else value


def parse_cli_payload(stdout: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise FeedError(f"X CLI returned non-JSON output: {sanitize_error(stdout)}") from exc
    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict):
        values = payload.get("tweets") or payload.get("items") or []
    else:
        values = []
    return [value for value in values if isinstance(value, dict)]


def run_timeline(command: list[str], count: int, following: bool, timeout: int) -> list[dict[str, Any]]:
    args = [*command, "home"]
    if following:
        args.append("--following")
    args.extend(["-n", str(count), "--json"])
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired as exc:
        raise FeedError(f"X CLI timed out after {timeout}s while fetching {'Following' if following else 'For You'}") from exc
    except OSError as exc:
        raise FeedError(f"Could not execute {command[0]}: {exc}") from exc
    if result.returncode != 0:
        detail = sanitize_error(result.stderr or result.stdout or f"exit {result.returncode}")
        raise FeedError(f"{command[0]} failed fetching {'Following' if following else 'For You'}: {detail}")
    return parse_cli_payload(result.stdout)


def first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[ \t]+", " ", text).strip()


def dedupe_key(text: str) -> str:
    compact = unicodedata.normalize("NFKC", text).casefold()
    compact = re.sub(r"https?://t\.co/[A-Za-z0-9]+", "", compact)
    compact = re.sub(r"\s+", " ", compact).strip()
    return compact


def normalize_urls(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for entry in raw:
        if isinstance(entry, str):
            url = entry
        elif isinstance(entry, dict):
            url = first(entry, "expandedUrl", "expanded_url", "url", "displayUrl", "display_url")
        else:
            continue
        if isinstance(url, str) and url.startswith(("http://", "https://")) and url not in values:
            values.append(url)
    return values


def normalize_media(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    values: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        item = {
            "type": first(entry, "type", "mediaType"),
            "url": first(entry, "url", "previewUrl", "preview_url", "videoUrl", "video_url"),
        }
        values.append({k: v for k, v in item.items() if v is not None})
    return values


def normalize_quote(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    author_raw = raw.get("author") if isinstance(raw.get("author"), dict) else raw.get("user")
    author_raw = author_raw if isinstance(author_raw, dict) else {}
    quote_id = first(raw, "id", "idStr", "id_str", "rest_id")
    username = first(author_raw, "username", "screenName", "screen_name")
    text = normalize_text(first(raw, "text", "fullText", "full_text"))
    if not quote_id and not text:
        return None
    result: dict[str, Any] = {
        "id": str(quote_id) if quote_id is not None else None,
        "author": f"@{username}" if username else None,
        "text": text,
    }
    if quote_id:
        result["url"] = f"https://x.com/{username}/status/{quote_id}" if username else f"https://x.com/i/status/{quote_id}"
    return {key: value for key, value in result.items() if value not in (None, "")}


def normalize_item(raw: dict[str, Any], source: str, position: int) -> dict[str, Any] | None:
    tweet_id = first(raw, "id", "idStr", "id_str", "rest_id")
    if tweet_id is None:
        return None
    tweet_id = str(tweet_id)

    author_raw = raw.get("author") if isinstance(raw.get("author"), dict) else raw.get("user")
    author_raw = author_raw if isinstance(author_raw, dict) else {}
    username = first(author_raw, "username", "screenName", "screen_name")
    author_name = first(author_raw, "name", "displayName", "display_name")
    text = normalize_text(first(raw, "text", "fullText", "full_text", "noteText", "note_text"))

    article_raw = raw.get("article") if isinstance(raw.get("article"), dict) else {}
    article = {
        "title": normalize_text(first(article_raw, "title")),
        "previewText": normalize_text(first(article_raw, "previewText", "preview_text")),
    }
    article = {key: value for key, value in article.items() if value}
    if not text and article:
        text = article.get("title", "")
    if not text:
        return None

    metrics_raw = raw.get("public_metrics") if isinstance(raw.get("public_metrics"), dict) else {}
    metrics = {
        "likes": as_int(first(raw, "likeCount", "like_count") or first(metrics_raw, "like_count")),
        "reposts": as_int(first(raw, "retweetCount", "retweet_count", "repostCount", "repost_count") or first(metrics_raw, "retweet_count")),
        "replies": as_int(first(raw, "replyCount", "reply_count") or first(metrics_raw, "reply_count")),
        "quotes": as_int(first(raw, "quoteCount", "quote_count") or first(metrics_raw, "quote_count")),
        "views": as_int(first(raw, "viewCount", "view_count") or first(metrics_raw, "impression_count")),
    }
    metrics = {key: value for key, value in metrics.items() if value is not None}

    link = f"https://x.com/{username}/status/{tweet_id}" if username else f"https://x.com/i/status/{tweet_id}"
    source_position = {"forYouPosition": position} if source == "forYou" else {"followingPosition": position}
    quoted = normalize_quote(first(raw, "quotedTweet", "quoted_tweet"))

    item: dict[str, Any] = {
        "id": tweet_id,
        "allIds": [tweet_id],
        "author": f"@{username}" if username else "unknown",
        "authorName": author_name or "",
        "createdAt": first(raw, "createdAt", "created_at"),
        "text": text,
        "url": link,
        "sources": [source],
        **source_position,
        "metrics": metrics,
        "expandedUrls": normalize_urls(first(raw, "urls", "entitiesUrls", "entities_urls")),
        "media": normalize_media(first(raw, "media")),
        "article": article or None,
        "quotedTweet": quoted,
        "conversationId": first(raw, "conversationId", "conversation_id"),
        "inReplyToStatusId": first(raw, "inReplyToStatusId", "in_reply_to_status_id"),
    }
    return {key: value for key, value in item.items() if value not in (None, "", [], {})}


def merge_same_id(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    for source in incoming.get("sources", []):
        if source not in existing["sources"]:
            existing["sources"].append(source)
    for key in ("forYouPosition", "followingPosition"):
        if key in incoming:
            existing[key] = min(existing.get(key, incoming[key]), incoming[key])
    for key in ("metrics", "expandedUrls", "media", "article", "quotedTweet"):
        if key not in existing and key in incoming:
            existing[key] = incoming[key]


def merge_exact_text(existing: dict[str, Any], incoming: dict[str, Any]) -> None:
    for tweet_id in incoming.get("allIds", [incoming["id"]]):
        if tweet_id not in existing["allIds"]:
            existing["allIds"].append(tweet_id)
    for source in incoming.get("sources", []):
        if source not in existing["sources"]:
            existing["sources"].append(source)
    for key in ("forYouPosition", "followingPosition"):
        if key in incoming:
            existing[key] = min(existing.get(key, incoming[key]), incoming[key])
    duplicate_links = existing.setdefault("duplicateUrls", [])
    if incoming["url"] != existing["url"] and incoming["url"] not in duplicate_links:
        duplicate_links.append(incoming["url"])


def normalize_timelines(for_you: list[dict[str, Any]], following: list[dict[str, Any]], seen: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    invalid = 0
    already_seen = 0

    for source, values in (("forYou", for_you), ("following", following)):
        for position, raw in enumerate(values, 1):
            item = normalize_item(raw, source, position)
            if item is None:
                invalid += 1
                continue
            tweet_id = item["id"]
            if tweet_id in seen:
                already_seen += 1
                continue
            if tweet_id in by_id:
                merge_same_id(by_id[tweet_id], item)
            else:
                by_id[tweet_id] = item
                order.append(tweet_id)

    exact_text: dict[str, dict[str, Any]] = {}
    items: list[dict[str, Any]] = []
    exact_duplicates = 0
    for tweet_id in order:
        item = by_id[tweet_id]
        key = dedupe_key(item["text"])
        # Avoid collapsing terse reactions that happen to be identical.
        if len(key) >= 40 and key in exact_text:
            merge_exact_text(exact_text[key], item)
            exact_duplicates += 1
        else:
            items.append(item)
            if len(key) >= 40:
                exact_text[key] = item

    # Preserve the algorithmic order. Following-only items come after the For You snapshot,
    # while overlaps retain both positions for the model to use as a weak relevance signal.
    items.sort(key=lambda item: (
        item.get("forYouPosition", 10**9),
        item.get("followingPosition", 10**9),
        item["id"],
    ))
    return items, {
        "invalidItems": invalid,
        "alreadySeenOccurrences": already_seen,
        "exactTextDuplicatesCollapsed": exact_duplicates,
    }


def output(value: Any) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    sys.stdout.write("\n")


def run_id() -> str:
    return f"{utc_now().strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def command_prepare(args: argparse.Namespace, p: Paths, config: dict[str, Any]) -> None:
    ensure_dirs(p)
    with FileLock(p.lock):
        if not args.fresh:
            reusable = find_reusable_pending(p, config["pendingReuseHours"])
            if reusable:
                payload = load_json(reusable, {})
                payload["reusedPending"] = True
                output(payload)
                return

        state = load_state(p)
        prune_state(state, config["retentionDays"])
        prune_run_files(p, config["archiveDays"])
        command = cli_command(config)

        for_you = run_timeline(command, config["forYouCount"], False, config["commandTimeoutSeconds"])
        warnings: list[str] = []
        following: list[dict[str, Any]] = []
        if config.get("includeFollowing", True) and config["followingCount"] > 0:
            try:
                following = run_timeline(command, config["followingCount"], True, config["commandTimeoutSeconds"])
            except FeedError as exc:
                warnings.append(str(exc))

        items, normalization_counts = normalize_timelines(for_you, following, state.get("seen", {}))
        identifier = run_id()
        payload = {
            "schemaVersion": VERSION,
            "runId": identifier,
            "preparedAt": iso_z(),
            "reusedPending": False,
            "xCli": Path(command[0]).name,
            "window": {"after": state.get("lastCommittedAt"), "through": iso_z()},
            "counts": {
                "forYouFetched": len(for_you),
                "followingFetched": len(following),
                "uniqueUnseenForAgent": len(items),
                **normalization_counts,
            },
            "warnings": warnings,
            "briefingProfile": config["briefingProfile"],
            "items": items,
        }
        atomic_write(p.pending / f"{identifier}.json", payload)
        atomic_write(p.state, state)
        output(payload)


def valid_run_id(value: str) -> str:
    if not RUN_ID_RE.fullmatch(value):
        raise FeedError("Invalid run ID")
    return value


def pending_path(p: Paths, identifier: str) -> Path:
    return p.pending / f"{valid_run_id(identifier)}.json"


def command_commit(args: argparse.Namespace, p: Paths, config: dict[str, Any]) -> None:
    ensure_dirs(p)
    identifier = valid_run_id(args.run_id)
    with FileLock(p.lock):
        source = pending_path(p, identifier)
        if not source.exists():
            archived = p.runs / f"{identifier}.json"
            if archived.exists():
                output({"ok": True, "runId": identifier, "alreadyCommitted": True})
                return
            raise FeedError(f"Pending run not found: {identifier}")
        payload = load_json(source, {})
        state = load_state(p)
        timestamp = iso_z()
        marked = 0
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            ids = item.get("allIds") or [item.get("id")]
            for tweet_id in ids:
                if tweet_id is None:
                    continue
                state["seen"][str(tweet_id)] = timestamp
                marked += 1
        state["lastCommittedAt"] = timestamp
        prune_state(state, config["retentionDays"])
        atomic_write(p.state, state)
        payload["committedAt"] = timestamp
        payload["commitNote"] = args.note if args.note else None
        destination = p.runs / source.name
        atomic_write(destination, payload)
        source.unlink()
        prune_run_files(p, config["archiveDays"])
        output({"ok": True, "runId": identifier, "tweetIdsMarkedSeen": marked, "committedAt": timestamp})


def command_abort(args: argparse.Namespace, p: Paths, config: dict[str, Any]) -> None:
    del config
    ensure_dirs(p)
    identifier = valid_run_id(args.run_id)
    with FileLock(p.lock):
        source = pending_path(p, identifier)
        if not source.exists():
            output({"ok": True, "runId": identifier, "alreadyAbsent": True})
            return
        payload = load_json(source, {})
        payload["abortedAt"] = iso_z()
        payload["abortReason"] = args.reason or "aborted"
        atomic_write(p.abandoned / source.name, payload)
        source.unlink()
        output({"ok": True, "runId": identifier, "aborted": True})


def command_status(args: argparse.Namespace, p: Paths, config: dict[str, Any]) -> None:
    del args
    ensure_dirs(p)
    state = load_state(p)
    pending = sorted(candidate.stem for candidate in p.pending.glob("*.json"))
    runs = sorted((candidate.stem for candidate in p.runs.glob("*.json")), reverse=True)[:10]
    output({
        "schemaVersion": VERSION,
        "configPath": str(p.config),
        "stateDirectory": str(p.base),
        "xCli": cli_command(config)[0] if any(find_executable(name) for name in ("xbird", "bird")) or config.get("xCli") else None,
        "lastCommittedAt": state.get("lastCommittedAt"),
        "seenCount": len(state.get("seen", {})),
        "pendingRuns": pending,
        "recentCommittedRuns": runs,
    })


def command_reset(args: argparse.Namespace, p: Paths, config: dict[str, Any]) -> None:
    del config
    if not args.yes:
        raise FeedError("Reset requires --yes")
    if p.base.exists():
        shutil.rmtree(p.base)
    output({"ok": True, "reset": True, "stateDirectory": str(p.base)})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="Fetch and stage unseen For You/Following items")
    prepare.add_argument("--fresh", action="store_true", help="Ignore a recent pending run and fetch a new snapshot")
    prepare.set_defaults(handler=command_prepare)

    commit = subparsers.add_parser("commit", help="Mark every staged item processed after the briefing is ready")
    commit.add_argument("run_id")
    commit.add_argument("--note", default=None)
    commit.set_defaults(handler=command_commit)

    abort = subparsers.add_parser("abort", help="Discard a staged run without marking any X items processed")
    abort.add_argument("run_id")
    abort.add_argument("--reason", default=None)
    abort.set_defaults(handler=command_abort)

    status = subparsers.add_parser("status", help="Show state and pending runs")
    status.set_defaults(handler=command_status)

    reset = subparsers.add_parser("reset", help="Delete all local x-ai-brief state")
    reset.add_argument("--yes", action="store_true")
    reset.set_defaults(handler=command_reset)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    p = paths()
    try:
        load_x_credentials()
        config = load_config(p)
        args.handler(args, p, config)
        return 0
    except FeedError as exc:
        json.dump({"ok": False, "error": str(exc)}, sys.stderr, ensure_ascii=False)
        sys.stderr.write("\n")
        return 1
    except KeyboardInterrupt:
        json.dump({"ok": False, "error": "interrupted"}, sys.stderr)
        sys.stderr.write("\n")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
