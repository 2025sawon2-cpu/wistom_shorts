"""Record the one actual production's progress. Does not launch or monitor a worker."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
import json
import re

HERE = Path(__file__).resolve().parent
STATE = HERE / 'production.json'
LIBRARY = HERE / 'library.json'
STAGES = ('script', 'assets', 'motion', 'edit', 'qa')


def write(data):
    data['updatedAt'] = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')
    temp = STATE.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(STATE)
    return data


def start(episode, title, message):
    current = json.loads(STATE.read_text(encoding='utf-8'))
    if current['status'] not in ('idle', 'complete'):
        raise ValueError('진행·보류 중인 한 편을 먼저 확인하세요. 새 제작으로 덮어쓸 수 없습니다.')
    if not re.fullmatch(r'episode-\d{3,}', episode) or not title.strip() or not message.strip():
        raise ValueError('영상 ID, 작업 제목, 실제 진행 내용을 확인하세요.')
    library = json.loads(LIBRARY.read_text(encoding='utf-8'))
    if any(item['id'] == episode for item in library):
        raise ValueError('이미 완성본으로 등록된 영상입니다.')
    return write({'status': 'running', 'episodeId': episode, 'title': title.strip(),
                  'stage': 'script', 'message': message.strip(), 'resultEpisodeId': None})


def update(episode, stage, message, status='running'):
    current = json.loads(STATE.read_text(encoding='utf-8'))
    if current['episodeId'] != episode or current['status'] in ('idle', 'complete'):
        raise ValueError('현재 제작 중인 영상 ID를 확인하세요.')
    if stage not in STAGES or status not in ('running', 'paused', 'failed') or not message.strip():
        raise ValueError('실제 단계·상태·진행 내용을 입력하세요.')
    current.update(stage=stage, message=message.strip(), status=status)
    return write(current)


def finish(episode, message):
    current = json.loads(STATE.read_text(encoding='utf-8'))
    if current['episodeId'] != episode or current['status'] != 'running' or current['stage'] != 'qa':
        raise ValueError('현재 영상의 최종 검수까지 진행한 뒤 완료하세요.')
    library = json.loads(LIBRARY.read_text(encoding='utf-8'))
    item = next((x for x in library if x['id'] == episode), None)
    if not item:
        raise ValueError('검수한 최종본을 library.json에 먼저 등록하세요.')
    root = HERE.parent
    for key in ('file', 'poster'):
        path = (root / item[key]).resolve()
        if not path.is_relative_to(root) or not path.is_file() or not path.stat().st_size:
            raise ValueError('등록한 최종 영상·대표 이미지 파일을 확인하세요.')
    if not message.strip():
        raise ValueError('검수 완료 내용을 입력하세요.')
    current.update(status='complete', message=message.strip(), resultEpisodeId=episode)
    return write(current)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    begin = sub.add_parser('start')
    begin.add_argument('--episode', required=True)
    begin.add_argument('--title', required=True)
    begin.add_argument('--message', required=True)
    change = sub.add_parser('update')
    change.add_argument('--episode', required=True)
    change.add_argument('--stage', choices=STAGES, required=True)
    change.add_argument('--status', choices=('running', 'paused', 'failed'), default='running')
    change.add_argument('--message', required=True)
    end = sub.add_parser('finish')
    end.add_argument('--episode', required=True)
    end.add_argument('--message', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'start':
            result = start(args.episode, args.title, args.message)
        elif args.command == 'update':
            result = update(args.episode, args.stage, args.message, args.status)
        else:
            result = finish(args.episode, args.message)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, str(error) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
