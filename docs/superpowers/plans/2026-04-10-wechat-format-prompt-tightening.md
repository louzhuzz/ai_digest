# 微信公众号格式约束与 Prompt 收紧 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收紧 ARK 的 Markdown 输出格式，并扩展本地 Markdown 转 HTML 转换器以更贴合微信公众号发布。

**Architecture:** 继续保留“LLM 输出受控 Markdown -> 本地转换 HTML -> 微信草稿接口”的主路径。通过更严格的系统提示词限制 LLM 只使用受支持格式，再在转换器中补齐 `###`、有序列表和 `**加粗**`。

**Tech Stack:** Python 3、`unittest`、标准库 `re`

---

### Task 1: 扩展 Markdown 转 HTML 支持范围

**Files:**
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/publishers/wechat.py`
- Modify: `/mnt/d/AIcodes/openclaw/tests/test_wechat_publisher.py`

- [ ] 先写失败测试，覆盖 `###`、`1.`、`**加粗**`
- [ ] 跑测试确认当前失败
- [ ] 最小实现转换器支持
- [ ] 跑相关测试确认通过

### Task 2: 收紧 ARK 系统提示词

**Files:**
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/llm_writer.py`
- Modify: `/mnt/d/AIcodes/openclaw/tests/test_llm_writer.py`

- [ ] 先写失败测试，检查系统提示词包含“允许格式”和“禁止格式”
- [ ] 跑测试确认当前失败
- [ ] 最小修改 `SYSTEM_PROMPT`
- [ ] 跑相关测试确认通过

### Task 3: 全量回归

**Files:**
- Test: `/mnt/d/AIcodes/openclaw/tests`

- [ ] 运行全量测试
- [ ] 确认发布链路相关测试仍然通过
