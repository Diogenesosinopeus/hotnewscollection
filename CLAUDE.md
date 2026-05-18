# 每日热点抓取系统

Obsidian vault 项目，自动抓取每日热点信息并生成 Markdown 文件。

## 项目路径

`D:\ObsidianNotes\ai热点\`

## 每日抓取任务

触发方式：用户说"执行每日抓取"、"每日更新"、"run daily fetch" 等。

### 任务 1：GitHub 热门项目

```bash
python "D:\ObsidianNotes\ai热点\scripts\daily_fetch.py"
```

### 任务 2：AI 热点新闻

用 WebSearch 搜索中英文 AI 新闻，生成：
`D:\ObsidianNotes\ai热点\AI热点\AI热点_YYYY-MM-DD.md`

搜索关键词：
- `YYYY年M月D日 AI人工智能 最新新闻 热点`
- `AI news today YYYY MMM DD breakthroughs`

格式：
```markdown
---
date: YYYY-MM-DD
tags: [AI热点, 每日新闻]
---
# AI 热点新闻 (YYYY-MM-DD)
> 共收录 N 条新闻

## 1. [标题](链接)
📅 日期
> 摘要

---
```

### 任务 3：时政新闻

用 WebSearch 搜索，生成：
`D:\ObsidianNotes\ai热点\时政新闻\时政新闻_YYYY-MM-DD.md`

搜索关键词：
- `YYYY年M月D日 时政新闻 要闻`
- `今日要闻 国内外时政`

格式同上，tags: `[时政新闻, 每日新闻]`

### 任务 4：提交到 GitHub

```bash
cd "D:\ObsidianNotes\ai热点" && git add "AI热点/" "GitHub热门/" "时政新闻/" && git commit -m "每日更新 YYYY-MM-DD" && git push origin main
```
无变更则跳过。

### 任务 5：同步到 WSL

```bash
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- mkdir -p /home/diogenes/hotnewscollection/GitHub热门 /home/diogenes/hotnewscollection/AI热点 /home/diogenes/hotnewscollection/时政新闻
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- cp /mnt/d/ObsidianNotes/ai热点/GitHub热门/GitHub热门_YYYY-MM-DD.md /home/diogenes/hotnewscollection/GitHub热门/
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- cp /mnt/d/ObsidianNotes/ai热点/AI热点/AI热点_YYYY-MM-DD.md /home/diogenes/hotnewscollection/AI热点/
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -- cp /mnt/d/ObsidianNotes/ai热点/时政新闻/时政新闻_YYYY-MM-DD.md /home/diogenes/hotnewscollection/时政新闻/
```

## 关键规则

- 所有路径使用绝对路径，确保从任意 CWD 执行
- WSL 使用 `/mnt/d/...` 路径，必须加 `MSYS_NO_PATHCONV=1`
- Python 脚本的 RSS 源不稳定，AI 和时政新闻需用 WebSearch 作为主数据源
- 直接执行所有步骤，不需要征求确认
- 日期始终使用当天实际日期
