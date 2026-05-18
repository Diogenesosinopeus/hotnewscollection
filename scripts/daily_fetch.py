#!/usr/bin/env python3
"""每日抓取脚本：GitHub热门项目 + AI热点新闻 + 时政新闻
输出 Obsidian 兼容的 Markdown 文件到 vault 根目录。
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ── 配置 ──────────────────────────────────────────────
VAULT_DIR = Path(__file__).resolve().parent.parent  # Obsidian vault 根目录
CONFIG_FILE = Path(__file__).with_name("config.json")

DEFAULT_CONFIG = {
    "github": {
        "per_page": 20,
        "language_filter": "",  # 留空=全部语言, 或如 "python", "javascript"
        "date_range_days": 7,
    },
    "output": {
        "date_format": "%Y-%m-%d",
        "subdir": "",  # 留空=根目录, 或如 "Daily/" 存到子目录
    },
    "news": {
        "ai_sources": [
            "https://www.36kr.com/search/articles/人工智能",
            "https://rsshub.app/huggingface/daily-papers",
        ],
        "shizheng_sources": [
            "https://rsshub.app/xinhua/news",
        ],
    },
}


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            # merge with defaults
            merged = DEFAULT_CONFIG.copy()
            merged.update(cfg)
            return merged
    return DEFAULT_CONFIG


# ── GitHub 热门项目 ───────────────────────────────────
def fetch_github_trending(cfg):
    """通过 GitHub Search API 抓取近期最高 star 增长的项目。"""
    days = cfg["github"]["date_range_days"]
    per_page = cfg["github"]["per_page"]
    lang = cfg["github"].get("language_filter", "")
    date_since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    query = f"created:>{date_since}"
    if lang:
        query += f"+language:{lang}"

    url = (
        f"https://api.github.com/search/repositories"
        f"?q={query}&sort=stars&order=desc&per_page={per_page}"
    )

    # 如果用 GITHUB_TOKEN 可以提升 rate limit
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "DailyTrendFetcher/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
    except HTTPError as e:
        print(f"[GitHub] HTTP {e.code}: {e.reason}")
        return []
    except URLError as e:
        print(f"[GitHub] 网络错误: {e.reason}")
        return []

    repos = []
    for item in data.get("items", []):
        repos.append({
            "name": item["full_name"],
            "url": item["html_url"],
            "stars": item["stargazers_count"],
            "description": (item.get("description") or "无描述").replace("|", "\\|"),
            "language": item.get("language") or "N/A",
            "forks": item["forks_count"],
            "topics": item.get("topics", []),
            "created_at": item["created_at"],
        })
    return repos


def write_github_md(repos, date_str):
    """将 GitHub 热门项目写入 Obsidian 兼容的 Markdown 文件。"""
    lines = [
        "---",
        f"date: {date_str}",
        "tags: [GitHub, 开源项目, 每日热门]",
        "---",
        "",
        f"# GitHub 热门项目 ({date_str})",
        "",
        f"> 数据来源: GitHub Search API，按近期 star 增长排序",
        f"> 共收录 {len(repos)} 个项目",
        "",
    ]

    for i, r in enumerate(repos, 1):
        stars_badge = f"⭐ {r['stars']:,}" if r['stars'] else "⭐ new"
        lines.extend([
            f"## {i}. [{r['name']}]({r['url']})",
            "",
            f"**{stars_badge}** | 语言: {r['language']} | Forks: {r['forks']:,}",
            "",
            f"> {r['description']}",
            "",
        ])
        if r["topics"]:
            tags = " ".join(f"`{t}`" for t in r["topics"][:8])
            lines.append(f"标签: {tags}")
            lines.append("")
        lines.append("---")
        lines.append("")

    output_path = VAULT_DIR / "GitHub热门" / f"GitHub热门_{date_str}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[GitHub] 已写入: {output_path}")
    return output_path


# ── 通用新闻抓取（RSS / API） ──────────────────────────
def fetch_news_from_sources(sources, label):
    """从 RSS 源抓取新闻标题和链接。返回标题列表。"""
    import xml.etree.ElementTree as ET

    items = []
    for url in sources:
        try:
            req = Request(url, headers={"User-Agent": "DailyTrendFetcher/1.0"})
            with urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            # 尝试 RSS/XML 解析
            root = ET.fromstring(raw)
            for entry in root.iter("item"):
                title = entry.findtext("title", "")
                link = entry.findtext("link", "")
                desc = entry.findtext("description", "")
                pub_date = entry.findtext("pubDate", "")
                if title:
                    items.append({
                        "title": title.strip(),
                        "url": link.strip() if link else "",
                        "description": (desc or "").strip()[:300],
                        "date": pub_date.strip() if pub_date else "",
                    })
            if items:
                print(f"  [{label}] 从 {url} 获取到 {len(items)} 条")
            else:
                print(f"  [{label}] {url} 无 RSS item，尝试 JSON 解析...")
                # 尝试 JSON 格式（RSSHub 等）
                items = _parse_json_feed(raw, label)
        except ET.ParseError:
            print(f"  [{label}] {url} XML 解析失败，尝试 JSON...")
            items = _parse_json_feed(raw, label)
        except Exception as e:
            print(f"  [{label}] {url} 错误: {e}")

    return items


def _parse_json_feed(raw_text, label):
    """解析 JSON 格式的 feed（如 RSSHub）。"""
    items = []
    try:
        data = json.loads(raw_text)
        entries = data.get("items") or data.get("entries") or data.get("data") or []
        if isinstance(entries, dict):
            entries = list(entries.values())
        for entry in entries[:30]:
            title = entry.get("title") or entry.get("name") or ""
            url = entry.get("url") or entry.get("link") or ""
            desc = entry.get("description") or entry.get("summary") or entry.get("content_text") or ""
            pub_date = entry.get("date_published") or entry.get("pubDate") or ""
            if title:
                items.append({
                    "title": str(title).strip(),
                    "url": str(url).strip() if url else "",
                    "description": str(desc).strip()[:300],
                    "date": str(pub_date).strip() if pub_date else "",
                })
        print(f"  [{label}] JSON 解析得到 {len(items)} 条")
    except json.JSONDecodeError:
        print(f"  [{label}] JSON 解析也失败了")
    return items


def write_news_md(items, date_str, category, title_label):
    """将新闻列表写入 Markdown 文件。"""
    lines = [
        "---",
        f"date: {date_str}",
        f"tags: [{category}, 每日新闻]",
        "---",
        "",
        f"# {title_label} ({date_str})",
        "",
        f"> 共收录 {len(items)} 条新闻",
        "",
    ]

    for i, item in enumerate(items[:20], 1):
        title = item["title"]
        url = item["url"]
        desc = item.get("description", "")
        news_date = item.get("date", "")

        if url:
            lines.append(f"## {i}. [{title}]({url})")
        else:
            lines.append(f"## {i}. {title}")

        if news_date:
            lines.append(f"📅 {news_date}")
            lines.append("")
        if desc:
            # 清理 HTML 标签
            import re
            clean_desc = re.sub(r"<[^>]+>", "", desc)[:350]
            lines.append(f"> {clean_desc}")
            lines.append("")
        lines.append("---")
        lines.append("")

    output_path = VAULT_DIR / category / f"{category}_{date_str}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[{category}] 已写入: {output_path}")
    return output_path


# ── 主流程 ────────────────────────────────────────────
def main():
    global cfg
    cfg = load_config()
    today = datetime.now().strftime(cfg["output"]["date_format"])

    print(f"=== 每日抓取开始 ({today}) ===")
    results = {}

    # 1. GitHub 热门项目
    print("\n[1/3] 抓取 GitHub 热门项目...")
    repos = fetch_github_trending(cfg)
    if repos:
        results["github"] = write_github_md(repos, today)
    else:
        print("[GitHub] 未获取到数据（可能触发 API 限流）")

    # 2. AI 热点新闻
    print("\n[2/3] 抓取 AI 热点新闻...")
    ai_sources = cfg["news"].get("ai_sources", [])
    ai_items = fetch_news_from_sources(ai_sources, "AI")
    if ai_items:
        results["ai"] = write_news_md(ai_items, today, "AI热点", "AI 热点新闻")
    else:
        print("[AI] 未获取到新闻，将生成模板文件供手动填充")
        write_news_md([], today, "AI热点", "AI 热点新闻")

    # 3. 时政新闻
    print("\n[3/3] 抓取时政新闻...")
    sz_sources = cfg["news"].get("shizheng_sources", [])
    sz_items = fetch_news_from_sources(sz_sources, "时政")
    if sz_items:
        results["shizheng"] = write_news_md(sz_items, today, "时政新闻", "时政新闻")
    else:
        print("[时政] 未获取到新闻，将生成模板文件供手动填充")
        write_news_md([], today, "时政新闻", "时政新闻")

    print(f"\n=== 抓取完成，共生成 {len(results)} 个文件 ===")
    for k, v in results.items():
        print(f"  {v}")

    return results


if __name__ == "__main__":
    main()
