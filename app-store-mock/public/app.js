async function loadApps() {
  const status = document.getElementById('status');
  const root = document.getElementById('apps');
  status.textContent = 'Carregando…';
  root.innerHTML = '';

  try {
    const res = await fetch('/api/apps');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = data.items || [];

    if (!items.length) {
      status.textContent = 'Nenhuma aplicação publicada ainda.';
      root.innerHTML = '<p class="empty">Publique um APK pela esteira Tekton para aparecer aqui.</p>';
      return;
    }

    status.textContent = `${items.length} aplicação(ões)`;
    root.innerHTML = items
      .map((app) => {
        const latest = app.latest || {};
        const download = latest.downloadPath
          ? `<a href="${latest.downloadPath}">Baixar APK</a>`
          : '';
        return `
          <article class="card">
            <div class="card-top">
              <h3>${escapeHtml(app.id)}</h3>
              <span class="pill">${app.releaseCount} release(s)</span>
            </div>
            <div class="meta">
              <div>
                <span>Versão</span>
                <strong>${escapeHtml(latest.versionName || '—')}</strong>
              </div>
              <div>
                <span>Ambiente</span>
                <strong>${escapeHtml(latest.environment || latest.flavor || '—')}</strong>
              </div>
              <div>
                <span>Publicado em</span>
                <strong>${escapeHtml(formatDate(latest.createdAt))}</strong>
              </div>
              <div>
                <span>Commit</span>
                <strong>${escapeHtml(short(latest.gitCommit) || '—')}</strong>
              </div>
              <div>
                <span>Tamanho</span>
                <strong>${formatBytes(latest.apkSizeBytes)}</strong>
              </div>
              <div>
                <span>PipelineRun</span>
                <strong>${escapeHtml(latest.pipelineRun || '—')}</strong>
              </div>
            </div>
            <div class="actions">${download}</div>
          </article>
        `;
      })
      .join('');
  } catch (err) {
    status.textContent = `Falha ao carregar: ${err.message}`;
  }
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function short(value) {
  if (!value) return '';
  return String(value).slice(0, 12);
}

function formatDate(value) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString('pt-BR');
  } catch {
    return String(value);
  }
}

function formatBytes(n) {
  const num = Number(n);
  if (!Number.isFinite(num) || num <= 0) return '—';
  if (num < 1024) return `${num} B`;
  if (num < 1024 * 1024) return `${(num / 1024).toFixed(1)} KB`;
  return `${(num / (1024 * 1024)).toFixed(1)} MB`;
}

document.getElementById('refresh').addEventListener('click', loadApps);
loadApps();
