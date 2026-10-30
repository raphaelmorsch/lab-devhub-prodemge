async function loadApps() {
  const alertRoot = document.getElementById('status-alert');
  const root = document.getElementById('apps');
  setAlert(alertRoot, 'info', 'Carregando aplicações…');
  root.innerHTML = '';

  try {
    const res = await fetch('/api/apps');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = data.items || [];

    if (!items.length) {
      alertRoot.hidden = true;
      root.innerHTML = emptyState();
      return;
    }

    setAlert(
      alertRoot,
      'success',
      `${items.length} aplicação(ões) disponível(is) para download.`,
    );
    root.innerHTML = items.map(renderAppCard).join('');
  } catch (err) {
    setAlert(alertRoot, 'danger', `Falha ao carregar: ${err.message}`);
    root.innerHTML = '';
  }
}

function renderAppCard(app) {
  const latest = app.latest || {};
  const download = latest.downloadPath
    ? `<a class="pf-v5-c-button pf-m-primary" href="${escapeAttr(latest.downloadPath)}">
         <span class="pf-v5-c-button__icon pf-m-start">
           <i class="fas fa-download" aria-hidden="true"></i>
         </span>
         Baixar APK
       </a>`
    : '';

  return `
    <div class="pf-v5-c-card pf-m-display-lg" id="card-${escapeAttr(app.id)}">
      <div class="pf-v5-c-card__header">
        <div class="pf-v5-c-card__header-main">
          <h2 class="pf-v5-c-title pf-m-lg app-card-title">${escapeHtml(app.id)}</h2>
        </div>
        <div class="pf-v5-c-card__actions">
          <span class="pf-v5-c-label pf-m-blue">
            <span class="pf-v5-c-label__content">${escapeHtml(String(app.releaseCount))} release(s)</span>
          </span>
        </div>
      </div>
      <div class="pf-v5-c-card__body">
        <dl class="pf-v5-c-description-list pf-m-2-col-on-lg">
          ${descItem('Versão', latest.versionName || '—')}
          ${descItem('Ambiente', latest.environment || latest.flavor || '—')}
          ${descItem('Publicado em', formatDate(latest.createdAt))}
          ${descItem('Commit', short(latest.gitCommit) || '—')}
          ${descItem('Tamanho', formatBytes(latest.apkSizeBytes))}
          ${descItem('PipelineRun', latest.pipelineRun || '—')}
        </dl>
      </div>
      <div class="pf-v5-c-card__footer">
        ${download}
      </div>
    </div>
  `;
}

function descItem(term, value) {
  return `
    <div class="pf-v5-c-description-list__group">
      <dt class="pf-v5-c-description-list__term">
        <span class="pf-v5-c-description-list__text">${escapeHtml(term)}</span>
      </dt>
      <dd class="pf-v5-c-description-list__description">
        <div class="pf-v5-c-description-list__text app-meta-value">${escapeHtml(value)}</div>
      </dd>
    </div>
  `;
}

function emptyState() {
  return `
    <div class="pf-v5-c-empty-state pf-m-lg">
      <div class="pf-v5-c-empty-state__content">
        <i class="fas fa-box-open pf-v5-c-empty-state__icon" aria-hidden="true"></i>
        <h2 class="pf-v5-c-title pf-m-lg">Nenhuma aplicação publicada</h2>
        <div class="pf-v5-c-empty-state__body">
          Publique um APK pela esteira Tekton para aparecer aqui.
        </div>
      </div>
    </div>
  `;
}

function setAlert(el, variant, message) {
  const icons = {
    info: 'fa-info-circle',
    success: 'fa-check-circle',
    danger: 'fa-exclamation-circle',
  };
  el.hidden = false;
  el.innerHTML = `
    <div class="pf-v5-c-alert pf-m-${variant}" aria-label="${escapeAttr(variant)}">
      <div class="pf-v5-c-alert__icon">
        <i class="fas ${icons[variant] || icons.info}" aria-hidden="true"></i>
      </div>
      <p class="pf-v5-c-alert__title">${escapeHtml(message)}</p>
    </div>
  `;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function escapeAttr(value) {
  return escapeHtml(value).replaceAll("'", '&#39;');
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
