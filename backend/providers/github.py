"""GitHub webhook provider.

Generates JSON bodies shaped like GitHub's webhook event payloads and signs
them with the official ``X-Hub-Signature-256`` scheme:

    X-Hub-Signature-256: sha256=<hex>

    hex = HMAC-SHA256(webhook_secret, raw_request_body)

The raw body must be exactly the bytes that will be POSTed. We use the same
``canonical_json`` serializer as Stripe so sign and send cannot drift.

Reference:
https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
"""

from __future__ import annotations

import secrets
from typing import Any, Callable

from utils.payload_templates import fake_id, unix_timestamp
from utils.signing import canonical_json, hmac_sha256_hex

EVENT_TYPES = [
    "push",
    "pull_request",
    "issues",
]

_REPO_ID = 1296269
_OWNER_ID = 1
_REPO_FULL_NAME = "octocat/Hello-World"
_REPO_HTML = f"https://github.com/{_REPO_FULL_NAME}"


def generate_payload(event_type: str) -> dict[str, Any]:
    """Return a realistic GitHub webhook JSON payload for ``event_type``.

    Raises:
        ValueError: if ``event_type`` is not in ``EVENT_TYPES``.
    """
    if event_type not in EVENT_TYPES:
        raise ValueError(
            f"Unsupported GitHub event_type {event_type!r}. "
            f"Expected one of: {', '.join(EVENT_TYPES)}"
        )
    return _PAYLOAD_BUILDERS[event_type]()


def sign_payload(
    payload: dict[str, Any],
    secret: str,
    *,
    target_url: str | None = None,
) -> dict[str, str]:
    """Sign ``payload`` and return ``X-Hub-Signature-256``.

    ``target_url`` is ignored (GitHub signs the raw body only). Kept so every
    provider module shares one callable shape.
    """
    _ = target_url
    if not secret:
        raise ValueError("GitHub webhook secret must be non-empty")

    body = canonical_json(payload)
    digest = hmac_sha256_hex(secret, body)
    return {"X-Hub-Signature-256": f"sha256={digest}"}


# ---------------------------------------------------------------------------
# Shared nested objects
# ---------------------------------------------------------------------------


def _user(login: str = "octocat", *, user_id: int = 1) -> dict[str, Any]:
    return {
        "login": login,
        "id": user_id,
        "node_id": f"MDQ6VXNlcj{user_id}",
        "avatar_url": f"https://avatars.githubusercontent.com/u/{user_id}?v=4",
        "html_url": f"https://github.com/{login}",
        "type": "User",
        "site_admin": False,
    }


def _repository() -> dict[str, Any]:
    owner = _user("octocat", user_id=_OWNER_ID)
    return {
        "id": _REPO_ID,
        "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
        "name": "Hello-World",
        "full_name": _REPO_FULL_NAME,
        "private": False,
        "owner": owner,
        "html_url": _REPO_HTML,
        "description": "Webhook sandbox demo repository",
        "fork": False,
        "url": f"https://api.github.com/repos/{_REPO_FULL_NAME}",
        "default_branch": "main",
        "master_branch": "main",
        "created_at": 1401234567,
        "updated_at": "2024-01-15T12:00:00Z",
        "pushed_at": unix_timestamp(),
        "visibility": "public",
    }


def _sha(nbytes: int = 20) -> str:
    return secrets.token_hex(nbytes)


# ---------------------------------------------------------------------------
# Event builders
# ---------------------------------------------------------------------------


def _push() -> dict[str, Any]:
    before = _sha()
    head = _sha()
    commit_id = head
    pusher_login = "octocat"
    created = "2024-06-01T12:00:00Z"

    return {
        "ref": "refs/heads/main",
        "before": before,
        "after": head,
        "created": False,
        "deleted": False,
        "forced": False,
        "base_ref": None,
        "compare": f"{_REPO_HTML}/compare/{before[:7]}...{head[:7]}",
        "commits": [
            {
                "id": commit_id,
                "tree_id": _sha(),
                "distinct": True,
                "message": "Add webhook sandbox fixture",
                "timestamp": created,
                "url": f"{_REPO_HTML}/commit/{commit_id}",
                "author": {
                    "name": "The Octocat",
                    "email": "octocat@github.com",
                    "username": pusher_login,
                },
                "committer": {
                    "name": "The Octocat",
                    "email": "octocat@github.com",
                    "username": pusher_login,
                },
                "added": ["README.md"],
                "removed": [],
                "modified": ["src/app.py"],
            }
        ],
        "head_commit": {
            "id": commit_id,
            "tree_id": _sha(),
            "distinct": True,
            "message": "Add webhook sandbox fixture",
            "timestamp": created,
            "url": f"{_REPO_HTML}/commit/{commit_id}",
            "author": {
                "name": "The Octocat",
                "email": "octocat@github.com",
                "username": pusher_login,
            },
            "committer": {
                "name": "The Octocat",
                "email": "octocat@github.com",
                "username": pusher_login,
            },
            "added": ["README.md"],
            "removed": [],
            "modified": ["src/app.py"],
        },
        "repository": _repository(),
        "pusher": {
            "name": pusher_login,
            "email": "octocat@github.com",
        },
        "sender": _user(pusher_login),
    }


def _pull_request() -> dict[str, Any]:
    number = 42
    pr_id = 1_000_000 + number
    user = _user()
    head_sha = _sha()
    base_sha = _sha()

    return {
        "action": "opened",
        "number": number,
        "pull_request": {
            "url": f"https://api.github.com/repos/{_REPO_FULL_NAME}/pulls/{number}",
            "id": pr_id,
            "node_id": fake_id("PR"),
            "html_url": f"{_REPO_HTML}/pull/{number}",
            "diff_url": f"{_REPO_HTML}/pull/{number}.diff",
            "patch_url": f"{_REPO_HTML}/pull/{number}.patch",
            "number": number,
            "state": "open",
            "locked": False,
            "title": "Improve webhook signature verification",
            "user": user,
            "body": "This PR exercises the GitHub webhook fixture.",
            "created_at": "2024-06-01T12:00:00Z",
            "updated_at": "2024-06-01T12:00:00Z",
            "closed_at": None,
            "merged_at": None,
            "merge_commit_sha": None,
            "assignee": None,
            "assignees": [],
            "requested_reviewers": [],
            "labels": [],
            "draft": False,
            "merged": False,
            "mergeable": True,
            "rebaseable": True,
            "mergeable_state": "clean",
            "comments": 0,
            "review_comments": 0,
            "commits": 1,
            "additions": 12,
            "deletions": 3,
            "changed_files": 2,
            "head": {
                "label": "octocat:feature-webhook",
                "ref": "feature-webhook",
                "sha": head_sha,
                "user": user,
                "repo": _repository(),
            },
            "base": {
                "label": "octocat:main",
                "ref": "main",
                "sha": base_sha,
                "user": user,
                "repo": _repository(),
            },
        },
        "repository": _repository(),
        "sender": user,
    }


def _issues() -> dict[str, Any]:
    number = 17
    issue_id = 2_000_000 + number
    user = _user()

    return {
        "action": "opened",
        "issue": {
            "url": f"https://api.github.com/repos/{_REPO_FULL_NAME}/issues/{number}",
            "repository_url": f"https://api.github.com/repos/{_REPO_FULL_NAME}",
            "labels_url": (
                f"https://api.github.com/repos/{_REPO_FULL_NAME}/issues/{number}/labels{{/name}}"
            ),
            "comments_url": (
                f"https://api.github.com/repos/{_REPO_FULL_NAME}/issues/{number}/comments"
            ),
            "events_url": (
                f"https://api.github.com/repos/{_REPO_FULL_NAME}/issues/{number}/events"
            ),
            "html_url": f"{_REPO_HTML}/issues/{number}",
            "id": issue_id,
            "node_id": fake_id("I"),
            "number": number,
            "title": "Webhook signature check fails on UTF-8 body",
            "user": user,
            "labels": [
                {
                    "id": 208045946,
                    "node_id": "MDU6TGFiZWwyMDgwNDU5NDY=",
                    "url": f"https://api.github.com/repos/{_REPO_FULL_NAME}/labels/bug",
                    "name": "bug",
                    "color": "d73a4a",
                    "default": True,
                    "description": "Something isn't working",
                }
            ],
            "state": "open",
            "locked": False,
            "assignee": None,
            "assignees": [],
            "milestone": None,
            "comments": 0,
            "created_at": "2024-06-01T12:00:00Z",
            "updated_at": "2024-06-01T12:00:00Z",
            "closed_at": None,
            "author_association": "OWNER",
            "active_lock_reason": None,
            "body": "Repro steps for the webhook sandbox.",
            "reactions": {
                "url": (
                    f"https://api.github.com/repos/{_REPO_FULL_NAME}/issues/{number}/reactions"
                ),
                "total_count": 0,
                "+1": 0,
                "-1": 0,
                "laugh": 0,
                "hooray": 0,
                "confused": 0,
                "heart": 0,
                "rocket": 0,
                "eyes": 0,
            },
        },
        "repository": _repository(),
        "sender": user,
    }


_PAYLOAD_BUILDERS: dict[str, Callable[[], dict[str, Any]]] = {
    "push": _push,
    "pull_request": _pull_request,
    "issues": _issues,
}
