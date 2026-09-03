#!/usr/bin/env python3
"""
KOTU 콘텐츠 변형 엔진 (Content Variation Engine)
=================================================
목적: 4시간 주기 자동 배포에서 매번 "다른 문구"의 홍보 콘텐츠를 생성합니다.
      플랫폼의 중복·스팸 필터는 "동일 문구 반복"을 삭제/제재하므로,
      문구·구조·강조 기능·이모지·해시태그를 매 슬롯마다 다르게 바꿔
      반복 게시가 중복으로 걸리지 않게 합니다.

동작: 현재 4시간 슬롯(epoch // 14400)을 시드로 사용하므로
      - 같은 슬롯 안에서 재실행해도 같은 문구 (멱등)
      - 슬롯이 바뀌면 다른 문구 (매 4시간 자동 변형)

사용법:
  python3 content_variation.py --out ./promo_out
  python3 content_variation.py --out ./promo_out --slot 3   # 특정 슬롯 강제 (테스트)
"""
import argparse
import hashlib
import os
import random
from datetime import datetime, timezone

SLOT_SECONDS = 4 * 3600  # 4시간

# ── 문구 풀 (각 슬롯마다 여기서 하나씩 조합) ──────────────────────────
HEADLINES = [
    "윈도우 필수 유틸 7개를 하나로 — KOTU",
    "새 PC 셋업, 이제 KOTU 하나로 끝납니다",
    "사진·영상·음악·문서·압축·모니터를 한 번에",
    "코덱 팩 없이 받자마자 쓰는 윈도우 유틸",
    "설치판도 포터블도 무료 — KOTU 소개",
    "윈도우 새로 깔면 제일 먼저 까는 앱",
    "하나의 창에서 일곱 가지 유틸을 여는 법",
    "PC 필수 프로그램, 이제 7개를 1개로",
]

OPENINGS = [
    "윈도우를 새로 설치할 때마다 여러 유틸을 따로 설치하셨나요? KOTU는 이걸 하나로 합쳤습니다.",
    "사진 뷰어, 동영상 플레이어, 압축 프로그램… 매번 따로 설치하느라 시간 보내셨던 경험, 다들 있으실 겁니다.",
    "PC를 새로 맞출 때 필수 유틸을 하나씩 깔던 시간, KOTU라면 그대로 아낄 수 있습니다.",
    "파일 형식마다 다른 프로그램을 열어야 했던 번거로움, KOTU 하나로 정리됩니다.",
    "코덱 팩 찾아 헤매던 시절은 이제 끝. KOTU는 필요한 엔진을 전부 품고 있습니다.",
    "윈도우 기본 앱에 살짝 부족함을 느끼셨다면, KOTU가 좋은 대안이 될 수 있습니다.",
]

FEATURES = [
    ("이미지", "jpg·png·gif·webp·bmp·tif·ico·psd, 줌 10~800%, GIF 애니메이션"),
    ("비디오", "mp4·mkv·avi·webm·mov·wmv 등 13종, 자막 자동 변환, 이어보기"),
    ("오디오", "mp3·flac·wav·ogg·opus·m4a·aac·wma, 비주얼라이저 4종"),
    ("문서", "txt·md·html·log·ini 편집 + PDF 보기, 인코딩 변환"),
    ("압축", "zip·7z·rar·tar·gz·tgz·bz2·xz, 암호 지원, 내부 탐색"),
    ("H/W Info", "CPU·GPU·RAM·SSD 실시간 그래프, 사양 전체 복사"),
]

HIGHLIGHT_LINES = [
    "특히 {mod} 모듈이 인상적입니다 — {desc}.",
    "그중 {mod} 기능은 {desc}까지 지원합니다.",
    "{mod}도 빼놓을 수 없는데, {desc}.",
    "직접 써보니 {mod}가 가장 편했습니다 — {desc}.",
]

BENEFITS = [
    "코덱 팩·별도 설치 불필요 — 7-Zip, libvlc, 하드웨어 모니터 엔진 동봉",
    "설치판(자동 업데이트)과 포터블(무설치) 모두 제공",
    "사용자 범위 설치라 관리자 권한 불필요, 탐색기 통합도 자유롭게",
    "한글 우선 UI + 영문 가이드 병행",
    "MIT 오픈소스 — GitHub에서 소스 공개",
]

CLOSINGS = [
    "다운로드는 GitHub Releases에서 받으실 수 있습니다. 사용해 보시고 피드백 남겨주시면 감사하겠습니다.",
    "GitHub Releases 링크에서 설치판 또는 포터블을 받아 바로 써보실 수 있습니다.",
    "궁금한 점이나 버그는 GitHub 이슈로 알려주세요. 활발히 개발 중입니다.",
    "직접 받아보시는 게 가장 빠릅니다 — GitHub Releases에서 무료로 받을 수 있어요.",
]

CTA_LINES = [
    "👉 GitHub Releases: https://github.com/zpstudios/kotu/releases/latest",
    "⬇️ 다운로드: https://github.com/zpstudios/kotu/releases/latest",
    "🔗 받기: https://github.com/zpstudios/kotu/releases/latest",
    "📦 GitHub: https://github.com/zpstudios/kotu/releases/latest",
]

EMOJI_SETS = [
    ["🖼️", "🎬", "🎵", "📄", "🗜️", "🌡️"],
    ["✨", "🚀", "⚡", "🔧", "💾", "🖥️"],
    ["✅", "🔍", "🎧", "📑", "📦", "📊"],
]

HASHTAG_SETS = [
    ["#KOTU", "#윈도우유틸", "#무료프로그램", "#오픈소스", "#포터블"],
    ["#KOTU", "#윈도우앱", "#생산성", "#압축프로그램", "#동영상플레이어"],
    ["#KOTU", "#Windows", "#유틸리티", "#프리웨어", "#PC최적화"],
]


def pick(rng, pool):
    return rng.choice(pool)


def build_post(seed):
    rng = random.Random(seed)
    headline = pick(rng, HEADLINES)
    opening = pick(rng, OPENINGS)
    mod_name, mod_desc = rng.choice(FEATURES)
    highlight = pick(rng, HIGHLIGHT_LINES).format(mod=mod_name, desc=mod_desc)
    benefits = rng.sample(BENEFITS, k=3)
    closing = pick(rng, CLOSINGS)
    cta = pick(rng, CTA_LINES)
    emojis = pick(rng, EMOJI_SETS)
    hashtags = pick(rng, HASHTAG_SETS)

    lines = []
    lines.append(f"# {headline}")
    lines.append("")
    lines.append(f"{opening}")
    lines.append("")
    lines.append(f"## 이런 분께 추천")
    lines.append("")
    for b in benefits:
        lines.append(f"- {b}")
    lines.append("")
    lines.append(f"## {mod_name} 모듈")
    lines.append("")
    lines.append(f"{highlight}")
    lines.append("")
    lines.append(f"{closing}")
    lines.append("")
    lines.append(cta)
    lines.append("")
    lines.append(" ".join(emojis))
    lines.append(" ".join(hashtags))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="./promo_out")
    ap.add_argument("--slot", type=int, default=None, help="특정 슬롯 번호 강제 (기본: 현재 슬롯)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    now = datetime.now(timezone.utc)
    if args.slot is not None:
        slot = args.slot
    else:
        slot = int(now.timestamp()) // SLOT_SECONDS

    # 슬롯 기반 시드 (멱등)
    seed = hashlib.sha256(f"kotu-promo-slot-{slot}".encode()).hexdigest()
    seed_int = int(seed[:8], 16)

    post = build_post(seed_int)

    slot_start = datetime.fromtimestamp(slot * SLOT_SECONDS, tz=timezone.utc)
    slot_end = datetime.fromtimestamp((slot + 1) * SLOT_SECONDS, tz=timezone.utc)

    fname = f"post_slot_{slot}.md"
    path = os.path.join(args.out, fname)
    with open(path, "w", encoding="utf-8") as f:
        f.write(post)

    # 로그 (어느 슬롯에 어떤 파일이 생성됐는지)
    log_path = os.path.join(args.out, "generation_log.csv")
    with open(log_path, "a", encoding="utf-8") as f:
        if os.path.getsize(log_path) == 0:
            f.write("slot,slot_start_utc,slot_end_utc,file,seed\n")
        f.write(f"{slot},{slot_start.isoformat()},{slot_end.isoformat()},{fname},{seed_int}\n")

    print(f"OK  slot={slot}  ({slot_start.isoformat()} ~ {slot_end.isoformat()})")
    print(f"OK  file={path}")
    print("--- POST PREVIEW ---")
    print(post)


if __name__ == "__main__":
    main()
