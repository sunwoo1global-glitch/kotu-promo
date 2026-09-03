#!/usr/bin/env python3
"""
KOTU 홍보 자동화 - 통계 수집기
GitHub Releases API에서 다운로드 수를 자동 수집하고, 홍보물 조회수 데이터와
합쳐 주간 리포트(마크다운 + CSV)를 자동 생성합니다.

사용법:
  python3 collect_stats.py --repo zpstudios/kotu --out ./report
  (홍보물 조회수는 --promo promo_stats.csv 로 주입 가능)

정기 실행(예: 매주 월요일 09:00)은 아래 cron 예시처럼 스케줄링합니다.
  0 9 * * 1  cd /path/to/kotu-promo && python3 collect_stats.py --repo zpstudios/kotu --out ./report
"""
import argparse
import csv
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

GITHUB_API = "https://api.github.com/repos/{repo}/releases?per_page=100"
UA = {"User-Agent": "kotu-promo-automation", "Accept": "application/vnd.github+json"}

# 다운로드 수에 집계할 실제 배포 파일 (홍보 대상)
# - Setup.exe  : 설치판 (홍보의 주 타깃)
# - Portable   : 무설치판
# - nupkg      : 자동업데체계 내부용 (집계 제외)
TRACKED_ASSETS = ("KOTU-win-Setup.exe", "KOTU-win-Portable.zip")


def fetch_json(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def collect_repo_stats(repo):
    """저장소 메타 + 릴리스별 다운로드 수 집계"""
    releases = fetch_json(GITHUB_API.format(repo=repo))
    total = {"setup": 0, "portable": 0, "all_assets": 0}
    per_release = []
    for rel in releases:
        setup = portable = 0
        for a in rel.get("assets", []):
            name = a["name"]
            dc = a["download_count"]
            total["all_assets"] += dc
            if name.endswith("KOTU-win-Setup.exe"):
                setup = dc
                total["setup"] += dc
            elif name.endswith("KOTU-win-Portable.zip"):
                portable = dc
                total["portable"] += dc
        per_release.append({
            "tag": rel["tag_name"],
            "published": rel["published_at"],
            "setup": setup,
            "portable": portable,
        })
    return {"total": total, "per_release": per_release, "release_count": len(releases)}


def load_promo(csv_path):
    """홍보물별 조회수 CSV (columns: channel,title,url,views,date)"""
    rows = []
    if csv_path and os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                rows.append(r)
    return rows


def render_markdown(repo, stats, promo_rows, out_dir):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    t = stats["total"]
    lines = []
    lines.append(f"# KOTU 홍보 성과 리포트 (자동 생성)")
    lines.append("")
    lines.append(f"> 생성 시각: {now}  ·  대상 저장소: `{repo}`")
    lines.append("")
    lines.append("## 1. 다운로드 현황")
    lines.append("")
    lines.append("| 구분 | 다운로드 수 |")
    lines.append("|---|---:|")
    lines.append(f"| 설치판 (KOTU-win-Setup.exe) | {t['setup']} |")
    lines.append(f"| 무설치판 (KOTU-win-Portable.zip) | {t['portable']} |")
    lines.append(f"| 릴리스 전체 자산 합계 | {t['all_assets']} |")
    lines.append("")
    lines.append(f"총 릴리스 수: {stats['release_count']}개")
    lines.append("")
    lines.append("### 릴리스별 다운로드")
    lines.append("")
    lines.append("| 버전 | 배포일(UTC) | 설치판 | 무설치판 |")
    lines.append("|---|---|---:|---:|")
    for r in stats["per_release"][:10]:
        lines.append(f"| {r['tag']} | {r['published'][:10]} | {r['setup']} | {r['portable']} |")
    lines.append("")
    lines.append("## 2. 홍보물 조회 현황")
    lines.append("")
    if promo_rows:
        lines.append("| 채널 | 제목 | 조회수 |")
        lines.append("|---|---|---:|")
        for p in promo_rows:
            lines.append(f"| {p.get('channel','')} | {p.get('title','')} | {p.get('views','')} |")
        total_views = sum(int(p.get("views", 0) or 0) for p in promo_rows)
        lines.append(f"\n홍보물 조회 합계: **{total_views}**")
    else:
        lines.append("아직 홍보물 데이터가 없습니다. `promo_stats.csv`에 채널별 조회수를 넣어 주세요.")
    lines.append("")
    lines.append("## 3. 전환 지표")
    lines.append("")
    total_views = sum(int(p.get("views", 0) or 0) for p in promo_rows)
    if total_views > 0:
        conv = (t["setup"] + t["portable"]) / total_views * 100
        lines.append(f"- 홍보물 조회 → 다운로드 전환율: **{conv:.2f}%**")
    else:
        lines.append("- 홍보물 조회 데이터가 없어 전환율을 계산할 수 없습니다.")
    lines.append("")
    lines.append("---")
    lines.append("*이 리포트는 자동 생성된 결과물입니다. 수동 편집하지 마세요.*")
    return "\n".join(lines)


def render_csv(stats, out_path):
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["tag", "published_utc", "setup_downloads", "portable_downloads"])
        for r in stats["per_release"]:
            w.writerow([r["tag"], r["published"], r["setup"], r["portable"]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="zpstudios/kotu")
    ap.add_argument("--out", default="./report")
    ap.add_argument("--promo", default=None, help="홍보물 조회수 CSV 경로")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    stats = collect_repo_stats(args.repo)
    promo_rows = load_promo(args.promo)

    md = render_markdown(args.repo, stats, promo_rows, args.out)
    md_path = os.path.join(args.out, "weekly_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    csv_path = os.path.join(args.out, "downloads.csv")
    render_csv(stats, csv_path)

    # JSON 원본도 저장 (대시보드/추가 분석용)
    with open(os.path.join(args.out, "raw.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"OK  report={md_path}")
    print(f"OK  csv   ={csv_path}")
    print(f"OK  json  ={os.path.join(args.out, 'raw.json')}")
    print(f"설치판 다운로드={stats['total']['setup']} / 무설치판={stats['total']['portable']} / 릴리스={stats['release_count']}")


if __name__ == "__main__":
    main()
