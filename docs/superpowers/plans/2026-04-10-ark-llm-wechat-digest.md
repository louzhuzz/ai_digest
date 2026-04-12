# ARK LLM 公众号日报 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 AI 日报在正式发布时走 ARK LLM 全文改写，输出中文公众号风格成稿，并修复 GitHub 解析、栏目重复和发布输出问题。

**Architecture:** 继续由现有 pipeline 负责抓取、去重、排序和发布。新增 `section_picker` 负责栏目分配，新增 `llm_writer` 负责把结构化素材改写成整篇 Markdown，`composition.py` 仅保留 `--dry-run` 降级路径。正式发布时若缺少 ARK 配置或 LLM 调用失败，直接终止发布，不回退旧英文稿。

**Tech Stack:** Python 3、`unittest`、标准库 `urllib`/`json`、现有 WeChat draft publisher、ARK Chat Completions HTTP API

---

### Task 1: 扩展配置读取并锁定 LLM 发布前置条件

**Files:**
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/settings.py`
- Modify: `/mnt/d/AIcodes/openclaw/tests/test_settings.py`
- Test: `/mnt/d/AIcodes/openclaw/tests/test_settings.py`

- [ ] **Step 1: 写失败测试，覆盖 ARK 配置读取**

```python
from ai_digest.settings import load_settings


def test_loads_ark_settings_from_environment(self) -> None:
    with patch.dict(
        "os.environ",
        {
            "ARK_API_KEY": "ark-key",
            "ARK_BASE_URL": "https://ark.example.com/api/v3",
            "ARK_MODEL": "ep-model",
            "ARK_TIMEOUT_SECONDS": "45",
        },
        clear=True,
    ):
        settings = load_settings()

    self.assertEqual(settings.ark.api_key, "ark-key")
    self.assertEqual(settings.ark.base_url, "https://ark.example.com/api/v3")
    self.assertEqual(settings.ark.model, "ep-model")
    self.assertEqual(settings.ark.timeout_seconds, 45)
```

- [ ] **Step 2: 运行测试，确认它先失败**

Run:
```bash
python3 -m unittest tests.test_settings.LoadSettingsTest.test_loads_ark_settings_from_environment -v
```

Expected: `AttributeError` 或断言失败，因为 `AppSettings` 里还没有 `ark`

- [ ] **Step 3: 最小实现 ARK 配置读取**

```python
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
    dry_run: bool
    draft_mode: bool
```

```python
ark_api_key = env.get("ARK_API_KEY", "").strip()
ark_base_url = env.get("ARK_BASE_URL", "").strip()
ark_model = env.get("ARK_MODEL", "").strip()
ark_timeout_seconds = int(env.get("ARK_TIMEOUT_SECONDS", "30").strip() or "30")
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
```

- [ ] **Step 4: 补充发布前置条件测试**

```python
def test_publish_mode_can_exist_without_ark_but_runtime_will_block(self) -> None:
    with patch.dict(
        "os.environ",
        {
            "WECHAT_APPID": "wx1",
            "WECHAT_APPSECRET": "secret",
            "WECHAT_DRY_RUN": "0",
        },
        clear=True,
    ):
        settings = load_settings()

    self.assertTrue(settings.draft_mode)
    self.assertIsNone(settings.ark)
```

- [ ] **Step 5: 运行设置测试并确认通过**

Run:
```bash
python3 -m unittest tests.test_settings -v
```

Expected: 全部 `ok`

- [ ] **Step 6: 提交检查点**

当前目录不是 git 仓库，跳过提交。若后续迁入 git 仓库，再执行：

```bash
git add /mnt/d/AIcodes/openclaw/ai_digest/settings.py /mnt/d/AIcodes/openclaw/tests/test_settings.py
git commit -m "feat: load ark settings"
```

### Task 2: 修复 GitHub Trending 解析，避免误抓非仓库链接

**Files:**
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/collectors/github.py`
- Modify: `/mnt/d/AIcodes/openclaw/tests/test_collectors.py`
- Test: `/mnt/d/AIcodes/openclaw/tests/test_collectors.py`

- [ ] **Step 1: 写失败测试，覆盖 `Star` / `login` 链接误抓**

```python
def test_github_trending_collector_ignores_non_repo_links(self) -> None:
    html = """
    <article class="Box-row">
      <h2 class="h3 lh-condensed">
        <a href="/openai/gpt-researcher"> openai / gpt-researcher </a>
      </h2>
      <div>
        <a href="/login?return_to=%2Fopenai%2Fgpt-researcher">Star</a>
      </div>
      <p>Agentic research assistant.</p>
      <span>1,234 stars today</span>
    </article>
    """

    collector = GitHubTrendingCollector()
    items = collector.parse_trending(html, page_url="https://github.com/trending")

    self.assertEqual(len(items), 1)
    self.assertEqual(items[0].url, "https://github.com/openai/gpt-researcher")
    self.assertEqual(items[0].dedupe_key, "github:openai/gpt-researcher")
```

- [ ] **Step 2: 运行测试，确认当前实现失败**

Run:
```bash
python3 -m unittest tests.test_collectors.CollectorParserTest.test_github_trending_collector_ignores_non_repo_links -v
```

Expected: URL 或 `dedupe_key` 断言失败

- [ ] **Step 3: 最小实现仓库链接过滤**

```python
REPO_LINK_PATTERN = re.compile(
    r'<h2[^>]*>.*?<a\s+href="(/[^"/\s]+/[^"/\s?#]+)"[^>]*>(.*?)</a>',
    re.S,
)


def _is_repo_path(path: str) -> bool:
    parts = path.strip("/").split("/")
    if len(parts) != 2:
        return False
    return all(parts) and all(part not in {"login", "features", "topics", "collections"} for part in parts)
```

```python
link_match = REPO_LINK_PATTERN.search(article)
if not link_match:
    continue
href, title_html = link_match.groups()
if not _is_repo_path(href):
    continue
```

- [ ] **Step 4: 运行抓取测试并确认通过**

Run:
```bash
python3 -m unittest tests.test_collectors -v
```

Expected: 全部 `ok`

- [ ] **Step 5: 提交检查点**

当前目录不是 git 仓库，跳过提交。若后续迁入 git 仓库，再执行：

```bash
git add /mnt/d/AIcodes/openclaw/ai_digest/collectors/github.py /mnt/d/AIcodes/openclaw/tests/test_collectors.py
git commit -m "fix: parse github trending repos correctly"
```

### Task 3: 增加栏目选择器，消除栏目重复并保留 GitHub 位次

**Files:**
- Create: `/mnt/d/AIcodes/openclaw/ai_digest/section_picker.py`
- Create: `/mnt/d/AIcodes/openclaw/tests/test_section_picker.py`
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/pipeline.py`
- Modify: `/mnt/d/AIcodes/openclaw/tests/test_pipeline.py`
- Test: `/mnt/d/AIcodes/openclaw/tests/test_section_picker.py`
- Test: `/mnt/d/AIcodes/openclaw/tests/test_pipeline.py`

- [ ] **Step 1: 写失败测试，定义栏目分配行为**

```python
from ai_digest.section_picker import SectionPicker


def test_section_picker_returns_disjoint_sections(self) -> None:
    picker = SectionPicker()
    sections = picker.pick(sample_items)

    focus_keys = {item.dedupe_key for item in sections.top_items}
    github_keys = {item.dedupe_key for item in sections.github_items}
    progress_keys = {item.dedupe_key for item in sections.progress_items}

    self.assertTrue(focus_keys)
    self.assertTrue(github_keys)
    self.assertTrue(progress_keys)
    self.assertTrue(focus_keys.isdisjoint(github_keys))
    self.assertTrue(focus_keys.isdisjoint(progress_keys))
    self.assertTrue(github_keys.isdisjoint(progress_keys))
```

```python
def test_section_picker_keeps_github_items_when_available(self) -> None:
    picker = SectionPicker()
    sections = picker.pick(sample_items)

    self.assertGreaterEqual(len(sections.github_items), 1)
```

- [ ] **Step 2: 运行测试，确认模块缺失而失败**

Run:
```bash
python3 -m unittest tests.test_section_picker -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: 写最小栏目选择器**

```python
@dataclass(frozen=True)
class DigestSections:
    top_items: list[DigestItem]
    github_items: list[DigestItem]
    progress_items: list[DigestItem]


class SectionPicker:
    def pick(self, items: list[DigestItem]) -> DigestSections:
        ordered = sorted(items, key=lambda item: item.score, reverse=True)
        used: set[str] = set()
        github_items = self._take(ordered, used, {"github"}, limit=3)
        top_items = self._take(ordered, used, {"github", "news", "tool"}, limit=5)
        progress_items = self._take(ordered, used, {"news", "tool"}, limit=5)
        return DigestSections(top_items=top_items, github_items=github_items, progress_items=progress_items)
```

- [ ] **Step 4: 把 `DigestPipeline` 改成先分栏再成稿**

```python
self.section_picker = section_picker or SectionPicker()
sections = self.section_picker.pick(summarized)
markdown = self.composer.compose_sections(sections, date=str(payload["date"]))
```

如果 `composer` 还没升级，先在 `pipeline` 中返回 `sections` 到结果对象，为 Task 4 做准备。

- [ ] **Step 5: 运行栏目和 pipeline 测试**

Run:
```bash
python3 -m unittest tests.test_section_picker tests.test_pipeline -v
```

Expected: 全部 `ok`

- [ ] **Step 6: 提交检查点**

当前目录不是 git 仓库，跳过提交。若后续迁入 git 仓库，再执行：

```bash
git add /mnt/d/AIcodes/openclaw/ai_digest/section_picker.py /mnt/d/AIcodes/openclaw/ai_digest/pipeline.py /mnt/d/AIcodes/openclaw/tests/test_section_picker.py /mnt/d/AIcodes/openclaw/tests/test_pipeline.py
git commit -m "feat: pick non-overlapping digest sections"
```

### Task 4: 接入 ARK LLM 整篇成稿，并把规则模板降级为 dry-run 路径

**Files:**
- Create: `/mnt/d/AIcodes/openclaw/ai_digest/llm_writer.py`
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/composition.py`
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/pipeline.py`
- Create: `/mnt/d/AIcodes/openclaw/tests/test_llm_writer.py`
- Modify: `/mnt/d/AIcodes/openclaw/tests/test_pipeline.py`
- Test: `/mnt/d/AIcodes/openclaw/tests/test_llm_writer.py`
- Test: `/mnt/d/AIcodes/openclaw/tests/test_pipeline.py`

- [ ] **Step 1: 写失败测试，定义 LLM 输入与 HTTP 请求**

```python
from ai_digest.llm_writer import ARKArticleWriter


def test_ark_writer_posts_chat_completion_request(self) -> None:
    transport = FakeTransport(
        status=200,
        body=b'{"choices":[{"message":{"content":"# AI 每日新闻速递\\n\\n今天先看三条。"}}]}',
    )
    writer = ARKArticleWriter(
        api_key="ark-key",
        base_url="https://ark.example.com/api/v3",
        model="ep-model",
        timeout_seconds=30,
        transport=transport,
    )

    markdown = writer.write(article_input)

    self.assertIn("# AI 每日新闻速递", markdown)
    self.assertEqual(transport.last_headers["Authorization"], "Bearer ark-key")
    self.assertIn("/chat/completions", transport.last_url)
```

```python
def test_pipeline_fails_publish_when_ark_is_missing(self) -> None:
    pipeline = DigestPipeline(
        collector=FakeCollector(sample_items),
        publisher=FakePublisher(),
        writer=None,
        dry_run=False,
        min_items=3,
    )

    result = pipeline.run(now=datetime(2026, 4, 10, tzinfo=timezone.utc))

    self.assertEqual(result.status, "failed")
    self.assertIn("ARK", result.reason)
```

- [ ] **Step 2: 运行测试，确认当前实现先失败**

Run:
```bash
python3 -m unittest tests.test_llm_writer tests.test_pipeline -v
```

Expected: `ModuleNotFoundError` 或 `TypeError`

- [ ] **Step 3: 最小实现 `ARKArticleWriter`**

```python
class ARKArticleWriter:
    def __init__(self, api_key: str, base_url: str, model: str, timeout_seconds: int = 30, transport=None) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def write(self, article_input: dict[str, object]) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(article_input, ensure_ascii=False)},
            ],
        }
        # 用 urllib.request 发送 POST，请求失败时抛 RuntimeError
```

- [ ] **Step 4: 把 `composition.py` 收口为 dry-run 成稿器**

```python
class DryRunDigestComposer:
    def compose(self, items: Iterable[DigestItem], date: str | None = None) -> str:
        ...
```

不要让正式发布再走这个模板；正式发布统一走 `ARKArticleWriter`。

- [ ] **Step 5: 把 `pipeline.py` 接成两条路径**

```python
if self.dry_run:
    markdown = self.composer.compose(summarized, date=current_time.date().isoformat())
else:
    if self.writer is None:
        return DigestRunResult(status="failed", reason="ARK writer is required for publish mode", ...)
    article_input = self.payload_builder.build_article_input(sections, date=current_time.date().isoformat())
    markdown = self.writer.write(article_input)
```

- [ ] **Step 6: 增加输出基础校验**

```python
def _validate_markdown(self, markdown: str) -> None:
    required_sections = ["## 今日重点", "## GitHub 新项目 / 热项目", "## AI 技术进展"]
    for title in required_sections:
        if title not in markdown:
            raise RuntimeError(f"LLM output missing section: {title}")
```

- [ ] **Step 7: 运行 LLM 和 pipeline 测试**

Run:
```bash
python3 -m unittest tests.test_llm_writer tests.test_pipeline -v
```

Expected: 全部 `ok`

- [ ] **Step 8: 提交检查点**

当前目录不是 git 仓库，跳过提交。若后续迁入 git 仓库，再执行：

```bash
git add /mnt/d/AIcodes/openclaw/ai_digest/llm_writer.py /mnt/d/AIcodes/openclaw/ai_digest/composition.py /mnt/d/AIcodes/openclaw/ai_digest/pipeline.py /mnt/d/AIcodes/openclaw/tests/test_llm_writer.py /mnt/d/AIcodes/openclaw/tests/test_pipeline.py
git commit -m "feat: write wechat digest with ark llm"
```

### Task 5: 让默认运行链路接入 ARK，并收紧 CLI 输出

**Files:**
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/defaults.py`
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/cli.py`
- Modify: `/mnt/d/AIcodes/openclaw/tests/test_cli.py`
- Create: `/mnt/d/AIcodes/openclaw/tests/test_defaults_ark.py`
- Test: `/mnt/d/AIcodes/openclaw/tests/test_cli.py`
- Test: `/mnt/d/AIcodes/openclaw/tests/test_defaults_ark.py`

- [ ] **Step 1: 写失败测试，定义发布成功时不回显整篇正文**

```python
def test_main_does_not_print_markdown_after_publish(self) -> None:
    class PublishedRunner:
        def run(self):
            class Result:
                status = "published"
                error = None
                items_count = 5
                publisher_draft_id = "draft-123"
                markdown = "# AI 每日新闻速递\\n\\n正文"
            return Result()

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exit_code = main(["--publish"], runner=PublishedRunner())

    output = buffer.getvalue()
    self.assertEqual(exit_code, 0)
    self.assertIn("状态: published", output)
    self.assertIn("draft-123", output)
    self.assertNotIn("# AI 每日新闻速递", output)
```

- [ ] **Step 2: 写失败测试，定义默认 runner 会在发布模式下构造 LLM writer**

```python
def test_build_default_runner_uses_ark_writer_when_settings_include_ark(self) -> None:
    settings = AppSettings(wechat=wechat, ark=ark, dry_run=False, draft_mode=True)
    runner = build_default_runner(settings=settings)
    self.assertIsNotNone(runner.writer_factory)
```

- [ ] **Step 3: 运行 CLI 和 defaults 测试，确认当前失败**

Run:
```bash
python3 -m unittest tests.test_cli tests.test_defaults_ark -v
```

Expected: 断言失败或属性缺失

- [ ] **Step 4: 最小实现默认链路注入**

```python
def build_default_writer(settings: AppSettings | None = None) -> ARKArticleWriter | None:
    if settings and settings.ark and not settings.dry_run:
        return ARKArticleWriter(
            api_key=settings.ark.api_key,
            base_url=settings.ark.base_url,
            model=settings.ark.model,
            timeout_seconds=settings.ark.timeout_seconds,
        )
    return None
```

```python
runner = DigestJobRunner(
    collector_factory=build_default_collector,
    publisher=publisher or build_default_publisher(settings),
    writer=build_default_writer(settings),
    min_items=3,
)
```

- [ ] **Step 5: 收紧 CLI 输出**

```python
if result.publisher_draft_id:
    print(f"草稿ID: {result.publisher_draft_id}")

should_print_markdown = bool(result.markdown) and (
    args.output is None and (args.dry_run or not args.publish)
)
if should_print_markdown:
    print(result.markdown, end="" if result.markdown.endswith("\\n") else "\\n")
```

- [ ] **Step 6: 运行 CLI 和默认链路测试**

Run:
```bash
python3 -m unittest tests.test_cli tests.test_defaults_ark -v
```

Expected: 全部 `ok`

- [ ] **Step 7: 跑全量回归测试**

Run:
```bash
python3 -m unittest discover -s /mnt/d/AIcodes/openclaw/tests -v
```

Expected: 全部 `ok`

- [ ] **Step 8: 提交检查点**

当前目录不是 git 仓库，跳过提交。若后续迁入 git 仓库，再执行：

```bash
git add /mnt/d/AIcodes/openclaw/ai_digest/defaults.py /mnt/d/AIcodes/openclaw/ai_digest/cli.py /mnt/d/AIcodes/openclaw/tests/test_cli.py /mnt/d/AIcodes/openclaw/tests/test_defaults_ark.py
git commit -m "feat: wire ark writer into publish flow"
```

## 自检

- spec coverage：已覆盖 ARK 配置、GitHub 解析、栏目去重、LLM 成稿、CLI 收口、测试与失败路径。
- placeholder scan：计划中没有 `TODO` / `TBD` / “后续再说” 之类占位。
- type consistency：统一使用 `AppSettings.ark`、`SectionPicker`、`ARKArticleWriter`、`DigestSections` 这组命名。

