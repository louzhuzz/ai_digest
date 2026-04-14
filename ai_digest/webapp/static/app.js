const elements = {
  markdown: document.querySelector('#markdown'),
  preview: document.querySelector('#preview'),
  history: document.querySelector('#history'),
  statusText: document.querySelector('#status-text'),
  statusBadge: document.querySelector('#status-badge'),
  statusDetail: document.querySelector('#status-detail'),
  draftId: document.querySelector('#draft-id'),
  run: document.querySelector('#run'),
  publish: document.querySelector('#publish'),
  refresh: document.querySelector('#refresh')
};

let saveTimer = null;

function setStatus(status, detail = '', draftId = '') {
  const normalized = (status || 'idle').toLowerCase();
  const badgeMap = {
    idle: '待机',
    pending: '待机',
    running: '运行中',
    composed: '已生成',
    published: '已发布',
    failed: '失败'
  };
  const classMap = {
    idle: 'pending',
    pending: 'pending',
    running: 'running',
    composed: 'success',
    published: 'success',
    failed: 'error'
  };

  elements.statusText.textContent = badgeMap[normalized] || status || '--';
  elements.statusBadge.textContent = badgeMap[normalized] || '待机';
  elements.statusBadge.className = `status-badge ${classMap[normalized] || 'pending'}`;
  elements.statusDetail.textContent = detail || '等待生成草稿。';
  elements.draftId.textContent = draftId || '--';
}

function renderHistory(items) {
  elements.history.innerHTML = '';
  if (!items || items.length === 0) {
    const empty = document.createElement('li');
    empty.className = 'history-empty';
    empty.textContent = '还没有运行记录。';
    elements.history.appendChild(empty);
    return;
  }

  items.slice().reverse().forEach((item) => {
    const li = document.createElement('li');
    li.className = 'history-item';

    const main = document.createElement('div');
    main.className = 'history-main';

    const title = document.createElement('div');
    title.className = 'history-title';
    title.textContent = `${item.mode || 'run'} ${item.timestamp || ''}`.trim();

    const meta = document.createElement('div');
    meta.className = 'history-meta';
    const parts = [];
    if (item.error) {
      parts.push(`错误: ${item.error}`);
    }
    if (item.draft_id) {
      parts.push(`草稿ID: ${item.draft_id}`);
    }
    if (item.items_count) {
      parts.push(`条目数: ${item.items_count}`);
    }
    meta.textContent = parts.join(' / ') || '无额外信息';

    const status = document.createElement('div');
    status.className = `history-status ${(item.status || 'unknown').toLowerCase()}`;
    status.textContent = item.status || 'unknown';

    main.appendChild(title);
    main.appendChild(meta);
    li.appendChild(main);
    li.appendChild(status);
    elements.history.appendChild(li);
  });
}

async function fetchPreview() {
  const resp = await fetch('/api/preview');
  const data = await resp.json();
  elements.markdown.value = data.markdown || '';
  elements.preview.innerHTML = data.html || '<p>暂无预览内容。</p>';
}

async function fetchHistory() {
  const resp = await fetch('/api/history');
  const data = await resp.json();
  renderHistory(data.items || []);
}

async function postJson(url, body) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : null
  });
  return resp.json();
}

async function runDraft() {
  setStatus('running', '正在抓取和生成今日草稿...');
  const data = await postJson('/api/run');
  setStatus(data.status, data.error || '草稿已生成，可以继续编辑或直接提交。', data.draft_id || '');
  await fetchPreview();
  await fetchHistory();
}

async function publishDraft() {
  setStatus('running', '正在提交公众号草稿...');
  const data = await postJson('/api/publish');
  const detail = data.error || '公众号草稿提交完成。';
  setStatus(data.status, detail, data.draft_id || '');
  await fetchHistory();
}

async function refreshAll() {
  setStatus('pending', '已刷新当前草稿与历史记录。', elements.draftId.textContent === '--' ? '' : elements.draftId.textContent);
  await fetchPreview();
  await fetchHistory();
}

async function saveMarkdown(markdown) {
  await postJson('/api/update', { markdown });
  elements.statusDetail.textContent = '草稿已自动保存。';
  await fetchPreview();
}

elements.run.onclick = async () => {
  await runDraft();
};

elements.publish.onclick = async () => {
  await publishDraft();
};

elements.refresh.onclick = async () => {
  await refreshAll();
};

elements.markdown.oninput = (evt) => {
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(async () => {
    await saveMarkdown(evt.target.value);
  }, 400);
};

fetchPreview();
fetchHistory();
setStatus('pending', '等待生成草稿。');

// Fact Card Panel
const factCardBtn = document.getElementById('fact-card-btn');
const factCardPanel = document.getElementById('fact-card-panel');
const factCardClose = document.getElementById('fact-card-close');
const factCardContent = document.getElementById('fact-card-content');

if (factCardBtn && factCardPanel && factCardClose && factCardContent) {
  factCardBtn.addEventListener('click', async () => {
    factCardPanel.style.display = 'block';
    factCardContent.innerHTML = '<p style="color:#666;">加载中...</p>';
    try {
      const res = await fetch('/api/fact-card');
      const data = await res.json();
      renderFactCard(data, factCardContent);
    } catch (e) {
      factCardContent.innerHTML = '<p style="color:red;">加载失败: ' + e.message + '</p>';
    }
  });

  factCardClose.addEventListener('click', () => {
    factCardPanel.style.display = 'none';
  });
}

function renderFactCard(data, container) {
  if (!data.clusters || data.clusters.length === 0) {
    container.innerHTML = '<p style="color:#666;">暂无数据，请先生成草稿。</p>';
    return;
  }

  const totalItems = data.total_items || 0;
  const dist = data.source_distribution || {};
  const distText = Object.entries(dist).map(([k, v]) => `${k}: ${v}`).join(' / ') || '无';

  let html = `<p style="margin:0 0 12px 0; color:#374151; font-size:14px;"><strong>${totalItems} 条入选</strong> &nbsp;${distText}</p>`;

  data.clusters.forEach(cluster => {
    const tag = cluster.topic_tag || '未分类';
    const title = cluster.canonical_title || cluster.title || '';
    const sources = Array.isArray(cluster.sources) ? cluster.sources.join(', ') : (cluster.sources || '');
    const isMulti = sources.includes(',');
    const multiBadge = isMulti ? '✅ 多源' : '❌ 单源';

    html += `<div style="border:1px solid #e5e7eb; border-radius:6px; padding:10px; margin-bottom:8px;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="background:#dbeafe; color:#1d4ed8; font-size:11px; padding:2px 6px; border-radius:3px;">${tag}</span>
        <span style="font-size:11px; color:#9ca3af;">${multiBadge}</span>
      </div>
      <p style="margin:6px 0 0 0; font-size:13px; color:#111;">${title}</p>
      <p style="margin:2px 0 0 0; font-size:11px; color:#6b7280;">来源: ${sources}</p>
    </div>`;
  });

  container.innerHTML = html;
}
