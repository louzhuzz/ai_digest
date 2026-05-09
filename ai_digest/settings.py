from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_dotenv_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


@dataclass(frozen=True)
class WeChatCredentials:
    appid: str
    appsecret: str
    thumb_media_id: str = ""


@dataclass(frozen=True)
class ArkCredentials:
    api_key: str
    base_url: str
    model: str
    timeout_seconds: int = 30


@dataclass(frozen=True)
class AppSettings:
    wechat: WeChatCredentials | None
    ark: ArkCredentials | None
    github_token: str
    dry_run: bool
    draft_mode: bool
    llm_enabled: bool
    state_db_path: Path = Path("data/state.db")
    keywords: tuple[str, ...] = ()  # 监控关键词列表，逗号分隔


def load_settings(environ: dict[str, str] | None = None) -> AppSettings:
    env = dict(_parse_dotenv_file(Path.cwd() / ".env"))
    env.update(os.environ if environ is None else environ)
    appid = env.get("WECHAT_APPID", "").strip()
    appsecret = env.get("WECHAT_APPSECRET", "").strip()
    thumb_media_id = env.get("WECHAT_THUMB_MEDIA_ID", "").strip()
    ark_api_key = env.get("ARK_API_KEY", "").strip()
    ark_base_url = env.get("ARK_BASE_URL", "").strip()
    ark_model = env.get("ARK_MODEL", "").strip()
    ark_timeout_seconds = int((env.get("ARK_TIMEOUT_SECONDS", "30") or "30").strip())
    dry_run = _as_bool(env.get("WECHAT_DRY_RUN"), default=True if not appid or not appsecret else False)
    draft_mode = bool(appid and appsecret and not dry_run)
    wechat = (
        WeChatCredentials(appid=appid, appsecret=appsecret, thumb_media_id=thumb_media_id)
        if appid and appsecret
        else None
    )
    ark = (
        ArkCredentials(
            api_key=ark_api_key,
            base_url=ark_base_url,
            model=ark_model,
            timeout_seconds=ark_timeout_seconds,
        )
        if ark_api_key and ark_base_url and ark_model
        else None
    )
    state_db_path = Path(env.get("AI_DIGEST_STATE_DB", "data/state.db"))
    keywords_raw = env.get("AI_DIGEST_KEYWORDS", "").strip()
    keywords = tuple(k.strip() for k in keywords_raw.split(",") if k.strip())
    llm_enabled = bool(ark_api_key and ark_base_url and ark_model)
    github_token = env.get("GITHUB_TOKEN", "").strip()
    return AppSettings(
        wechat=wechat,
        ark=ark,
        github_token=github_token,
        dry_run=dry_run,
        draft_mode=draft_mode,
        llm_enabled=llm_enabled,
        state_db_path=state_db_path,
        keywords=keywords,
    )
