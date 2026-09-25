'use strict';
const $ = id => document.getElementById(id);
const state = {papers: [], selected: new Set(), task: 'ask', provider: 'offline', apiKey: '', model: 'gpt-4o-mini', topK: 5, history: [], active: null, busy: false, source: null, view: 'desk', defaultProvider: 'offline', defaultModel: 'openai/gpt-oss-120b', hasDefaultKey: false};
const names = {P01: 'MobileNets', P02: 'EfficientNet', P03: 'Vision Transformer', P04: 'EfficientViT'};
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = t(text); return n; };
const shortName = p => names[p.id] || p.title;
const paperById = id => state.papers.find(p => p.id === id);
let toastTimer;
function toast(message) { $('toast').textContent = t(message); $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 4000); }
async function api(path, body) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 180000);
  let response;
  try {
    response = await fetch(path, body ? {method: 'POST', headers: {'Content-Type': 'application/json', 'X-ResearchPilot': 'workspace'}, body: JSON.stringify(body), signal: controller.signal} : {signal: controller.signal});
  } catch (error) {
    throw new Error(t(error.name === 'AbortError' ? 'Yêu cầu mất quá nhiều thời gian. Hãy thử lại sau.' : 'Không kết nối được ResearchPilot trên máy. Hãy khởi động lại server rồi thử lại; đây chưa phải lỗi API key.'));
  } finally { clearTimeout(timer); }
  let data;
  try { data = await response.json(); }
  catch (_) { throw new Error(t('Server trả về dữ liệu không hợp lệ. Hãy tải lại trang và thử lại.')); }
  if (!response.ok) throw new Error(t(data.error || 'Chưa hoàn thành yêu cầu. Vui lòng thử lại.'));
  return data;
}

function view(name) {
  state.view = name;
  for (const n of document.querySelectorAll('.page-view')) n.hidden = n.id !== name + '-view';
  for (const n of document.querySelectorAll('[data-view]')) { n.classList.toggle('active', n.dataset.view === name); n.setAttribute('aria-current', n.dataset.view === name ? 'page' : 'false'); }
  $('page-name').textContent = t({desk: 'Bàn nghiên cứu', library: 'Thư viện', history: 'Phiên làm việc'}[name]);
  if (name === 'history') renderHistory();
}
function selection() {
  $('selection-count').textContent = t(state.selected.size + ' tài liệu');
  document.querySelectorAll('.paper-card').forEach(card => { const selected = state.selected.has(card.dataset.paper); card.classList.toggle('selected', selected); card.querySelector('input').checked = selected; });
}
function setTask(task) {
  state.task = task;
  document.querySelectorAll('[data-task]').forEach(b => { b.classList.toggle('active', b.dataset.task === task); b.setAttribute('aria-selected', String(b.dataset.task === task)); });
  if (task === 'compare' && state.selected.size !== 2) toast('Chọn đúng hai tài liệu trên bàn để so sánh.');
}
function cover(p) { const img = el('img'); img.src = `/api/papers/${encodeURIComponent(p.id)}/preview?page=1&width=240`; img.alt = t('Trang bìa ') + shortName(p); img.loading = 'lazy'; return img; }
function renderPapers() {
  $('paper-grid').replaceChildren(...state.papers.map(p => {
    const card = el('article', 'paper-card selected'); card.dataset.paper = p.id;
    const thumb = cover(p); thumb.className = 'paper-cover';
    const info = el('div', 'paper-info'); info.append(el('span', 'paper-label', `${p.id} / ${p.year || 'PAPER'}`), el('h3', '', shortName(p)), el('p', '', `${p.pages} trang · ${p.evidence_count} đoạn trích`));
    const label = el('label', 'paper-choice'); const checkbox = el('input'); checkbox.type = 'checkbox'; checkbox.checked = true; checkbox.setAttribute('aria-label', t('Chọn ') + shortName(p)); checkbox.addEventListener('change', () => { checkbox.checked ? state.selected.add(p.id) : state.selected.delete(p.id); selection(); }); label.append(checkbox);
    const open = el('button', 'open-paper', '↗'); open.setAttribute('aria-label', t('Mở ') + shortName(p)); open.onclick = () => openSource(p.id, 1);
    card.append(thumb, info, label, open); return card;
  }));
  selection(); renderLibrary();
}
function renderLibrary() {
  const term = $('paper-search').value.toLocaleLowerCase();
  const papers = state.papers.filter(p => `${p.title} ${p.authors.join(' ')} ${p.year} ${shortName(p)}`.toLocaleLowerCase().includes(term));
  $('library-list').replaceChildren(...papers.map(p => {
    const row = el('article', 'library-row'); const body = el('div', 'row-body');
    body.append(el('span', 'paper-label', `${p.id} / ${p.year || ''}`), el('h3', '', p.title), el('p', '', p.authors.slice(0, 3).join(', ') + (p.authors.length > 3 ? ' và cộng sự' : '')), el('small', '', `${p.pages} trang · ${p.evidence_count} đoạn trích`));
    const button = el('button', 'text-button', 'Đọc paper ↗'); button.onclick = () => openSource(p.id, 1); row.append(cover(p), body, button); return row;
  }));
  if (!papers.length) $('library-list').append(el('p', 'intro', 'Không có tài liệu khớp với tìm kiếm.'));
}
function openSource(id, page) {
  const paper = paperById(id); if (!paper) return;
  state.source = {paper, page: Math.max(1, Math.min(paper.pages, Number(page) || 1))};
  $('source-title').textContent = t(shortName(paper)); $('source-label').textContent = t(paper.id + ' / TÀI LIỆU NGUỒN');
  renderSource(); if (!$('source-dialog').open) $('source-dialog').showModal();
}
function renderSource() {
  const {paper, page} = state.source;
  $('source-page').textContent = t(`${page} / ${paper.pages}`);
  $('source-image').src = `/api/papers/${encodeURIComponent(paper.id)}/preview?page=${page}&width=2000`;
  $('source-image').alt = `${shortName(paper)} — ${t('trang')} ${page}`;
  $('open-pdf').href = `/api/papers/${encodeURIComponent(paper.id)}/pdf#page=${page}`;
  $('previous-page').disabled = page === 1; $('next-page').disabled = page === paper.pages;
}
function renderAnswer(item) {
  state.active = item;
  const answer = item.result.answer;
  $('answer-section').hidden = false; $('export-answer').hidden = false;
  $('answer-status').textContent = t(answer.abstained ? 'CHƯA ĐỦ BẰNG CHỨNG' : answer.limitations?.length ? 'TRẢ LỜI MỘT PHẦN' : 'GHI CHÚ NGHIÊN CỨU');
  $('answer-question').textContent = item.question;
  $('answer-body').className = 'answer-text'; $('answer-body').replaceChildren();
  const text = answer.abstained ? 'Chưa có đủ bằng chứng để trả lời chắc chắn. Hãy thử câu hỏi cụ thể hơn hoặc chọn thêm tài liệu. Bạn vẫn có thể kiểm tra các đoạn tìm được ở sổ bằng chứng.' : answer.answer;
  if (answer.abstained) $('answer-body').append(document.createTextNode(t(text)));
  else appendCitedAnswer($('answer-body'), text, answer.citations);
  if (answer.limitations?.length) { const note = el('div', 'partial-answer'); note.append(el('strong', '', 'Phần chưa xác định từ nguồn:')); answer.limitations.forEach(item => note.append(el('p', '', item))); $('answer-body').append(note); }
  $('answer-meta').textContent = t(`${item.provider === 'offline' ? 'Trích đoạn offline' : providerName(item.provider) + ' · ' + item.model} · ${((answer.latency_ms || 0) / 1000).toFixed(1)} giây · ${answer.retrieved_evidence.length} bằng chứng`);
  const warnings = [...(answer.warnings || []), ...(item.result.unsupported || [])];
  $('answer-warnings').hidden = !warnings.length;
  $('answer-warnings').querySelector('ul').replaceChildren(...warnings.map(w => el('li', '', evidenceWarning(w))));
  const cited = new Set(answer.citations.map(c => c.evidence_id));
  const citationOrder = new Map(answer.citations.map((c,i) => [c.evidence_id,i]));
  const evidence = [...answer.retrieved_evidence].sort((a,b) => (citationOrder.get(a.evidence.evidence_id) ?? 1000) - (citationOrder.get(b.evidence.evidence_id) ?? 1000) || a.rank-b.rank);
  $('evidence-count').textContent = String(evidence.length).padStart(2, '0'); $('evidence-empty').hidden = !!evidence.length;
  document.querySelector('.evidence-rail').scrollTop = 0;
  const otherSources = el('details', 'source-details'); otherSources.append(el('summary', '', 'Đoạn truy xuất chưa dùng'));
  const cards = evidence.map(r => {
    const e = r.evidence, used = cited.has(e.evidence_id);
    const terms = (answer.evidence_terms || {})[e.evidence_id] || [];
    const quotes = (answer.support_quotes || {})[e.evidence_id] || [];
    const box = el('article', 'evidence-item' + (used ? ' is-cited' : '')); box.id = 'evidence-' + e.evidence_id;
    const header = el('div','evidence-card-header'); header.append(el('span','evidence-number',used ? String(citationOrder.get(e.evidence_id)+1).padStart(2,'0') : '—'), el('span','evidence-badge', used ? 'Đã dùng trong câu trả lời' : 'Đoạn truy xuất chưa dùng'));
    box.append(header,el('h4','',shortName(paperById(e.paper_id) || {id:e.paper_id,title:e.paper_id})),el('div','evidence-page',t('Trang')+' '+e.page));
    const excerpt = el('blockquote','source-quote');
    const preview = quotes.length ? quotes.join(' … ') : e.text.slice(0,360) + (e.text.length>360 ? '…' : '');
    excerpt.textContent = preview; box.append(excerpt);
    const why = el('div','evidence-why'); why.append(el('strong','', 'Vì sao liên quan?'));
    const supports = (answer.evidence_support || {})[e.evidence_id] || [];
    if (supports.length) supports.forEach(support => {
      why.append(el('strong', '', 'Hỗ trợ ý:'), el('p', '', support.claim));
      if (support.reason) why.append(el('span', '', 'Giải thích của model:'), el('p', '', support.reason));
    });
    else why.append(el('p', '', used ? 'Câu trả lời có trích dẫn đến nguồn này.' : 'Được tìm thấy khi truy xuất; chưa được dùng để khẳng định câu trả lời.'));
    box.append(why);
    const full = el('details','source-details'); full.append(el('summary','', 'Xem thêm ngữ cảnh')); const content=el('p'); appendHighlighted(content,e.text,terms); full.append(content); box.append(full);
    const b = el('button','source-open', 'Mở trang PDF ↗'); b.onclick=()=>openSource(e.paper_id,e.page); box.append(b);
    if (!used) { otherSources.append(box); return null; }
    return box;
  }).filter(Boolean);
  $('evidence-list').replaceChildren(...cards);
  if (answer.retrieval_method === 'lexical_fallback') $('evidence-list').prepend(el('p', 'evidence-why', 'Bước chọn theo ngữ nghĩa chưa thành công; đang dùng kết quả truy xuất dự phòng.')); 
  if (otherSources.children.length > 1) $('evidence-list').append(otherSources);
  $('evidence-count').textContent = String(cards.length).padStart(2, '0');
}
function evidenceWarning(message) {
  const copy = {
    'Model found insufficient evidence': 'Các nguồn tìm được chưa đủ để trả lời đầy đủ câu hỏi.',
    'Supporting quote does not occur in the cited page': 'Model chưa trích đúng nguyên văn từ nguồn. Câu trả lời được giữ lại để tránh dẫn chứng sai.',
    'Unknown citation alias': 'Model viện dẫn nguồn không có trong các đoạn tìm được.',
    'Both papers must support the comparison': 'Chưa có đủ bằng chứng từ cả hai paper để so sánh.',
    'No matching source pages': 'Chưa tìm thấy trang phù hợp với câu hỏi.',
    'Model returned invalid JSON': 'Phản hồi của model chưa đúng định dạng. Hãy thử lại.'
  };
  return copy[message] || message;
}
function appendHighlighted(parent, text, terms) {
  const safeTerms=terms.filter(x=>/^[a-z0-9]+$/i.test(x));
  if (!safeTerms.length) { parent.append(document.createTextNode(text)); return; }
  const regex=new RegExp('\\b(' + safeTerms.join('|') + ')\\b','gi');
  let offset=0;
  for (const match of text.matchAll(regex)) { parent.append(document.createTextNode(text.slice(offset,match.index)),el('mark','',match[0])); offset=match.index+match[0].length; }
  parent.append(document.createTextNode(text.slice(offset)));
}
function appendCitedAnswer(parent,text,citations) {
  const regex=/\[([^,\]]+),\s*p\.(\d+),\s*([^\]]+)\]/g; let offset=0;
  for (const match of text.matchAll(regex)) {
    const index=citations.findIndex(c=>c.paper_id===match[1].trim() && c.page===Number(match[2]) && c.evidence_id===match[3].trim());
    if (index<0) continue;
    parent.append(document.createTextNode(text.slice(offset,match.index)));
    const c=citations[index], b=el('button','citation-button',String(index+1));
    b.setAttribute('aria-label', t('Mở nguồn')+' '+c.paper_id+', '+t('trang')+' '+c.page);
    b.title=shortName(paperById(c.paper_id)||{id:c.paper_id,title:c.paper_id})+' · '+t('trang')+' '+c.page;
    b.onclick=()=>{ document.querySelectorAll('.evidence-item.active').forEach(n=>n.classList.remove('active')); const card=$('evidence-'+c.evidence_id); if(card)card.classList.add('active'); openSource(c.paper_id,c.page); };
    parent.append(b); offset=match.index+match[0].length;
  }
  parent.append(document.createTextNode(text.slice(offset)));
}

function renderHistory() {
  $('history-list').replaceChildren(...state.history.slice().reverse().map((item, i) => {
    const b = el('button', 'history-item'); b.append(el('span', 'paper-label', `${String(state.history.length - i).padStart(2, '0')} / ${providerName(item.provider).toUpperCase()}`), el('h3', '', item.question), el('p', '', item.result.answer.abstained ? 'Chưa đủ bằng chứng' : `${item.result.answer.citations.length} trích dẫn · Mở ghi chú ↗`));
    b.onclick = () => { view('desk'); renderAnswer(item); $('answer-section').scrollIntoView({behavior: 'smooth'}); }; return b;
  }));
  if (!state.history.length) $('history-list').append(el('p', 'intro', 'Chưa có câu hỏi nào. Bắt đầu tại bàn nghiên cứu.'));
}
$('question-form').addEventListener('submit', async event => {
  event.preventDefault(); if (state.busy) return;
  const question = $('question').value.trim(); $('query-error').hidden = true;
  const error = !question ? 'Hãy nhập câu hỏi.' : !state.selected.size ? 'Chọn ít nhất một tài liệu.' : state.task === 'compare' && state.selected.size !== 2 ? 'Chọn đúng hai tài liệu để so sánh.' : state.provider !== 'offline' && !state.apiKey && !state.hasDefaultKey ? 'Nhập API key trong Kết nối model trước khi hỏi.' : '';
  if (error) { $('query-error').textContent = t(error); $('query-error').hidden = false; return; }
  const provider = state.provider, model = state.model;
  state.busy = true; $('submit-question').disabled = true; $('submit-question').classList.add('busy'); $('submit-question').querySelector('span').textContent = t('Đang đọc…');
  try {
    const result = await api('/api/ask', {question, papers: [...state.selected], task: state.task, mode: $('retrieval-mode').value, provider, model, api_key: provider !== 'offline' ? state.apiKey : '', top_k: state.topK, language: language});
    const item = {question, result, provider: result.provider, model: result.model}; state.history.push(item); $('history-count').textContent = t(state.history.length); renderAnswer(item); $('answer-section').scrollIntoView({behavior: 'smooth', block: 'start'});
  } catch (e) { $('query-error').textContent = t(e.message); $('query-error').hidden = false; }
  finally { state.busy = false; $('submit-question').disabled = false; $('submit-question').classList.remove('busy'); $('submit-question').querySelector('span').textContent = t('Tìm câu trả lời'); }
});
function providerName(provider) { return {groq: 'Groq', openai: 'OpenAI', gemini: 'Gemini', offline: 'Offline'}[provider] || provider; }
function updateConnection() {
  $('connection-label').textContent = t(state.provider === 'offline' ? 'Kết nối model' : providerName(state.provider));
  $('provider-indicator').textContent = t(providerName(state.provider));
  $('privacy-note').textContent = t(state.provider === 'offline' ? 'Trích bằng chứng trên máy · Không cần API key' : `Câu hỏi và đoạn trích sẽ được gửi tới ${providerName(state.provider)}`);
}
function settingsFields(resetModel = false) {
  const provider = document.querySelector('input[name="provider"]:checked').value;
  $('api-fields').hidden = provider === 'offline';
  if (resetModel) { $('api-key').value = ''; $('model-name').value = provider === 'groq' ? state.defaultModel : provider === 'gemini' ? 'gemini-3.8-flash' : 'gpt-4o-mini'; $('connection-result').hidden = true; }
  $('default-key-note').textContent = t(state.hasDefaultKey ? 'Để trống key: dùng Groq mặc định trên máy. Key mới sẽ được ưu tiên.' : 'Chưa có key mặc định. Nhập key để kết nối.');
  $('get-api-key').href = provider === 'groq' ? 'https://console.groq.com/keys' : provider === 'gemini' ? 'https://aistudio.google.com/apikey' : 'https://platform.openai.com/api-keys';
}
function openSettings() {
  document.querySelector(`input[name="provider"][value="${state.provider}"]`).checked = true;
  $('api-key').value = state.apiKey; $('model-name').value = state.model; $('top-k').value = String(state.topK); settingsFields(); $('connection-result').hidden = true; $('settings-dialog').showModal();
}
$('settings-form').addEventListener('submit', e => {
  e.preventDefault(); let provider = document.querySelector('input[name="provider"]:checked').value;
  const key = $('api-key').value.trim();
  if (provider !== 'offline' && !key && !state.hasDefaultKey) { $('connection-result').textContent = t('Nhập API key và model trước khi áp dụng.'); $('connection-result').classList.add('error'); $('connection-result').hidden = false; return; }
  let model = $('model-name').value.trim() || (provider === 'groq' ? state.defaultModel : provider === 'gemini' ? 'gemini-3.8-flash' : 'gpt-4o-mini');
  if (provider !== 'offline' && !key && state.hasDefaultKey) { if (provider !== 'groq') model = state.defaultModel; provider = 'groq'; }
  state.provider = provider; state.apiKey = provider === 'offline' ? '' : key; state.model = model; state.topK = Number($('top-k').value); updateConnection(); $('settings-dialog').close(); toast('Đã áp dụng cấu hình cho tab này.');
});
$('test-connection').onclick = async () => {
  const button = $('test-connection'), output = $('connection-result'); output.hidden = false; output.classList.remove('error');
  if (!$('api-key').value.trim() && !state.hasDefaultKey) { output.textContent = t('Nhập API key và model để kiểm tra.'); output.classList.add('error'); return; }
  button.disabled = true; output.textContent = t('Đang kiểm tra quyền truy cập…');
  try { const data = await api('/api/connection', {provider: document.querySelector('input[name="provider"]:checked').value, api_key: $('api-key').value.trim(), model: $('model-name').value.trim()}); output.textContent = t(data.message); }
  catch (e) { output.textContent = t(e.message); output.classList.add('error'); }
  finally { button.disabled = false; }
};
$('clear-key').onclick = () => { state.apiKey = ''; state.provider = state.defaultProvider; state.model = state.defaultModel; $('api-key').value = ''; document.querySelector(`input[name="provider"][value="${state.provider}"]`).checked = true; $('model-name').value = state.model; settingsFields(); $('connection-result').hidden = true; updateConnection(); toast('Đã xóa key tùy chỉnh và khôi phục cấu hình mặc định.'); };
$('toggle-key').onclick = () => { const show = $('api-key').type === 'password'; $('api-key').type = show ? 'text' : 'password'; $('toggle-key').textContent = t(show ? 'Ẩn' : 'Hiện'); };
$('settings-dialog').addEventListener('close', () => { $('api-key').type = 'password'; $('toggle-key').textContent = t('Hiện'); $('api-key').value = ''; });
for (const radio of document.querySelectorAll('input[name="provider"]')) radio.onchange = () => settingsFields(true);
for (const b of document.querySelectorAll('[data-view]')) b.onclick = () => view(b.dataset.view);
for (const b of document.querySelectorAll('[data-task]')) b.onclick = () => setTask(b.dataset.task);
for (const b of document.querySelectorAll('[data-question]')) b.onclick = () => { $('question').value = b.dataset.question; state.selected = new Set([b.dataset.paper]); setTask('ask'); selection(); $('question').focus(); };
$('browse-library').onclick = $('collection-nav').onclick = () => view('library');
$('paper-search').oninput = renderLibrary;
$('open-settings').onclick = $('profile-settings').onclick = openSettings;
$('close-settings').onclick = () => $('settings-dialog').close();
$('close-source').onclick = () => $('source-dialog').close();
$('previous-page').onclick = () => { state.source.page--; renderSource(); };
$('next-page').onclick = () => { state.source.page++; renderSource(); };
$('source-image').onerror = () => toast('Không tải được trang. Thử mở PDF gốc.');
$('question').onkeydown = e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); $('question-form').requestSubmit(); } };
$('export-answer').onclick = () => {
  if (!state.active) return;
  const {question, result, provider, model} = state.active;
  const text = `# ${question}\n\n${result.answer.answer}\n\n---\n${provider === 'offline' ? 'Offline extractive' : model}\n\n## ${t('Bằng chứng')}\n\n` + result.answer.retrieved_evidence.map(r => `### ${r.evidence.paper_id} — ${t('trang')} ${r.evidence.page}\n\n${r.evidence.text}`).join('\n\n');
  const url = URL.createObjectURL(new Blob([text], {type: 'text/markdown;charset=utf-8'})); const a = el('a'); a.href = url; a.download = 'researchpilot-notes.md'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); toast('Đã xuất ghi chú Markdown.');
};
(async () => {
  try { const data = await api('/api/workspace'); state.papers = data.papers; state.defaultProvider = data.default_provider; state.defaultModel = data.default_model; state.hasDefaultKey = data.has_default_groq_key; state.provider = state.defaultProvider; state.model = state.defaultModel; updateConnection(); state.selected = new Set(data.papers.map(p => p.id)); $('library-count').textContent = t(data.papers.length); $('collection-description').textContent = t(`${data.papers.length} papers · Chọn nguồn cho câu hỏi của bạn`); $('rail-stats').textContent = t(`${data.papers.length} papers · ${data.pages} trang`); renderPapers(); }
  catch (e) { $('collection-description').textContent = t('Chưa tải được bộ sưu tập'); $('paper-grid').replaceChildren(); $('query-error').textContent = t(e.message); $('query-error').hidden = false; $('submit-question').disabled = true; }
})();

$('language').addEventListener('change', () => {
  setLanguage($('language').value);
  renderPapers(); renderHistory(); view(state.view); updateConnection();
  if (state.active) renderAnswer(state.active);
  if (state.source) renderSource();
  settingsFields();
  $('selection-count').textContent = t(state.selected.size + ' tài liệu');
  $('collection-description').textContent = t(`${state.papers.length} papers · Chọn nguồn cho câu hỏi của bạn`);
  $('rail-stats').textContent = t(`${state.papers.length} papers · ${state.papers.reduce((n,p) => n + p.pages, 0)} trang`);
  $('submit-question').querySelector('span').textContent = t(state.busy ? 'Đang đọc…' : 'Tìm câu trả lời');
});
setLanguage(language);

let importing = false;
function openImport() { if (!importing) $('import-status').hidden = true; $('import-dialog').showModal(); }
$('add-paper').onclick = $('add-paper-library').onclick = openImport;
$('close-import').onclick = () => { if (!importing) $('import-dialog').close(); };
$('import-dialog').addEventListener('cancel', e => { if (importing) e.preventDefault(); });
for (const radio of document.querySelectorAll('input[name="import-method"]')) radio.onchange = () => {
  $('import-url-field').hidden = radio.value !== 'url'; $('import-file-field').hidden = radio.value !== 'file';
};
$('import-form').addEventListener('submit', async e => {
  e.preventDefault(); if (importing) return;
  const status = $('import-status'); status.hidden = false; status.classList.remove('error');
  const method = document.querySelector('input[name="import-method"]:checked').value;
  const title = $('import-title').value.trim();
  let path, options;
  if (method === 'file') {
    const file = $('import-file').files[0];
    if (!file) { status.textContent = t('Chọn file PDF trước khi nhập.'); status.classList.add('error'); return; }
    if (file.size > 30 * 1024 * 1024) { status.textContent = t('Chọn file PDF hợp lệ, tối đa 30 MB.'); status.classList.add('error'); return; }
    path = '/api/import/file?title=' + encodeURIComponent(title);
    options = {method:'POST', headers:{'X-ResearchPilot':'workspace','Content-Type':'application/pdf'}, body:file};
  } else {
    if (!$('import-url').value.trim()) { status.textContent = t('Nhập link PDF hoặc arXiv hợp lệ.'); status.classList.add('error'); return; }
    path='/api/import/url'; options={method:'POST',headers:{'X-ResearchPilot':'workspace','Content-Type':'application/json'},body:JSON.stringify({url:$('import-url').value.trim(),title})};
  }
  importing=true; $('import-submit').disabled=true; $('close-import').disabled=true;
  status.textContent=t('Đang tải và xử lý PDF…');
  try {
    const response=await fetch(path,options); const data=await response.json();
    if (!response.ok) throw new Error(t(data.error));
    state.papers=data.workspace.papers; state.selected=new Set([data.paper_id]);
    $('library-count').textContent=state.papers.length;
    $('collection-description').textContent=t(`${state.papers.length} papers · Chọn nguồn cho câu hỏi của bạn`);
    $('rail-stats').textContent=t(`${state.papers.length} papers · ${data.workspace.pages} trang`);
    $('paper-search').value=''; renderPapers(); setTask('ask'); view('desk');
    $('import-dialog').close(); $('import-form').reset(); $('import-url-field').hidden=false; $('import-file-field').hidden=true;
    toast(data.duplicate ? 'Paper đã có trong thư viện.' : 'Đã thêm paper. Bạn có thể đặt câu hỏi ngay.');
    $('question').focus();
  } catch(err) { status.textContent=t(err.message); status.classList.add('error'); }
  finally { importing=false; $('import-submit').disabled=false; $('close-import').disabled=false; }
});
