# GitHub AI 过滤与今日重点混排 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 只保留 AI 相关 GitHub Trending 项目，并让“今日重点”在新闻与 GitHub 之间保持混排。

**Architecture:** 在 GitHub collector 层做规则过滤，避免无关项目进入后续排序；在 `SectionPicker` 层做配额式混排，确保重点栏目不被单一来源占满。

**Tech Stack:** Python 3、`unittest`、标准库 `re`

---

### Task 1: GitHub Collector 增加 AI 相关过滤

**Files:**
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/collectors/github.py`
- Modify: `/mnt/d/AIcodes/openclaw/tests/test_collectors.py`

- [ ] 先写失败测试，覆盖 AI 项目保留和泛工具过滤
- [ ] 跑测试确认当前失败
- [ ] 最小实现关键词过滤
- [ ] 跑 collector 测试确认通过

### Task 2: SectionPicker 改成显式混排

**Files:**
- Modify: `/mnt/d/AIcodes/openclaw/ai_digest/section_picker.py`
- Modify: `/mnt/d/AIcodes/openclaw/tests/test_section_picker.py`

- [ ] 先写失败测试，覆盖“今日重点”包含新闻与 GitHub
- [ ] 跑测试确认当前失败
- [ ] 最小实现混排选取逻辑
- [ ] 跑 section picker 测试确认通过

### Task 3: 全量回归与真实验证

**Files:**
- Test: `/mnt/d/AIcodes/openclaw/tests`

- [ ] 跑全量测试
- [ ] 用真实 Trending 页面验证 GitHub 项目确实能进栏
