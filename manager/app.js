const $ = id => document.getElementById(id);
const localEditor = location.hostname === '127.0.0.1';
if (!localEditor) document.querySelector('.workspace').textContent = '읽기 전용 미리보기';
const statuses = {before: '업로드 전', uploading: '업로드 중', done: '비공개 업로드 완료'};
let films = [], filter = 'all', selected = null, dirty = false;
let production = null, progressBusy = false;
let storyOptions = [];
const PROGRESS_INTERVAL = 5 * 60 * 1000;
let progressTimer, lastProgressAttempt = 0;
const stages = [['script','소재·대본'],['assets','음성·원화'],['motion','모션'],['edit','편집'],['qa','최종 검수']];
const time = value => `${Math.floor(value / 60)}:${String(Math.round(value % 60)).padStart(2, '0')}`;
const vis = item => item.visibility === 'public' ? '공개' : item.visibility === 'private' ? '비공개' : item.visibility === 'unlisted' ? '일부 공개' : item.youtubeId ? '확인 필요' : '—';
const node = (tag, cls, text) => {const el = document.createElement(tag); if(cls) el.className = cls; if(text !== undefined) el.textContent = text; return el;};

function render() {
  $('total').textContent = films.length;
  $('all-count').textContent = films.length;
  $('before-count').textContent = films.filter(x => x.uploadStatus === 'before').length;
  $('done-count').textContent = films.filter(x => x.uploadStatus === 'done').length;
  const query = $('search').value.trim().toLocaleLowerCase();
  const visible = films.filter(x => (filter === 'all' || x.uploadStatus === filter) && x.title.toLocaleLowerCase().includes(query));
  $('films').replaceChildren();
  if (!visible.length) {
    $('films').append(node('p', 'empty', query ? '검색한 제목의 영상이 없습니다.' : '이 상태의 영상이 아직 없습니다.'));
    return;
  }
  visible.forEach(item => {
    const row = node('article', 'film');
    const content = node('div', 'film-main');
    const imageButton = node('button', 'poster-button');
    imageButton.type = 'button'; imageButton.setAttribute('aria-label', `${item.title} 영상 보기`);
    const image = node('img'); image.src = `/media/${item.id}/poster`; image.alt = ''; image.loading = 'lazy';
    imageButton.append(image); imageButton.onclick = () => openDetail(item);
    const text = node('div', 'film-text');
    const title = node('button', 'title-button', item.title); title.type = 'button'; title.onclick = () => openDetail(item);
    text.append(node('span', 'episode', `EP. ${item.id.slice(-3)}`), title, node('p', 'film-meta', `${time(item.seconds)} · 1080 × 1920 · 60fps · ${item.version}`), node('p', 'book', `책에서 시작한 이야기 · ${item.book}`));
    content.append(imageButton, text);
    const status = node('div', 'upload-cell'); status.append(node('span', `status ${item.uploadStatus}`, item.available ? statuses[item.uploadStatus] || '확인 필요' : '파일 확인 필요'));
    const visibility = node('div', 'visibility', vis(item));
    visibility.title = item.checkedAt ? `마지막 확인: ${item.checkedAt}` : '업로드 후 별도로 확인합니다.';
    const action = node('button', 'row-action', '영상 확인 →'); action.type = 'button'; action.onclick = () => openDetail(item);
    row.append(content, status, visibility, action); $('films').append(row);
  });
}

function announce(text, error = false) {
  $('message').textContent = text;
  $('message').classList.toggle('error', error);
  $('message').hidden = false;
}

function counters() {
  $('title-count').textContent = `${$('title').value.length} / 100`;
  $('description-count').textContent = `${$('description').value.length} / 5,000`;
}

function openDetail(item) {
  selected = item; dirty = false;
  $('episode-label').textContent = `EP. ${item.id.slice(-3)} · 완성본`;
  $('detail-title').textContent = '영상 확인 & 업로드 준비';
  $('title').value = item.title; $('description').value = item.description;
  $('save-state').textContent = localEditor ? '저장됨' : '읽기 전용'; $('message').hidden = true; $('request-fallback').hidden = true;
  $('title').readOnly = !localEditor; $('description').readOnly = !localEditor; $('save').disabled = !localEditor;
  $('player').src = `/media/${item.id}/video`; $('player').poster = `/media/${item.id}/poster`;
  $('file-version').textContent = `${item.version} · ${time(item.seconds)} · 60fps`;
  $('file-name').textContent = item.file;
  $('download').href = `/media/${item.id}/download`;
  $('upload-status').textContent = statuses[item.uploadStatus] || '확인 필요';
  $('visibility').textContent = item.youtubeId ? vis(item) : '업로드 후 확인';
  $('checked').textContent = item.checkedAt ? `마지막 확인 ${item.checkedAt}` : '';
  $('upload-request').disabled = !!item.youtubeId || item.uploadStatus !== 'before' || !item.available;
  $('upload-request').textContent = item.uploadStatus === 'done' ? '비공개 업로드 완료' : item.uploadStatus === 'uploading' ? '업로드 중' : '비공개 업로드 요청 복사 ↗';
  $('check-request').disabled = !item.youtubeId;
  $('action-hint').textContent = item.available ? '복사한 요청을 Codex에 보내면 현재 Chrome에서 진행합니다.' : '완성 영상 파일을 찾을 수 없습니다. 파일 위치를 먼저 확인해주세요.';
  if (!localEditor) $('action-hint').textContent += ' 제목·설명 편집은 PC의 로컬 관리페이지에서 가능합니다.';
  counters(); $('detail').showModal();
}

function closeDetail() {
  if (dirty && !confirm('저장하지 않은 변경사항을 닫을까요?')) return;
  $('player').pause(); $('player').removeAttribute('src'); $('player').load();
  $('detail').close(); selected = null;
}

async function save() {
  if (!$('editor').reportValidity()) return false;
  const button = $('save'); button.disabled = true;
  try {
    const response = await fetch('/library', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id:selected.id, title:$('title').value, description:$('description').value})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '저장하지 못했습니다.');
    selected.title = $('title').value.trim(); selected.description = $('description').value.trim();
    $('title').value = selected.title; $('description').value = selected.description;
    dirty = false; $('save-state').textContent = '저장됨'; counters(); render();
    announce('제목과 설명을 저장했습니다.'); return true;
  } catch (error) { announce(error.message, true); return false; }
  finally { button.disabled = false; }
}

async function copyRequest(kind) {
  // The page does not claim to run Playwright. Codex executes the copied request.
  if (dirty && !(await save())) return;
  const item = selected;
  const prompt = kind === 'upload'
    ? `지혜이야기 ${item.id}의 현재 최종본(${item.file}, 버전 ${item.version})을 manager/library.json에 저장한 제목·설명으로 현재 로그인된 Chrome의 Playwright에서 YouTube에 비공개 업로드해줘. 먼저 대상 채널을 확인하고, 실제 비공개 저장 완료와 영상 ID를 확인한 뒤 library.json의 업로드 상태·업로드 버전·파일 SHA256·YouTube 영상 ID를 기록해줘. 공개 전환·예약은 하지 마. 중복 업로드 여부를 먼저 확인해줘.`
    : `지혜이야기 ${item.id}, YouTube 영상 ID ${item.youtubeId}의 현재 공개 여부만 현재 로그인된 Chrome의 Playwright로 확인하고 manager/library.json의 visibility와 checkedAt을 갱신해줘. 공개 설정은 변경하지 마. 확인 실패 시 기존 값을 보존해줘.`;
  try {
    await navigator.clipboard.writeText(prompt);
    $('request-fallback').hidden = true;
    announce('요청을 복사했습니다. Codex 채팅에 붙여넣어 보내주세요. 아직 실행되지는 않았습니다.');
  } catch {
    $('request-text').value = prompt; $('request-fallback').hidden = false;
    $('request-text').focus(); $('request-text').select();
    announce('아래 요청을 직접 복사해 Codex에 보내주세요.');
  }
}

$('search').addEventListener('input', render);
document.querySelectorAll('[data-filter]').forEach(button => button.onclick = () => {
  filter = button.dataset.filter;
  document.querySelectorAll('[data-filter]').forEach(el => {el.classList.toggle('active', el === button); el.setAttribute('aria-pressed', String(el === button));});
  render();
});
['title','description'].forEach(id => $(id).addEventListener('input', () => {dirty = true; $('save-state').textContent = '저장 전'; $('message').hidden = true; counters();}));
$('editor').onsubmit = event => {event.preventDefault(); save();};
$('close-detail').onclick = closeDetail;
$('detail').addEventListener('cancel', event => {event.preventDefault(); closeDetail();});
$('detail').addEventListener('click', event => {if (event.target === $('detail')) {const r = $('detail').getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) closeDetail();}});
$('upload-request').onclick = () => copyRequest('upload');
$('check-request').onclick = () => copyRequest('check');
window.addEventListener('beforeunload', event => {if(dirty){event.preventDefault(); event.returnValue = '';}});
async function load() {
  try {
    const response = await fetch('/library'); if (!response.ok) throw new Error();
    films = await response.json(); render();
  } catch {
    $('films').replaceChildren(node('p', 'empty', '완성본을 불러오지 못했습니다. 서버 실행을 확인한 뒤 새로고침해주세요.'));
  }
}
load();

function renderProgress(value) {
  const labels = {idle:'대기',running:'제작 중',paused:'보류',failed:'오류로 중단',complete:'완료'};
  if (!(value.status in labels) || (value.status !== 'idle' && !stages.some(([id]) => id === value.stage))) throw new Error('상태 형식 확인 필요');
  const changed = JSON.stringify(production) !== JSON.stringify(value);
  const previous = production;
  production = value;
  if (!changed) return;
  $('production-card').dataset.status = value.status;
  $('production-badge').textContent = labels[value.status];
  $('production-title').textContent = value.status === 'idle' ? '지금은 제작 중인 영상이 없습니다.' : `${value.episodeId} · ${value.title}`;
  $('production-message').textContent = value.status === 'idle' ? '새 영상 제작 버튼에서 다음 이야기를 요청해보세요.' : value.message;
  $('production-updated').textContent = value.updatedAt ? `마지막 작업 업데이트 · ${new Date(value.updatedAt).toLocaleString('ko-KR',{timeZone:'Asia/Seoul',hour12:false})}` : '';
  const active = stages.findIndex(([id]) => id === value.stage);
  $('production-steps').hidden = value.status === 'idle';
  $('production-steps').replaceChildren();
  stages.forEach(([id,label], index) => {
    const finished = value.status === 'complete' || index < active;
    const current = value.status !== 'complete' && index === active;
    const step = node('li',finished ? 'finished' : current ? 'current' : '');
    step.append(node('span','',finished ? '✓' : String(index + 1)),document.createTextNode(label));
    if (current) step.setAttribute('aria-current','step');
    $('production-steps').append(step);
  });
  const busy = !['idle','complete'].includes(value.status);
  $('new-production').disabled = busy;
  $('new-production').title = busy ? '진행·보류 중인 한 편을 먼저 마무리해주세요.' : '';
  updateCreateChoice();
  $('production-result').hidden = value.status !== 'complete';
  if (value.status === 'complete' && (previous?.status !== 'complete' || previous?.resultEpisodeId !== value.resultEpisodeId)) load();
}

async function refreshProgress(manual = false) {
  if (progressBusy) return;
  progressBusy = true;
  clearTimeout(progressTimer);
  lastProgressAttempt = Date.now();
  const button = $('refresh-progress');
  button.disabled = true;
  button.classList.add('is-loading');
  button.setAttribute('aria-busy','true');
  $('progress-controls').dataset.state = 'loading';
  $('progress-sync').textContent = '확인 중…';
  try {
    const response = await fetch('/production',{cache:'no-store',signal:AbortSignal.timeout(5000)});
    if (!response.ok) throw new Error();
    const value = await response.json();
    const unchanged = JSON.stringify(production) === JSON.stringify(value);
    renderProgress(value);
    const checked = new Date().toLocaleTimeString('en-GB',{timeZone:'Asia/Seoul',hour12:false});
    $('progress-sync').textContent = `${manual && unchanged ? '변경 없음 · ' : ''}${checked} 확인`;
    $('progress-controls').dataset.state = 'success';
  } catch {
    $('progress-sync').textContent = production ? '확인 실패 · 이전 상태 유지' : '연결 실패 · 다시 확인해주세요';
    $('progress-controls').dataset.state = 'error';
    if (!production) {
      $('production-badge').textContent = '확인 필요';
      $('production-title').textContent = '제작 상태를 불러오지 못했습니다.';
      $('new-production').disabled = true;
      $('copy-production').disabled = true;
    }
  } finally {
    progressBusy = false;
    button.disabled = false;
    button.classList.remove('is-loading');
    button.setAttribute('aria-busy','false');
    progressTimer = setTimeout(() => {if (!document.hidden) refreshProgress();},PROGRESS_INTERVAL);
  }
}

$('new-production').onclick = () => {
  $('copy-next-step').hidden = true;
  $('create-message').hidden = true;
  $('create-fallback').hidden = true;
  $('create-dialog').showModal();
  loadStoryOptions();
};
$('close-create').onclick = () => $('create-dialog').close();

function updateCreateChoice() {
  const choice = document.querySelector('input[name="story-choice"]:checked')?.value;
  const custom = choice === 'custom';
  const option = storyOptions.find(item => item.id === choice);
  const ready = custom ? !!$('production-brief').value.trim() : !!option;
  const busy = !production || !['idle','complete'].includes(production.status);
  $('copy-production').disabled = busy || !ready;
  $('create-selection').textContent = custom
    ? ready ? '선택: 직접 요청한 이야기' : '원하는 주제나 이야기 방향을 적어주세요.'
    : option ? `선택: ${option.topic}` : '추천 하나를 고르거나 마지막 칸에 직접 적어주세요.';
}

async function loadStoryOptions() {
  storyOptions = [];
  $('story-recommendations').replaceChildren(node('p','action-hint','추천을 불러오는 중입니다.'));
  updateCreateChoice();
  try {
    const response = await fetch('/story-options',{cache:'no-store',signal:AbortSignal.timeout(5000)});
    if (!response.ok) throw new Error();
    const options = (await response.json()).options;
    if (!Array.isArray(options) || options.length !== 3 || new Set(options.map(x => x.id)).size !== 3 ||
        new Set(options.map(x => x.topic)).size !== 3 ||
        options.some(x => ['id','topic','title','message','form','synopsis'].some(key => typeof x[key] !== 'string' || !x[key].trim()))) throw new Error();
    storyOptions = options;
    $('story-recommendations').replaceChildren();
    options.forEach((option,index) => {
      const label = node('label','story-choice');
      const radio = node('input'); radio.type='radio'; radio.name='story-choice'; radio.value=option.id;
      const content = node('span','story-choice-content');
      const top = node('span','story-choice-top');
      top.append(node('span','story-number',`추천 ${index+1}`),node('span','story-form',option.form));
      content.append(top,node('span','story-message-label','주제'),node('strong','story-topic',option.topic),
        node('span','story-message-label','전하려는 생각'),node('span','story-key-message',option.message),
        node('span','story-working-title',`이야기 · ${option.title}`),node('span','story-choice-description',option.synopsis));
      label.append(radio,content); $('story-recommendations').append(label);
    });
  } catch {
    $('story-recommendations').replaceChildren(node('p','action-hint','추천을 불러오지 못했습니다. 창을 다시 열거나 마지막 칸에 직접 적어주세요.'));
  }
  updateCreateChoice();
}

$('story-choices').addEventListener('change',() => {
  $('copy-next-step').hidden = true;
  $('create-message').hidden = true; $('create-fallback').hidden = true; updateCreateChoice();
});
['focus','input'].forEach(event => $('production-brief').addEventListener(event,() => {
  $('copy-next-step').hidden = true;
  document.querySelector('input[name="story-choice"][value="custom"]').checked = true;
  $('create-message').hidden = true; $('create-fallback').hidden = true; updateCreateChoice();
}));
$('copy-production').onclick = async () => {
  const choice = document.querySelector('input[name="story-choice"]:checked')?.value;
  const option = storyOptions.find(item => item.id === choice);
  const custom = $('production-brief').value.trim();
  if (choice === 'custom' ? !custom : !option) return;
  const brief = choice === 'custom' ? `직접 요청한 주제·방향: ${custom}`
    : `선택한 추천안: ${option.title}\n주제: ${option.topic}\n전하려는 생각: ${option.message}\n형식: ${option.form}\n짧은 줄거리: ${option.synopsis}\n이 방향에 맞는 책의 중심 생각을 골라, 인물과 사건을 설득력 있게 발전시켜줘.`;
  const prompt = `지혜이야기 새 영상 한 편 제작해줘.\n${brief}\n현재 AGENTS.md·handoff.md·스토리_창작_규칙.md를 확인하고 한 편씩 최종 QA까지 진행해줘. 실제 제작을 시작할 때 manager/progress.py start로 영상 ID와 작업 제목을 기록하고, script(소재·대본) → assets(음성·원화) → motion(모션) → edit(편집) → qa(최종 검수)의 실제 단계가 바뀌거나 보류될 때 update로 현재 작업과 상태를 갱신해줘. 파일 생성이나 시간 경과만으로 완료 처리하지 마. 최종 QA 후 완성본을 manager/library.json에 등록하고 finish로 마무리해줘. 실제 업로드·공개·예약·다음 편은 시작하지 마.`;
  $('copy-production').disabled = true;
  $('copy-next-step').hidden = true;
  $('create-message').textContent = '요청을 복사하는 중입니다…';
  $('create-message').hidden = false;
  try {
    await navigator.clipboard.writeText(prompt);
    $('create-fallback').hidden = true;
    $('create-message').hidden = true;
    $('copy-next-step').hidden = false;
    $('copy-next-step').focus({preventScroll:true});
  } catch {
    $('create-request-text').value = prompt;
    $('create-fallback').hidden = false;
    $('create-request-text').focus(); $('create-request-text').select();
    $('create-message').textContent = '아래 요청을 직접 복사해 Codex 채팅에 보내주세요.';
  } finally {
    updateCreateChoice();
  }
};
$('production-result').onclick = () => {
  const item = films.find(x => x.id === production?.resultEpisodeId);
  if (item) openDetail(item);
};
refreshProgress();
$('refresh-progress').onclick = () => refreshProgress(true);
document.addEventListener('visibilitychange',() => {
  if (!document.hidden && Date.now() - lastProgressAttempt >= PROGRESS_INTERVAL) refreshProgress();
});
