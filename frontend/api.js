export const session = { user: null, csrf: null };

export async function api(path, { method = 'GET', data, ...options } = {}) {
  const headers = { ...(options.headers || {}) };
  if (session.csrf && method !== 'GET') headers['X-CSRF-Token'] = session.csrf;
  if (data !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(`/api${path}`, { ...options, method, headers, credentials: 'same-origin',
    body: data === undefined ? undefined : JSON.stringify(data) });
  if (response.status === 204) return null;
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    let detail = result.detail || 'Не удалось выполнить запрос. Попробуйте ещё раз';
    if (Array.isArray(detail)) detail = detail.map(x => x.msg).join('. ');
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  return result;
}

export async function refreshSession() {
  const result = await api('/auth/me');
  session.user = result.user;
  session.csrf = result.csrf_token;
}

export function uploadSource(id, file, onProgress, signal) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', `/api/videos/${encodeURIComponent(id)}/source`);
    xhr.setRequestHeader('X-CSRF-Token', session.csrf);
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.upload.onprogress = e => { if (e.lengthComputable) onProgress(Math.round(e.loaded / e.total * 100)); };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else {
        let message = 'Не удалось загрузить файл. Повторите попытку';
        try { message = JSON.parse(xhr.responseText).detail || message; } catch { /* network error */ }
        reject(new Error(message));
      }
    };
    xhr.onerror = () => reject(new Error('Соединение прервано. Проверьте подключение'));
    xhr.onabort = () => reject(new Error('Загрузка отменена'));
    if (signal) signal.addEventListener('abort', () => xhr.abort(), { once: true });
    xhr.send(file);
  });
}
