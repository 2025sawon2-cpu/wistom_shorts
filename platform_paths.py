"""Windows(기존 제작 PC)와 macOS 양쪽에서 같은 제작 스크립트를 쓰기 위한 경로 조회."""
import os
import sys
from pathlib import Path

_FONT_DIRS = [
    Path('C:/Windows/Fonts'),
    Path.home() / 'AppData/Local/Microsoft/Windows/Fonts',
    Path.home() / 'Library/Fonts',
    Path('/Library/Fonts'),
    Path('/usr/share/fonts/truetype/noto'),
]


def font_path(family):
    """family: 'NotoSansKR' 또는 'NotoSerifKR'. 가변 글꼴 파일 경로를 돌려준다."""
    names = [f'{family}-VF.ttf', f'{family}[wght].ttf', f'{family}-Variable.ttf']
    for d in _FONT_DIRS:
        for n in names:
            p = d / n
            if p.is_file():
                return str(p)
    raise FileNotFoundError(f'{family} 가변 글꼴을 찾지 못했습니다. macOS: brew install --cask font-noto-sans-kr font-noto-serif-kr')


def whisper_dir():
    """faster-whisper 모델 폴더. WHISPER_MODEL_DIR 환경변수가 우선한다."""
    env = os.environ.get('WHISPER_MODEL_DIR')
    if env:
        return env
    if sys.platform == 'win32':
        return 'C:/Codex/인스타자동화_사원2/insta_auto/data/models/faster-whisper'
    return str(Path.home() / '.cache/wistom_shorts/faster-whisper')
