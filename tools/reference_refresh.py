"""레퍼런스 채널 쇼츠의 주간 스냅숏을 만들고, 지난 스냅숏과 비교한 데이터 보고서를 쓴다.

사용: python3 tools/reference_refresh.py [YYYY-MM-DD]
결과:
  근거/레퍼런스/snapshots/<날짜>.tsv   채널키·영상ID·조회수·제목
  근거/레퍼런스/subs/<ID>.ko.json3     새 영상·급상승 영상의 자동자막 (Git 제외)
  근거/레퍼런스/주간/<날짜>-data.md   새 영상·급상승·상위 목록과 자막 (분석 입력)
vidIQ는 사용하지 않는다. 공개 정보만 yt-dlp로 읽는다.
"""
import datetime
import json
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / '근거' / '레퍼런스'
SNAP = REF / 'snapshots'
SUBS = REF / 'subs'
WEEK = REF / '주간'


def fetch_list(handle):
    url = 'https://www.youtube.com/' + urllib.parse.quote(handle) + '/shorts'
    out = subprocess.run(['yt-dlp', '--flat-playlist', '-J', url],
                         capture_output=True, text=True, check=True).stdout
    rows = []
    for e in json.loads(out).get('entries') or []:
        title = re.sub(r'#\S+', '', e.get('title') or '')
        title = re.sub(r'\s+', ' ', title).strip()
        rows.append((e['id'], int(e.get('view_count') or 0), title))
    return rows


def load_snapshot(path):
    data = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        key, vid, views, title = line.split('\t', 3)
        data[(key, vid)] = (int(views), title)
    return data


def fetch_subs(ids):
    todo = [i for i in ids if not (SUBS / f'{i}.ko.json3').exists()]
    for k in range(0, len(todo), 8):
        subprocess.run(['yt-dlp', '-q', '--no-warnings', '--skip-download', '--write-auto-subs',
                        '--sub-langs', 'ko', '--sub-format', 'json3', '--ignore-errors',
                        '-o', str(SUBS / '%(id)s.%(ext)s'),
                        *[f'https://www.youtube.com/shorts/{i}' for i in todo[k:k + 8]]])


def transcript(vid):
    f = SUBS / f'{vid}.ko.json3'
    if not f.exists():
        return '(자막 없음)'
    j = json.loads(f.read_text(encoding='utf-8'))
    txt = ''.join(s.get('utf8', '') for e in j.get('events', []) for s in e.get('segs') or [])
    return re.sub(r'\s+', ' ', txt.replace('[음악]', '')).strip() or '(자막 없음)'


def fmt(n):
    return f'{n / 10000:.1f}만' if n >= 10000 else f'{n:,}'


def main():
    today = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
    for d in (SNAP, SUBS, WEEK):
        d.mkdir(parents=True, exist_ok=True)
    channels = json.loads((REF / 'channels.json').read_text(encoding='utf-8'))
    previous = sorted(p for p in SNAP.glob('*.tsv') if p.stem < today)
    prev = load_snapshot(previous[-1]) if previous else {}
    prev_date = previous[-1].stem if previous else None

    current, lines = {}, []
    for ch in channels:
        for vid, views, title in fetch_list(ch['handle']):
            current[(ch['key'], vid)] = (views, title)
            lines.append(f"{ch['key']}\t{vid}\t{views}\t{title}")
    (SNAP / f'{today}.tsv').write_text('\n'.join(lines) + '\n', encoding='utf-8')

    report = [f'# 레퍼런스 주간 데이터 {today}', '',
              f'비교 기준 스냅숏: {prev_date or "없음(첫 수집)"}. 조회수는 목록 표시값(반올림)이며 게시일은 없다.', '']
    need_subs = []
    sections = []
    for ch in channels:
        rows = [(vid, v, t) for (k, vid), (v, t) in current.items() if k == ch['key']]
        new = [r for r in rows if (ch['key'], r[0]) not in prev] if prev else []
        gains = []
        for vid, v, t in rows:
            if (ch['key'], vid) in prev:
                before = prev[(ch['key'], vid)][0]
                if v - before > 0:
                    gains.append((v - before, before, vid, v, t))
        gains.sort(reverse=True)
        top = sorted(rows, key=lambda r: -r[1])[:15]
        need_subs += [r[0] for r in new] + [g[2] for g in gains[:10]]
        sections.append((ch, rows, new, gains, top))
    fetch_subs(need_subs)

    for ch, rows, new, gains, top in sections:
        report += [f"## {ch['name']} ({ch['handle']}) — 쇼츠 {len(rows)}편", '']
        report += [f'### 새로 올라온 영상 {len(new)}편', '']
        for vid, v, t in sorted(new, key=lambda r: -r[1]):
            report += [f'- [{fmt(v)}] {t} ({vid})', f'  - 자막: {transcript(vid)}']
        report += ['', '### 지난주 대비 조회 증가 상위 10', '']
        for delta, before, vid, v, t in gains[:10]:
            report += [f'- +{fmt(delta)} ({fmt(before)} → {fmt(v)}) {t} ({vid})', f'  - 자막: {transcript(vid)}']
        report += ['', '### 누적 조회 상위 15', '']
        report += [f'- [{fmt(v)}] {t} ({vid})' for vid, v, t in top]
        report.append('')
    out = WEEK / f'{today}-data.md'
    out.write_text('\n'.join(report), encoding='utf-8')
    print(out)


if __name__ == '__main__':
    main()
