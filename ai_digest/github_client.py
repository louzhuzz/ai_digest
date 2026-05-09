# -*- coding: utf-8 -*-
"""
ai_digest/github_client.py — GitHub REST API 客户端

功能：
- 解析 GitHub 仓库 URL 或 owner/repo 格式
- 获取仓库元数据（stars / forks / language / description / topics）
- 获取 README 原始内容（无需 base64 解码）
- 获取最新 Release（处理 404 —— 仓库无发布时返回 None）
- 退避重试：Retry-After → X-RateLimit-Reset → 60s 兜底 → 指数增长

认证：
- GITHUB_TOKEN 环境变量（可选）→ Bearer Token → 5000 req/hr
- 无 Token → 匿名 → 60 req/hr
"""

from __future__ import annotations

import base64
import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Optional

from urllib import request
from .http_client import decode_response

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"

# 软警告阈值：剩余请求低于此值时打日志
RATE_LIMIT_WARNING_THRESHOLD = 100


# ── 数据模型 ──────────────────────────────────────────────


@dataclass
class RepoMetadata:
    owner: str
    repo: str
    full_name: str
    description: Optional[str]
    stars: int
    forks: int
    language: Optional[str]
    topics: list[str]
    pushed_at: Optional[datetime]
    html_url: str
    homepage: Optional[str]
    license: Optional[str]
    open_issues_count: int
    watchers_count: int
    created_at: Optional[datetime]

    def to_dict(self) -> dict:
        d = asdict(self)
        if d.get("pushed_at"):
            d["pushed_at"] = d["pushed_at"].isoformat()
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        return d


@dataclass
class ReleaseInfo:
    tag_name: str
    name: Optional[str]
    body: Optional[str]
    created_at: datetime
    html_url: str

    def to_dict(self) -> dict:
        d = asdict(self)
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        return d


@dataclass
class GitHubRepoData:
    metadata: RepoMetadata
    readme: Optional[str]
    latest_release: Optional[ReleaseInfo]
    rate_limit_remaining: Optional[int]
    rate_limit_reset: Optional[int]

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata.to_dict(),
            "readme": self.readme,
            "latest_release": self.latest_release.to_dict() if self.latest_release else None,
            "rate_limit_remaining": self.rate_limit_remaining,
            "rate_limit_reset": self.rate_limit_reset,
        }


# ── GitHub API Client ─────────────────────────────────────


class GitHubAPIClient:
    _token: Optional[str]
    _max_retries: int
    _backoff_factor: float

    def __init__(self, token: Optional[str] = None, max_retries: int = 3, backoff_factor: float = 1.0) -> None:
        self._token = token or os.environ.get("GITHUB_TOKEN", "").strip() or None
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor

    # ── 通用请求（带退避重试）─────────────────────────────

    def _headers(self, extra: Optional[dict] = None) -> dict:
        h: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
            "User-Agent": "OpenClawDigest/1.0",
        }
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        if extra:
            h.update(extra)
        return h

    def _parse_rate_limit(self, response) -> tuple[Optional[int], Optional[int]]:
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        return (int(remaining), int(reset)) if remaining is not None else (None, None)

    def _handle_rate_limit(self, response) -> Optional[int]:
        """从 403/429 响应中提取应等待的秒数（基于响应头，不读取 body）。"""
        if response.status not in (403, 429):
            return None

        # 策略 1: Retry-After
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            return int(retry_after)

        # 策略 2: X-RateLimit-Remaining == 0 → 用 reset 时间戳
        remaining = response.headers.get("X-RateLimit-Remaining", "1")
        if remaining == "0":
            reset_ts = int(response.headers.get("X-RateLimit-Reset", "0"))
            wait = max(reset_ts - int(time.time()) + 1, 1)
            return wait

        # 策略 3: secondary limit 兜底，至少等 60s
        return 60

    def _request(self, method: str, url: str, headers: Optional[dict] = None) -> tuple[Any, Optional[int], Optional[int]]:
        """带退避重试的请求，返回 (response_body_json, rate_limit_remaining, rate_limit_reset)。"""
        hdrs = self._headers(headers)
        for attempt in range(self._max_retries):
            try:
                req = request.Request(url, headers=hdrs)
                response = request.urlopen(req, timeout=15)
                raw = response.read()
                status = response.status
            except Exception as exc:
                # 网络错误视为 5xx，等一等再试
                if attempt < self._max_retries - 1:
                    time.sleep(self._backoff_factor * (2 ** attempt) + random.uniform(0, 1))
                    continue
                raise

            rl_remaining, rl_reset = self._parse_rate_limit(response)

            # 成功或 404
            if status < 400 or status == 404:
                if rl_remaining is not None and rl_remaining < RATE_LIMIT_WARNING_THRESHOLD:
                    logger.warning("GitHub API rate limit low: %s/%s", rl_remaining, response.headers.get("X-RateLimit-Limit"))
                if status == 404:
                    # 404 body 通常为空，不需要 json.loads
                    return {}, rl_remaining, rl_reset
                return json.loads(raw.decode("utf-8", errors="replace")), rl_remaining, rl_reset

            # Rate limit
            wait = self._handle_rate_limit(response)
            if wait is not None:
                if attempt < self._max_retries - 1:
                    sleep_time = wait * self._backoff_factor * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning("GitHub API rate limited. Attempt %s/%s, sleeping %.1fs...", attempt + 1, self._max_retries, sleep_time)
                    time.sleep(sleep_time)
                    continue
                else:
                    raise RuntimeError(f"GitHub API rate limit exceeded after {self._max_retries} retries. Reset at: {rl_reset}")

            # 5xx 服务器错误
            if status >= 500:
                if attempt < self._max_retries - 1:
                    time.sleep(self._backoff_factor * (2 ** attempt) + random.uniform(0, 1))
                    continue

            # 其余 4xx 不重试
            error_body = raw.decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"GitHub API error {status}: {error_body}")

        raise RuntimeError(f"GitHub API request failed after {self._max_retries} retries")

    # ── 核心 API ─────────────────────────────────────────

    def fetch_repo_metadata(self, owner: str, repo: str) -> RepoMetadata:
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
        data, _, _ = self._request("GET", url)
        return RepoMetadata(
            owner=owner,
            repo=repo,
            full_name=data["full_name"],
            description=data.get("description"),
            stars=data["stargazers_count"],
            forks=data["forks_count"],
            language=data.get("language"),
            topics=data.get("topics", []),
            pushed_at=_parse_datetime(data.get("pushed_at")),
            html_url=data["html_url"],
            homepage=data.get("homepage"),
            license=data.get("license", {}).get("name") if data.get("license") else None,
            open_issues_count=data.get("open_issues_count", 0),
            watchers_count=data.get("watchers_count", 0),
            created_at=_parse_datetime(data.get("created_at")),
        )

    def fetch_readme(self, owner: str, repo: str) -> Optional[str]:
        """获取 README 原始内容（Accept: application/vnd.github.raw+json，直接返回文本，无需 base64 解码）。"""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/readme"
        hdrs = {"Accept": "application/vnd.github.raw+json"}
        for attempt in range(self._max_retries):
            try:
                req = request.Request(url, headers=self._headers(hdrs))
                response = request.urlopen(req, timeout=15)
                raw = response.read()
                status = response.status
            except Exception as exc:
                if attempt < self._max_retries - 1:
                    time.sleep(self._backoff_factor * (2 ** attempt) + random.uniform(0, 1))
                    continue
                if "404" in str(exc):
                    return None
                raise

            if status == 200:
                return raw.decode("utf-8", errors="replace")
            if status == 404:
                return None

        return None

    def fetch_latest_release(self, owner: str, repo: str) -> Optional[ReleaseInfo]:
        """获取最新 Release。404 = 仓库无发布，返回 None。"""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/releases/latest"
        try:
            data, status, _ = self._request("GET", url)
        except RuntimeError as exc:
            if "404" in str(exc):
                return None
            raise
        if status == 404 or not data.get("tag_name"):
            return None
        return ReleaseInfo(
            tag_name=data["tag_name"],
            name=data.get("name"),
            body=data.get("body"),
            created_at=_parse_datetime(data["created_at"]) or datetime.now(timezone.utc),
            html_url=data["html_url"],
        )

    def fetch_full_repo_data(self, owner: str, repo: str) -> GitHubRepoData:
        """获取完整的仓库数据（metadata + README + latest release）。"""
        metadata = self.fetch_repo_metadata(owner, repo)
        readme = self.fetch_readme(owner, repo)
        latest_release = self.fetch_latest_release(owner, repo)
        # 最后一请求的 rate limit 已在各方法中记录，此处不再单独请求
        return GitHubRepoData(
            metadata=metadata,
            readme=readme,
            latest_release=latest_release,
            rate_limit_remaining=None,
            rate_limit_reset=None,
        )


# ── 解析器 ───────────────────────────────────────────────


def parse_repo_input(repo_input: str) -> tuple[str, str]:
    """解析 GitHub 仓库输入，返回 (owner, repo)。

    支持格式：
      owner/repo
      https://github.com/owner/repo
      https://github.com/owner/repo/
      github.com/owner/repo
    """
    repo_input = repo_input.strip().rstrip("/")
    # 去掉协议和域名
    repo_input = re.sub(r"^https?://", "", repo_input)
    repo_input = re.sub(r"^github\.com/", "", repo_input)
    parts = repo_input.split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError(f"无效的 GitHub 仓库格式: {repo_input!r}，期望 owner/repo")
    return parts[0], parts[1]


# ── 快捷函数 ─────────────────────────────────────────────


def fetch_full_repo_data(repo_input: str) -> GitHubRepoData:
    """解析 repo_input，获取完整仓库数据。"""
    owner, repo = parse_repo_input(repo_input)
    client = GitHubAPIClient()
    return client.fetch_full_repo_data(owner, repo)


def fetch_repo_metadata(repo_input: str) -> RepoMetadata:
    """解析 repo_input，获取仓库元数据。"""
    owner, repo = parse_repo_input(repo_input)
    client = GitHubAPIClient()
    return client.fetch_repo_metadata(owner, repo)


def fetch_readme(repo_input: str) -> Optional[str]:
    """解析 repo_input，获取 README 原文。"""
    owner, repo = parse_repo_input(repo_input)
    client = GitHubAPIClient()
    return client.fetch_readme(owner, repo)


def fetch_latest_release(repo_input: str) -> Optional[ReleaseInfo]:
    """解析 repo_input，获取最新 Release。"""
    owner, repo = parse_repo_input(repo_input)
    client = GitHubAPIClient()
    return client.fetch_latest_release(owner, repo)


# ── 工具函数 ─────────────────────────────────────────────


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        # GitHub API 格式: 2026-05-08T12:34:56Z
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
