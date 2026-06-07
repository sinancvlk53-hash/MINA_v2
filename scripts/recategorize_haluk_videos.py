#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""haluk_video_list.json kategorilerini yeni kurallarla güncelle."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from signal_bot.haluk_video_categories import (
    CATEGORY_ORDER,
    categorize_video,
    category_stats,
)

OUT_JSON = os.path.join(_ROOT, "signal_bot", "history", "haluk_video_list.json")
OUT_MD = os.path.join(_ROOT, "signal_bot", "history", "haluk_video_list.md")
TR_TZ = timezone(timedelta(hours=3))


def write_markdown(videos: List[Dict[str, Any]], path: str, stats: Dict[str, int]) -> None:
    grouped: Dict[str, List[Dict[str, Any]]] = {c: [] for c in CATEGORY_ORDER}
    for v in videos:
        cat = v.get("category") or "Diğer"
        grouped.setdefault(cat, []).append(v)

    lines = [
        "# Haluk Hoca — Video Listesi",
        "",
        f"**Toplam:** {len(videos)} video",
        f"**Güncelleme:** {datetime.now(TR_TZ).strftime('%Y-%m-%d %H:%M')} (TR)",
        "",
        "## Grup İstatistikleri",
        "",
        "| Grup | Adet |",
        "|------|------|",
    ]
    for cat in CATEGORY_ORDER:
        lines.append(f"| {cat} | {stats.get(cat, 0)} |")
    lines.append("")

    for cat in CATEGORY_ORDER:
        items = grouped.get(cat) or []
        lines.append(f"## {cat} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("_Video yok._")
            lines.append("")
            continue
        for v in items:
            title = v.get("title") or "(başlıksız)"
            lines.append(
                f"- **#{v['message_id']}** · {v.get('date', '—')} · "
                f"{v.get('duration_display', '—')} · {title}"
            )
            desc = (v.get("description") or "").strip()
            if desc and desc != title:
                preview = desc.replace("\n", " ")[:200]
                if len(desc) > 200:
                    preview += "…"
                lines.append(f"  - {preview}")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not os.path.isfile(OUT_JSON):
        print(f"JSON bulunamadı: {OUT_JSON}")
        return 1

    with open(OUT_JSON, encoding="utf-8") as f:
        payload = json.load(f)

    videos = payload.get("videos") or []
    for v in videos:
        v["category"] = categorize_video(v.get("title") or "", v.get("description") or "")

    stats = category_stats(videos)
    payload["videos"] = videos
    payload["total"] = len(videos)
    payload["generated_at"] = datetime.now(TR_TZ).isoformat()
    payload["by_category"] = stats

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    write_markdown(videos, OUT_MD, stats)

    print(f"Toplam: {len(videos)} video\n")
    print("Grup istatistikleri:")
    for cat in CATEGORY_ORDER:
        print(f"  {cat}: {stats.get(cat, 0)}")
    print(f"\nJSON: {OUT_JSON}")
    print(f"MD:   {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
