#!/usr/bin/env python3
"""Generate weekly AI news markdown from public RSS feeds."""

from __future__ import annotations

import datetime as dt
import html
import pathlib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

FEEDS = [
    "https://feeds.feedburner.com/oreilly/radar",
    "https://www.marktechpost.com/feed/",
    "https://openai.com/news/rss.xml",
    "https://huggingface.co/blog/feed.xml",
]

MAX_ITEMS = 12
OUTPUT_DIR = pathlib.Path("content/zh/blog/ai-weekly")


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_xml(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "devlogs-ai-weekly-bot/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def parse_feed(feed_url: str) -> list[dict[str, str]]:
    raw = fetch_xml(feed_url)
    root = ET.fromstring(raw)

    items: list[dict[str, str]] = []
    # RSS format
    for item in root.findall(".//channel/item"):
        title = clean_text(item.findtext("title", default=""))
        link = clean_text(item.findtext("link", default=""))
        desc = clean_text(item.findtext("description", default=""))
        if title and link:
            items.append({"title": title, "link": link, "summary": desc})

    # Atom format fallback
    if not items:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall(".//atom:entry", ns):
            title = clean_text(entry.findtext("atom:title", default="", namespaces=ns))
            summary = clean_text(
                entry.findtext("atom:summary", default="", namespaces=ns)
                or entry.findtext("atom:content", default="", namespaces=ns)
            )
            link = ""
            for link_node in entry.findall("atom:link", ns):
                href = link_node.attrib.get("href", "")
                rel = link_node.attrib.get("rel", "alternate")
                if href and rel in {"alternate", ""}:
                    link = href
                    break
            if title and link:
                items.append({"title": title, "link": link, "summary": summary})

    return items


def build_weekly_markdown(news_items: list[dict[str, str]], today: dt.date) -> str:
    week_label = f"{today.isocalendar().year}-W{today.isocalendar().week:02d}"
    lines = [
        "---",
        f'title: "AI 快讯周报 · {week_label}"',
        f"date: {today.isoformat()}",
        "description: 自动采集生成的 AI 一周资讯速览",
        "categories: [\"AI\", \"周报\"]",
        "tags: [\"AI\", \"新闻\", \"自动化\"]",
        "---",
        "",
        f"本周共收集 {len(news_items)} 条 AI 资讯（自动生成）。",
        "",
    ]

    for idx, item in enumerate(news_items, start=1):
        domain = urllib.parse.urlparse(item["link"]).netloc
        summary = item["summary"][:160] + ("..." if len(item["summary"]) > 160 else "")
        summary_line = f"- 摘要：{summary}" if summary else "- 摘要：暂无摘要"
        lines.extend(
            [
                f"## {idx}. {item['title']}",
                f"- 来源：{domain}",
                summary_line,
                f"- 链接：{item['link']}",
                "",
            ]
        )

    lines.extend(
        [
            "---",
            "",
            "> 本文由 GitHub Actions 定时任务自动生成并提交。",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    today = dt.date.today()
    all_items: list[dict[str, str]] = []

    for feed in FEEDS:
        try:
            all_items.extend(parse_feed(feed))
        except Exception as err:  # noqa: BLE001
            print(f"[WARN] Failed to parse feed: {feed} -> {err}")

    deduped = []
    seen = set()
    for item in all_items:
        key = item["link"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= MAX_ITEMS:
            break

    if not deduped:
        deduped = [
            {
                "title": "本周自动抓取暂时不可用",
                "link": "https://github.com/CIPFZ/devlogs",
                "summary": "自动采集源暂时无法访问，建议稍后重试或手动补充本周 AI 重点资讯。",
            }
        ]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filename = OUTPUT_DIR / f"{today.isoformat()}-ai-weekly.md"
    filename.write_text(build_weekly_markdown(deduped, today), encoding="utf-8")
    print(f"Generated: {filename}")


if __name__ == "__main__":
    main()
