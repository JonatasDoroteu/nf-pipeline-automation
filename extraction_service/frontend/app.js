const form = document.querySelector('#upload-form');
const input = document.querySelector('#file-input');
const dropzone = document.querySelector('#dropzone');
const fileLabel = document.querySelector('#file-label');
const fileHint = document.querySelector('#file-hint');
const submitButton = document.querySelector('#submit-button');
const resultEmpty = document.querySelector('#result-empty');
const resultContent = document.querySelector('#result-content');
const statusBadge = document.querySelector('#status-badge');
const resultStatus = document.querySelector('#result-status');
const resultReason = document.querySelector('#result-reason');
const steps = [...document.querySelectorAll('.pipeline-step')];
const apiKeyInput = document.querySelector('#api-key');
apiKeyInput.value = sessionStorage.getItem('nf-api-key') || '';
apiKeyInput.addEventListener('input', () => sessionStorage.setItem('nf-api-key', apiKeyInput.value));

const apiFetch = (url, options = {}) => {
  const headers = new Headers(options.headers || {});
  headers.set('X-API-Key', apiKeyInput.value.trim());
  return fetch(url, { ...options, headers });
};

const setStep = (current) => {
  const order = ['extract', 'validate', 'save'];
  steps.forEach((step) => {
    const index = order.indexOf(step.dataset.step);
    step.classList.toggle('active', index === current);
    step.classList.toggle('done', index < current);
  });
};

const setStatus = (label, tone) => {
  statusBadge.textContent = label;
  statusBadge.className = `status-badge ${tone}`;
};

const showResult = (result) => {
  resultEmpty.classList.add('hidden');
  resultContent.classList.remove('hidden');
  const data = result.dados_extraidos || {};
  const approved = result.status === 'aprovada';
  resultStatus.textContent = approved ? 'Aprovada' : result.status === 'rejeitada' ? 'Rejeitada' : 'Erro';
  resultStatus.style.color = approved ? '#267046' : '#a94431';
  resultReason.textContent = result.motivo || (approved ? 'Regras de negócio validadas com sucesso.' : 'Não foi possível concluir o processamento.');
  document.querySelector('#data-number').textContent = data.numero_nota || 'Não identificado';
  document.querySelector('#data-cnpj').textContent = data.cnpj_emitente || 'Não identificado';
  document.querySelector('#data-value').textContent = data.valor_total != null ? `R$ ${Number(data.valor_total).toFixed(2).replace('.', ',')}` : 'Não identificado';
  document.querySelector('#data-date').textContent = data.data_emissao || 'Não identificada';
  setStatus(approved ? 'Aprovada' : result.status === 'rejeitada' ? 'Rejeitada' : 'Erro', approved ? 'approved' : 'rejected');
};

const selectFile = (file) => {
  if (!file) return;
  const size = `${(file.size / 1024 / 1024).toFixed(2)} MB`;
  fileLabel.textContent = file.name;
  fileHint.textContent = `${size} · pronto para processar`;
  dropzone.classList.add('dragging');
};
input.addEventListener('change', () => selectFile(input.files[0]));
['dragenter', 'dragover'].forEach((event) => dropzone.addEventListener(event, (e) => { e.preventDefault(); dropzone.classList.add('dragging'); }));
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragging'));
dropzone.addEventListener('drop', (e) => { e.preventDefault(); input.files = e.dataTransfer.files; selectFile(input.files[0]); });

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!input.files[0]) return;
  submitButton.disabled = true;
  submitButton.querySelector('span').textContent = 'Processando documento...';
  resultContent.classList.add('hidden');
  resultEmpty.classList.remove('hidden');
  setStatus('Em processamento', 'processing');
  setStep(0);
  const body = new FormData(); body.append('file', input.files[0]);
  try {
    setTimeout(() => setStep(1), 600);
    const response = await apiFetch('/process', { method: 'POST', body });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Falha no processamento');
    setStep(result.status === 'erro' ? 2 : 3);
    showResult(result);
  } catch (error) {
    setStatus('Erro', 'error');
    showResult({ status: 'erro', motivo: error.message });
  } finally {
    submitButton.disabled = false;
    submitButton.querySelector('span').textContent = 'Processar nota';
  }
});

document.querySelector('#new-process').addEventListener('click', () => {
  form.reset(); fileLabel.textContent = 'Arraste sua nota aqui'; fileHint.textContent = 'ou clique para procurar um arquivo'; dropzone.classList.remove('dragging'); resultContent.classList.add('hidden'); resultEmpty.classList.remove('hidden'); setStatus('Aguardando', 'idle'); setStep(-1);
});

document.querySelector('#lookup-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const number = document.querySelector('#lookup-number').value.trim();
  const target = document.querySelector('#lookup-result');
  target.classList.remove('hidden'); target.innerHTML = '<p>Consultando...</p>';
  try {
    const response = await apiFetch(`/notas/${encodeURIComponent(number)}/status`);
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail || 'Nota não encontrada');
    target.innerHTML = `<strong>${result.status === 'aprovada' ? 'Aprovada' : 'Rejeitada'}</strong><p>Nota ${result.numero_nota} · ${result.motivo_rejeicao || 'Sem ressalvas'}</p>`;
  } catch (error) { target.innerHTML = `<strong style="color:#a94431">Não encontrada</strong><p>${error.message}</p>`; }
});
