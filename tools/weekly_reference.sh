#!/bin/zsh
# 매주 레퍼런스 채널을 다시 훑고, Claude가 분석해 스토리_창작_규칙.md를 갱신한다.
# 자동 예약 없음. 사용자가 "주간 레퍼런스 갱신해"라고 요청하면 실행한다(세션 안에서는 수집 스크립트 실행 후 직접 분석해도 된다).
set -euo pipefail
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
ROOT="${0:A:h:h}"
cd "$ROOT"
TODAY=$(date +%F)
LOG="근거/레퍼런스/logs"; mkdir -p "$LOG"
exec >>"$LOG/$TODAY.log" 2>&1
echo "== $(date) weekly reference refresh"

yt-dlp -U >/dev/null 2>&1 || true
python3 tools/reference_refresh.py "$TODAY"

claude -p --allowedTools "Read,Edit,Write,Glob,Grep,Bash(git add:*),Bash(git commit:*),Bash(git status:*),Bash(git diff:*)" <<EOF
부자의 심리학 쇼츠 채널의 주간 레퍼런스 갱신 작업이다. 저장소: $ROOT

1. AGENTS.md, 스토리_창작_규칙.md, 근거/채널3종_20261102/분석.md, 그리고 이번 주 데이터 근거/레퍼런스/주간/$TODAY-data.md 를 읽는다. 이전 주간 보고서(근거/레퍼런스/주간/*.md 중 -data가 아닌 것)가 있으면 최근 것도 읽는다.
2. 새로 올라온 영상과 지난주 대비 조회가 크게 오른(터진) 영상을 중심으로 주제·제목 문형·전개(훅·사건·전환·인용·마무리)·길이·문체를 분석한다. 테토남형·호구형에 쓸 만한 새 유행어·속어 제목이 있으면 따로 뽑는다.
3. 근거/레퍼런스/주간/$TODAY.md 에 보고서를 쓴다: 이번 주 터진 영상 목록(조회 증가·제목·한 줄 요약), 새로 보이는 패턴, 현재 규칙과 다른 점, 규칙에 반영한 것과 보류한 것(이유 포함). 한국어로 짧고 명확하게 쓴다.
4. 근거가 충분한 변화만 스토리_창작_규칙.md에 반영하고, 문서 끝 "변경 이력"에 "- $TODAY: 변경 내용 (근거: 영상ID)" 형식으로 남긴다. 다음은 사용자 확정 사항이므로 절대 바꾸지 않는다: 하루 5편 배분(기본 3·호구형 1·테토남형 1), 인용 출처·제목과 본문 일치를 따지지 않는 원칙, vidIQ 금지. 변화가 약하면 규칙은 그대로 두고 보고서에만 적는다.
5. handoff.md 맨 위 "현재 요약" 목록에 "- **주간 레퍼런스 갱신 $TODAY:** ..." 한 줄을 추가하거나, 같은 제목의 이전 줄이 있으면 교체한다.
6. git add 로 바뀐 문서와 근거/레퍼런스/snapshots, 근거/레퍼런스/주간 을 올리고 "Weekly reference refresh $TODAY" 메시지로 커밋한다. push는 하지 않는다.

vidIQ와 웹 검색·웹 접근은 사용하지 않는다. 위 파일들만 사용한다.
EOF
echo "== $(date) done"
