import { api, session, refreshSession, uploadSource } from './api.js';
import { icon } from './icons.js';

const app = document.querySelector('#app');
const dialog = document.querySelector('#dialog');
const topics = ['Все', 'Природа', 'Путешествия', 'Технологии', 'Музыка', 'Архитектура', 'Кулинария', 'Вдохновение'];
const statusNames = { uploading: 'Ожидает файл', receiving: 'Загружается', queued: 'В очереди', processing: 'Обрабатывается', ready: 'Опубликовано', failed: 'Ошибка обработки' };
let generation = 0, currentTopic = 'Все', compact = false, currentVideo = null, studioVideos = [], uploadBusy = false, routeTimer;
let toastTimer, currentComments = [];
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const enc = value => encodeURIComponent(value);
const num = n => new Intl.NumberFormat('ru-RU', { notation: n >= 10000 ? 'compact' : 'standard', maximumFractionDigits: 1 }).format(n || 0);
const duration = seconds => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
const date = timestamp => new Date(timestamp * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
function ago(timestamp) {
  const days = Math.floor((Date.now() / 1000 - timestamp) / 86400);
  if (days <= 0) return 'сегодня';
  if (days === 1) return 'вчера';
  if (days < 7) return `${days} дн. назад`;
  if (days < 30) return `${Math.floor(days / 7)} нед. назад`;
  return date(timestamp);
}
function avatar(user, cls = '') {
  const color = /^#[0-9a-f]{6}$/i.test(user?.color || '') ? user.color : '#065fd4';
  return `<span class="avatar ${cls}" style="--avatar:${color}" aria-hidden="true">${esc(user?.name?.[0]?.toUpperCase() || '?')}</span>`;
}
function toast(message) {
  const target = document.querySelector('#toast');
  target.textContent = message;
  target.classList.add('visible');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => target.classList.remove('visible'), 4500);
}
function navLink(path, name, symbol, key, extended = false) {
  return `<a href="${path}" data-link data-nav="${key}" class="nav-link ${location.pathname === path ? 'active' : ''} ${extended ? 'extended-nav' : ''}">${icon(symbol)}<span>${name}</span></a>`;
}
function shell() {
  const user = session.user;
  app.innerHTML = `<header class="topbar">
    <div class="brand-group"><button class="icon-btn" data-action="menu" aria-label="Переключить меню">${icon('menu')}</button>
      <a class="brand" href="/" data-link aria-label="YouTube — главная"><img src="/static/favicon.svg" alt=""><span class="brand-word">YouTube</span><span class="brand-country">RU</span></a></div>
    <form class="search" id="search-form" role="search"><input name="q" type="search" placeholder="Введите запрос" aria-label="Поиск видео" maxlength="140" value="${esc(new URLSearchParams(location.search).get('search_query') || '')}"><button aria-label="Найти">${icon('search')}</button></form>
    <div class="header-actions"><a class="btn btn-neutral" href="/upload" data-link>${icon('plus')} Создать</a>
      ${user ? `<button class="account-button" data-action="account" aria-label="Аккаунт ${esc(user.name)}">${avatar(user, 'sm')}</button>` : `<button class="btn btn-outline" data-action="login">${icon('user')}Войти</button>`}</div>
    </header>
    <aside class="sidebar" aria-label="Основная навигация">
      <div class="nav-section">${navLink('/', 'Главная', 'home', 'home')}${navLink('/subscriptions', 'Подписки', 'subscriptions', 'subscriptions')}</div>
      <div class="nav-section"><div class="nav-label">Вы ${icon('chevron')}</div>
        ${user ? navLink(`/channel/${enc(user.handle)}`, 'Мой канал', 'user', 'channel', true) : ''}
        ${navLink('/playlists', 'Плейлисты', 'list', 'playlists')}${navLink('/liked', 'Понравившиеся', 'like', 'liked', true)}${navLink('/studio', 'Мои видео', 'studio', 'studio')}
        ${user?.role === 'moderator' || user?.role === 'admin' ? navLink('/moderation', 'Модерация', 'shield', 'moderation', true) : ''}
        ${user?.role === 'admin' ? navLink('/admin', 'Пользователи', 'user', 'admin', true) : ''}</div>
      ${!user ? `<div class="nav-section nav-copy"><p>Войдите, чтобы ставить лайки, оставлять комментарии и подписываться.</p><button class="btn btn-outline" data-action="login">${icon('user')}Войти</button></div>` : `<div class="nav-section extended-nav"><div class="nav-label">Подписки</div><div id="sidebar-subs"></div></div>`}
      <div class="sidebar-footer"><strong>Видео · Каналы · Вдохновение</strong>Учебный проект StackBridge<br>Независимая копия интерфейса</div>
    </aside><main class="main" id="content" tabindex="-1"></main>`;
  document.body.classList.toggle('compact', compact || location.pathname.startsWith('/watch/'));
  if (user) api('/subscriptions').then(r => {
    const target = document.querySelector('#sidebar-subs');
    if (target) target.innerHTML = r.items.length ? r.items.slice(0, 8).map(u => `<a class="nav-link" href="/channel/${enc(u.handle)}" data-link>${avatar(u, 'sm')}<span>${esc(u.name)}</span></a>`).join('') : '<p class="nav-copy">Здесь появятся ваши каналы</p>';
  }).catch(() => {});
}
function skeleton() {
  return `<div class="video-grid loader" aria-label="Загрузка видео">${Array.from({ length: 9 }, () => '<div><div class="skeleton-thumb"></div><div class="skeleton-line"></div><div class="skeleton-line short"></div></div>').join('')}</div>`;
}
function empty(title, text, symbol = 'play', button = '') {
  return `<div class="empty">${icon(symbol)}<h1>${esc(title)}</h1><p>${esc(text)}</p>${button}</div>`;
}
function loginGate(title) {
  return empty(title, 'Войдите в аккаунт или создайте новый. Ваши видео, подписки и плейлисты будут здесь.', 'user', '<button class="btn btn-outline" data-action="login">Войти</button>');
}
function card(v) {
  return `<article class="video-card"><a class="thumbnail" href="/watch/${enc(v.id)}" data-link aria-label="Смотреть ${esc(v.title)}">
    ${v.thumbnail ? `<img src="${esc(v.thumbnail)}" alt="" loading="lazy" decoding="async">` : ''}<span class="duration">${duration(v.duration)}</span></a>
    <div class="card-details"><a href="/channel/${enc(v.channel.handle)}" data-link aria-label="Канал ${esc(v.channel.name)}">${avatar(v.channel)}</a>
    <div class="card-copy"><h2 class="card-title"><a href="/watch/${enc(v.id)}" data-link>${esc(v.title)}</a></h2>
    <div class="card-meta"><a class="channel-link" href="/channel/${enc(v.channel.handle)}" data-link>${esc(v.channel.name)}</a>${v.visibility === 'private' ? `<span class="card-lock" title="Приватное видео">${icon('lock')}</span>` : ''}<br>${num(v.views)} просмотров · ${ago(v.created_at)}</div></div></div></article>`;
}
function categoryChips() {
  return `<div class="topics" aria-label="Категории">${topics.map(t => `<button class="chip ${currentTopic === t ? 'selected' : ''}" data-action="topic" data-value="${esc(t)}">${t}</button>`).join('')}</div>`;
}
async function feedPage(path, token) {
  const query = new URLSearchParams(location.search).get('search_query') || '';
  let endpoint = '/videos?limit=24';
  let heading = '', searchMode = false;
  if (path === '/results') { endpoint += `&q=${enc(query)}`; heading = `Результаты по запросу «${query}»`; searchMode = true; }
  else if (path === '/subscriptions') { endpoint += '&feed=subscriptions'; heading = 'Новые видео ваших каналов'; }
  else if (path === '/liked') { endpoint += '&feed=liked'; heading = 'Понравившиеся видео'; }
  else if (currentTopic !== 'Все') endpoint += `&category=${enc(currentTopic)}`;
  if ((path === '/subscriptions' || path === '/liked') && !session.user) return loginGate(path === '/subscriptions' ? 'Ваши подписки' : 'Понравившиеся видео');
  const data = await api(endpoint);
  if (token !== generation) return null;
  document.title = heading ? `${heading} — YouTube` : 'YouTube · StackBridge';
  return `${path === '/' ? categoryChips() : `<h1 class="page-heading">${esc(heading)}</h1>`}
    ${data.items.length ? `<div class="${searchMode ? 'results-list' : 'video-grid'}" id="video-list">${data.items.map(card).join('')}</div>${data.has_more ? `<div class="load-more"><button class="btn btn-neutral" data-action="more-videos" data-endpoint="${esc(endpoint)}" data-offset="24">Показать ещё</button></div>` : ''}` : empty(searchMode ? 'Ничего не найдено' : 'Здесь пока нет видео', searchMode ? 'Попробуйте другое название или более короткий запрос.' : 'Выберите другую категорию, подпишитесь на каналы или загрузите своё первое видео.', searchMode ? 'search' : 'play')}`;
}
function commentsHTML(items) {
  return items.map(c => `<article class="comment-item">${avatar(c.author)}<div class="comment-body"><a class="comment-author" href="/channel/${enc(c.author.handle)}" data-link>@${esc(c.author.handle)}</a><span class="comment-author comment-time">${ago(c.created_at)}</span><p class="comment-text">${esc(c.body)}</p></div>${c.can_delete ? `<button class="icon-btn" data-action="delete-comment" data-id="${enc(c.id)}" aria-label="Удалить комментарий">${icon('trash')}</button>` : ''}</article>`).join('');
}
async function watchPage(id, token) {
  const v = await api(`/videos/${enc(id)}`);
  const [recommendations, comments, channel] = await Promise.all([api('/videos?limit=12'), api(`/videos/${enc(id)}/comments`), api(`/channels/${enc(v.channel.handle)}`)]);
  if (token !== generation) return null;
  currentVideo = v; currentComments = comments.items;
  document.title = `${v.title} — YouTube`;
  return `<div class="watch-layout"><section>
    <div class="player-wrap">${v.status === 'ready' ? `<video id="video-player" controls playsinline preload="metadata" poster="${esc(v.thumbnail || '')}" src="${esc(v.media)}" aria-label="${esc(v.title)}"></video>` : `<div class="player-message">${icon('play')}<strong>${esc(statusNames[v.status])}</strong><p>${esc(v.error || 'Готовим видео к просмотру. Это может занять несколько минут.')}</p></div>`}</div>
    <h1 class="watch-title">${esc(v.title)}</h1>
    <div class="watch-actions"><div class="channel-row"><a href="/channel/${enc(v.channel.handle)}" data-link>${avatar(v.channel)}</a><div><a href="/channel/${enc(v.channel.handle)}" data-link><strong>${esc(v.channel.name)}</strong></a><span class="muted" id="subscriber-count">${num(channel.subscribers)} подписчиков</span></div>
    ${session.user?.id === v.channel.id ? `<a class="btn btn-neutral" href="/studio" data-link>Мои видео</a>` : `<button class="btn ${channel.subscribed ? 'btn-neutral' : 'btn-primary'}" data-action="subscribe" data-handle="${enc(v.channel.handle)}" data-subscribed="${channel.subscribed}">${channel.subscribed ? 'Вы подписаны' : 'Подписаться'}</button>`}</div>
    <div class="watch-tools"><button class="btn btn-neutral" data-action="like" aria-pressed="${v.liked}">${icon('like')}<span>${num(v.likes)}</span></button><button class="btn btn-neutral" data-action="save">${icon('list')}Сохранить</button><button class="btn btn-neutral" data-action="share">${icon('share')}Поделиться</button><button class="icon-btn" data-action="report" aria-label="Пожаловаться на видео">${icon('flag')}</button></div></div>
    ${v.hidden ? `<div class="notice error-note" style="margin-top:16px">Видео скрыто модератором: ${esc(v.moderation_reason)}. Общий доступ закрыт; разрешения на приватное видео задаёт владелец.</div>` : ''}
    <div class="description" id="description"><strong>${num(v.views)} просмотров · ${date(v.created_at)}${v.visibility === 'private' ? ' · Приватное видео' : ''}</strong><div class="description-text">${esc(v.description || 'Автор пока не добавил описание.')}</div><button class="text-button" data-action="description">Ещё</button></div>
    <h2 class="comment-heading"><span id="comments-count">${v.comments}</span> комментариев</h2>
    ${session.user ? `<form class="comment-form" data-form="comment">${avatar(session.user)}<div><textarea name="body" placeholder="Введите комментарий" aria-label="Текст комментария" maxlength="2000" required rows="1"></textarea><div class="form-error" role="alert"></div><div class="comment-submit"><button class="btn btn-blue">Оставить комментарий</button></div></div></form>` : `<div class="notice"><button class="text-button" data-action="login">Войдите</button>, чтобы оставить комментарий.</div>`}
    <div id="comments-list">${commentsHTML(comments.items)}</div>
    </section><aside class="recommendations" aria-label="Другие видео"><h2>Смотрите также</h2>${recommendations.items.filter(x => x.id !== id).slice(0, 10).map(card).join('')}</aside></div>`;
}
async function channelPage(handle, token) {
  const r = await api(`/channels/${enc(handle)}`);
  if (token !== generation) return null;
  const u = r.channel, playlists = new URLSearchParams(location.search).get('tab') === 'playlists';
  document.title = `${u.name} — YouTube`;
  return `<div class="channel-banner"><span>${esc(u.name)}</span></div><div class="channel-intro">${avatar(u, 'lg')}<div><h1>${esc(u.name)}</h1><div class="muted">@${esc(u.handle)} · ${num(r.subscribers)} подписчиков · ${r.videos.length} видео<br>${esc(u.description || 'Место для новых историй и интересных видео.')}</div>
    ${session.user?.id === u.id ? '<button class="btn btn-neutral" data-action="edit-channel">Настроить канал</button>' : `<button class="btn ${r.subscribed ? 'btn-neutral' : 'btn-primary'}" data-action="subscribe" data-handle="${enc(u.handle)}" data-subscribed="${r.subscribed}">${r.subscribed ? 'Вы подписаны' : 'Подписаться'}</button>`}</div></div>
    <nav class="tabs" aria-label="Разделы канала"><a class="tab ${!playlists ? 'active' : ''}" href="/channel/${enc(u.handle)}" data-link>Видео</a><a class="tab ${playlists ? 'active' : ''}" href="/channel/${enc(u.handle)}?tab=playlists" data-link>Плейлисты</a></nav>
    ${playlists ? (r.playlists.length ? `<div class="video-grid">${r.playlists.map(playlistTile).join('')}</div>` : empty('Плейлистов пока нет', 'Автор ещё не создал плейлисты.', 'list')) : (r.videos.length ? `<div class="video-grid">${r.videos.map(card).join('')}</div>` : empty('Видео пока нет', 'Здесь появятся опубликованные видео канала.', 'play'))}`;
}
function playlistTile(p) {
  return `<a class="playlist-tile" href="/playlist/${enc(p.id)}" data-link>${icon('list')}<strong>${esc(p.title)}</strong><span class="muted">${p.visibility === 'private' ? 'Личный плейлист' : 'Открыть плейлист'} →</span></a>`;
}
async function playlistsPage(token) {
  if (!session.user) return loginGate('Ваши плейлисты');
  const r = await api('/playlists');
  if (token !== generation) return null;
  return `<div class="studio-top"><h1>Плейлисты</h1><button class="btn btn-neutral" data-action="new-playlist">${icon('plus')}Создать плейлист</button></div>${r.items.length ? `<div class="video-grid">${r.items.map(playlistTile).join('')}</div>` : empty('Соберите свою подборку', 'Создайте плейлист, а затем добавляйте в него видео кнопкой «Сохранить».', 'list')}`;
}
async function playlistPage(id, token) {
  const p = await api(`/playlists/${enc(id)}`);
  if (token !== generation) return null;
  document.title = `${p.title} — YouTube`;
  return `<div class="playlist-hero">${icon('list')}<div><h1>${esc(p.title)}</h1><p>${esc(p.owner.name)} · ${p.videos.length} видео · ${p.visibility === 'private' ? 'Личный плейлист' : 'Открытый плейлист'}</p></div>${p.can_edit ? `<button class="icon-btn" data-action="delete-playlist" data-id="${enc(id)}" aria-label="Удалить плейлист">${icon('trash')}</button>` : ''}</div>
    ${p.videos.length ? `<div class="results-list">${p.videos.map(v => `<div>${card(v)}${p.can_edit ? `<button class="text-button" data-action="remove-playlist-video" data-playlist="${enc(id)}" data-id="${enc(v.id)}">Убрать из плейлиста</button>` : ''}</div>`).join('')}</div>` : empty('В плейлисте пока нет видео', 'Добавляйте доступные вам видео кнопкой «Сохранить» на странице просмотра.', 'list')}`;
}
async function uploadPage() {
  if (!session.user) return loginGate('Загрузите своё видео');
  const config = await api('/config');
  return `<section class="form-page"><div class="panel"><h1>Загрузка видео</h1><p class="form-intro">Поделитесь тем, что вам интересно. Сначала загрузите файл, затем мы подготовим его к просмотру.</p>
    <form data-form="upload" id="upload-form" data-max="${config.max_upload_bytes}"><label class="dropzone" id="dropzone">${icon('upload')}<strong id="file-label">Перетащите видео сюда</strong><small>Или выберите файл на компьютере<br>MP4, WebM, MOV · до ${Math.round(config.max_upload_bytes / 1048576)} МБ</small><input type="file" name="video" accept="video/*,.mkv,.mov,.webm,.mp4" required aria-label="Видео для загрузки"></label>
    <label class="field"><span>Название</span><input name="title" maxlength="140" placeholder="Придумайте название видео" required></label><label class="field"><span>Описание</span><textarea name="description" maxlength="5000" placeholder="Расскажите, о чём ваше видео" rows="4"></textarea></label>
    <div class="field-row"><label class="field"><span>Категория</span><select name="category">${topics.filter(t => t !== 'Все').map(t => `<option>${t}</option>`).join('')}<option>Разное</option></select></label><label class="field"><span>Доступ</span><select name="visibility"><option value="public">Открытый — для всех</option><option value="private">Приватный — по разрешению</option></select><small>Для приватного видео выберите зрителей в разделе «Мои видео». Для просмотра другим пользователем требуется ваше разрешение.</small></label></div>
    <div id="upload-status"></div><div class="form-error" role="alert"></div><div class="form-footer"><button class="btn btn-blue" type="submit">${icon('upload')}Загрузить видео</button></div></form></div></section>`;
}
async function studioPage(token) {
  if (!session.user) return loginGate('Ваши видео');
  const r = await api('/studio');
  if (token !== generation) return null;
  studioVideos = r.items;
  if (r.items.some(v => ['queued', 'processing', 'receiving'].includes(v.status))) routeTimer = setTimeout(() => renderRoute(false), 3000);
  return `<div class="studio-top"><h1>Мои видео</h1><a class="btn btn-blue" href="/upload" data-link>${icon('upload')}Загрузить видео</a></div>
    ${r.items.length ? r.items.map(v => `<article class="studio-item">${v.thumbnail ? `<a href="/watch/${enc(v.id)}" data-link><img class="studio-thumb" src="${esc(v.thumbnail)}" alt=""></a>` : `<div class="studio-thumb">${icon(v.status === 'failed' ? 'flag' : 'play')}</div>`}
    <div class="studio-copy"><h2><a href="/watch/${enc(v.id)}" data-link>${esc(v.title)}</a></h2><span class="status ${v.status}">${esc(statusNames[v.status])}</span><span class="status">${icon(v.visibility === 'private' ? 'lock' : 'globe')}${v.visibility === 'private' ? 'Приватное' : 'Открытое'}</span>${v.hidden ? '<span class="status failed">Скрыто модератором</span>' : ''}<p class="row-note">${date(v.created_at)} · ${num(v.views)} просмотров · ${v.likes} отметок «Нравится»</p>${v.error ? `<p class="row-note error-note">${esc(v.error)}</p>` : ''}</div>
    <div class="studio-buttons"><button class="btn btn-neutral" data-action="edit-video" data-id="${enc(v.id)}">${icon('edit')}Изменить</button>${v.visibility === 'private' ? `<button class="btn btn-neutral" data-action="grants" data-id="${enc(v.id)}">${icon('lock')}Доступ</button>` : ''}${['failed', 'uploading'].includes(v.status) ? `<button class="btn btn-neutral" data-action="retry-upload" data-id="${enc(v.id)}">Загрузить файл</button>` : ''}<button class="icon-btn" data-action="delete-video" data-id="${enc(v.id)}" aria-label="Удалить видео">${icon('trash')}</button></div></article>`).join('') : empty('Снимите свою первую историю', 'Загрузите видео: оно появится здесь, а после обработки будет доступно для просмотра.', 'upload', '<a class="btn btn-blue" href="/upload" data-link>Загрузить видео</a>')}`;
}
async function moderationPage(token) {
  if (!session.user) return loginGate('Модерация');
  const r = await api('/moderation/reports');
  if (token !== generation) return null;
  return `<h1 class="page-heading">Модерация</h1><div class="notice">Проверяйте жалобы и скрывайте видео с нарушениями. Для просмотра приватного видео модератору тоже нужно разрешение владельца. Каждое решение сохраняется в журнале.</div>
    ${r.items.length ? r.items.map(r => `<article class="moderation-card"><h2>${r.video.can_view ? `<a href="/watch/${enc(r.video.id)}" data-link>${esc(r.video.title)}</a>` : `Приватное видео`}</h2><p><strong>Жалоба:</strong> ${esc(r.reason)}</p><p class="muted">От @${esc(r.reporter.handle)} · ${date(r.created_at)}</p><div class="moderation-actions">${r.video.can_view ? `<a class="btn btn-neutral" href="/watch/${enc(r.video.id)}" data-link>Посмотреть видео</a>` : `<span class="muted">Для просмотра нужно разрешение владельца</span>`}<button class="btn btn-danger" data-action="moderate" data-id="${enc(r.video.id)}" data-hidden="true">Скрыть видео</button><button class="btn btn-neutral" data-action="moderate" data-id="${enc(r.video.id)}" data-hidden="false">Оставить доступным</button></div></article>`).join('') : empty('Новых жалоб нет', 'Все поступившие жалобы рассмотрены. Новые обращения появятся здесь.', 'shield')}
    <hr class="divider"><h2 class="subheading">Восстановить видео</h2><form data-form="restore" class="panel"><label class="field"><span>Ссылка на видео или его ID</span><input name="video" required placeholder="Вставьте ссылку на скрытое видео"></label><label class="field"><span>Причина решения</span><input name="reason" required minlength="3" maxlength="500"></label><div class="form-error" role="alert"></div><button class="btn btn-neutral">Восстановить доступ</button></form>`;
}
async function adminPage(token) {
  if (!session.user) return loginGate('Управление пользователями');
  const r = await api('/admin/users');
  if (token !== generation) return null;
  return `<h1 class="page-heading">Пользователи</h1><p class="form-intro">Роли меняет только администратор. Последнего администратора нельзя лишить прав.</p>${r.items.map(u => `<div class="admin-row">${avatar(u)}<div><strong>${esc(u.name)}</strong><span class="muted">@${esc(u.handle)}</span></div><select aria-label="Роль ${esc(u.handle)}" data-role-user="${enc(u.id)}">${[['user', 'Пользователь'], ['moderator', 'Модератор'], ['admin', 'Администратор']].map(([value, label]) => `<option value="${value}" ${u.role === value ? 'selected' : ''}>${label}</option>`).join('')}</select></div>`).join('')}`;
}
async function renderRoute(showLoading = true) {
  const token = ++generation;
  clearTimeout(routeTimer);
  const main = document.querySelector('#content');
  if (!main) return;
  const path = location.pathname;
  main.classList.toggle('watch-page', path.startsWith('/watch/'));
  document.body.classList.toggle('compact', compact || path.startsWith('/watch/'));
  document.querySelectorAll('.nav-link').forEach(a => a.classList.toggle('active', a.getAttribute('href') === path));
  if (showLoading) main.innerHTML = skeleton();
  try {
    let html;
    if (['/', '/results', '/subscriptions', '/liked'].includes(path)) html = await feedPage(path, token);
    else if (path.startsWith('/watch/')) html = await watchPage(decodeURIComponent(path.split('/')[2]), token);
    else if (path.startsWith('/channel/')) html = await channelPage(decodeURIComponent(path.split('/')[2]), token);
    else if (path === '/upload') html = await uploadPage();
    else if (path === '/studio') html = await studioPage(token);
    else if (path === '/playlists') html = await playlistsPage(token);
    else if (path.startsWith('/playlist/')) html = await playlistPage(decodeURIComponent(path.split('/')[2]), token);
    else if (path === '/moderation') html = await moderationPage(token);
    else if (path === '/admin') html = await adminPage(token);
    else html = empty('Страница не найдена', 'Откройте главную страницу, чтобы найти интересное видео.', 'search', '<a class="btn btn-neutral" href="/" data-link>На главную</a>');
    if (token !== generation || html === null) return;
    main.innerHTML = html;
    setupUpload();
    const player = document.querySelector('#video-player');
    if (player) {
      player.addEventListener('error', () => toast('Видео недоступно. Обновите страницу или попробуйте позже'));
      player.addEventListener('play', () => api(`/videos/${enc(currentVideo.id)}/view`, { method: 'POST' }).catch(() => {}), { once: true });
    }
  } catch (error) {
    if (token === generation) main.innerHTML = empty(error.status === 404 ? 'Видео или страница недоступны' : 'Не удалось открыть страницу', error.message, 'lock', '<a class="btn btn-neutral" href="/" data-link>На главную</a>');
  }
}
function navigate(path, push = true) {
  if (uploadBusy) return toast('Дождитесь завершения загрузки');
  if (push) history.pushState({}, '', path);
  dialog.close();
  window.scrollTo({ top: 0 });
  return renderRoute();
}
function modal(title, body) {
  dialog.innerHTML = `<div class="dialog-inner"><div class="dialog-head"><h2 id="dialog-title">${esc(title)}</h2><button class="icon-btn" data-action="close-dialog" aria-label="Закрыть">${icon('close')}</button></div>${body}</div>`;
  if (!dialog.open) dialog.showModal();
}
function authModal(register = false) {
  modal(register ? 'Создать аккаунт' : 'Войти', `<p class="dialog-intro">${register ? 'Смотрите, создавайте и сохраняйте то, что вам нравится.' : 'Чтобы подписываться, оставлять комментарии и загружать видео.'}</p><form data-form="${register ? 'register' : 'login'}">
    ${register ? '<label class="field"><span>Название канала</span><input name="name" autocomplete="name" maxlength="80" required></label>' : ''}
    <label class="field"><span>Логин</span><input name="handle" autocomplete="username" pattern="[A-Za-z0-9_]{3,32}" minlength="3" maxlength="32" required>${register ? '<small>От 3 до 32 латинских букв, цифр или знаков подчёркивания</small>' : ''}</label>
    <label class="field"><span>Пароль</span><input name="password" type="password" autocomplete="${register ? 'new-password' : 'current-password'}" minlength="${register ? '10' : '1'}" maxlength="128" required>${register ? '<small>Не менее 10 символов</small>' : ''}</label>
    <div class="form-error" role="alert"></div><div class="form-footer"><button class="btn btn-blue">${register ? 'Создать аккаунт' : 'Войти'}</button></div></form><div class="auth-switch">${register ? 'Уже есть аккаунт?' : 'Нет аккаунта?'} <button data-action="${register ? 'login' : 'register'}">${register ? 'Войти' : 'Создать аккаунт'}</button></div>`);
}
function needLogin() { if (session.user) return false; authModal(); return true; }
function setupUpload() {
  const form = document.querySelector('#upload-form');
  if (!form) return;
  const input = form.elements.video, zone = document.querySelector('#dropzone');
  input.addEventListener('change', () => {
    const file = input.files[0];
    if (!file) return;
    document.querySelector('#file-label').textContent = file.name;
    if (!form.elements.title.value) form.elements.title.value = file.name.replace(/\.[^.]+$/, '').slice(0, 140);
  });
  for (const type of ['dragover', 'dragleave', 'drop']) zone.addEventListener(type, event => {
    event.preventDefault();
    zone.classList.toggle('drag', type === 'dragover');
    if (type === 'drop' && event.dataTransfer.files.length) {
      const transfer = new DataTransfer(); transfer.items.add(event.dataTransfer.files[0]);
      input.files = transfer.files; input.dispatchEvent(new Event('change'));
    }
  });
}
async function action(name, button) {
  const id = decodeURIComponent(button.dataset.id || '');
  if (name === 'menu') { compact = !compact; document.body.classList.toggle('compact', compact); }
  else if (name === 'login') authModal();
  else if (name === 'register') authModal(true);
  else if (name === 'close-dialog') dialog.close();
  else if (name === 'topic') { currentTopic = button.dataset.value; await renderRoute(); }
  else if (name === 'account') modal('Аккаунт', `<div class="account-info">${avatar(session.user)}<div><strong>${esc(session.user.name)}</strong><span class="muted">@${esc(session.user.handle)}</span></div></div><div class="account-menu"><a class="btn btn-neutral" href="/channel/${enc(session.user.handle)}" data-link>${icon('user')}Мой канал</a><a class="btn btn-neutral" href="/studio" data-link>${icon('studio')}Мои видео</a><a class="btn btn-neutral" href="/upload" data-link>${icon('upload')}Загрузить видео</a>${session.user.role !== 'user' ? '<a class="btn btn-neutral" href="/moderation" data-link>Модерация</a>' : ''}${session.user.role === 'admin' ? '<a class="btn btn-neutral" href="/admin" data-link>Пользователи</a>' : ''}<button class="btn" data-action="logout">${icon('logout')}Выйти</button></div>`);
  else if (name === 'logout') { await api('/auth/logout', { method: 'POST' }); await refreshSession(); dialog.close(); shell(); await renderRoute(); }
  else if (name === 'subscribe') {
    if (needLogin()) return;
    const subscribed = button.dataset.subscribed === 'true';
    const r = await api(`/channels/${button.dataset.handle}/subscription`, { method: subscribed ? 'DELETE' : 'PUT' });
    button.dataset.subscribed = String(r.subscribed); button.textContent = r.subscribed ? 'Вы подписаны' : 'Подписаться';
    button.classList.toggle('btn-neutral', r.subscribed); button.classList.toggle('btn-primary', !r.subscribed);
    const count = document.querySelector('#subscriber-count'); if (count) count.textContent = `${num(r.subscribers)} подписчиков`;
    toast(r.subscribed ? 'Подписка оформлена' : 'Подписка отменена');
  } else if (name === 'like') {
    if (needLogin()) return;
    const r = await api(`/videos/${enc(currentVideo.id)}/like`, { method: currentVideo.liked ? 'DELETE' : 'PUT' });
    currentVideo.liked = r.liked; button.setAttribute('aria-pressed', r.liked);
    button.querySelector('span').textContent = num(r.likes);
    button.style.color = r.liked ? '#065fd4' : '';
  } else if (name === 'description') { const target = document.querySelector('#description'); target.classList.toggle('expanded'); button.textContent = target.classList.contains('expanded') ? 'Свернуть' : 'Ещё'; }
  else if (name === 'share') {
    if (currentVideo.visibility === 'private') toast('Ссылка откроется только у зрителей, которым разрешил владелец');
    try { await navigator.clipboard.writeText(location.href); toast('Ссылка скопирована'); }
    catch { modal('Поделиться видео', `<label class="field"><span>Ссылка</span><input readonly value="${esc(location.href)}"></label>${currentVideo.visibility === 'private' ? '<p class="dialog-intro">Для просмотра потребуется разрешение владельца.</p>' : ''}`); }
  } else if (name === 'save') {
    if (needLogin()) return;
    const r = await api('/playlists');
    modal('Сохранить в плейлист', `<div class="account-menu">${r.items.map(p => `<button class="btn btn-neutral" data-action="save-to-playlist" data-id="${enc(p.id)}">${icon('list')}${esc(p.title)}</button>`).join('')}</div>${!r.items.length ? '<p class="dialog-intro">Сначала создайте плейлист.</p>' : ''}<hr class="divider"><button class="btn" data-action="new-playlist">${icon('plus')}Новый плейлист</button>`);
  } else if (name === 'save-to-playlist') { await api(`/playlists/${enc(id)}/videos/${enc(currentVideo.id)}`, { method: 'PUT' }); dialog.close(); toast('Видео добавлено в плейлист'); }
  else if (name === 'new-playlist') {
    if (needLogin()) return;
    modal('Новый плейлист', '<form data-form="new-playlist"><label class="field"><span>Название</span><input name="title" required maxlength="100"></label><label class="field"><span>Доступ</span><select name="visibility"><option value="public">Открытый</option><option value="private">Личный</option></select></label><div class="form-error" role="alert"></div><div class="form-footer"><button class="btn btn-blue">Создать</button></div></form>');
  } else if (name === 'report') {
    if (needLogin()) return;
    modal('Пожаловаться на видео', '<p class="dialog-intro">Жалобу рассмотрит модератор. Расскажите, какое нарушение вы заметили.</p><form data-form="report"><label class="field"><span>Причина жалобы</span><textarea name="reason" minlength="3" maxlength="500" required></textarea></label><div class="form-error" role="alert"></div><div class="form-footer"><button class="btn btn-blue">Отправить жалобу</button></div></form>');
  } else if (name === 'delete-comment') {
    await api(`/comments/${enc(id)}`, { method: 'DELETE' });
    currentComments = currentComments.filter(c => c.id !== id); document.querySelector('#comments-list').innerHTML = commentsHTML(currentComments);
    document.querySelector('#comments-count').textContent = Number(document.querySelector('#comments-count').textContent) - 1;
    toast('Комментарий удалён');
  } else if (name === 'edit-video') {
    const v = studioVideos.find(v => v.id === id);
    modal('Изменить видео', `<form data-form="edit-video" data-id="${enc(id)}"><label class="field"><span>Название</span><input name="title" value="${esc(v.title)}" maxlength="140" required></label><label class="field"><span>Описание</span><textarea name="description" maxlength="5000">${esc(v.description)}</textarea></label><label class="field"><span>Категория</span><input name="category" value="${esc(v.category)}" maxlength="40" required></label><label class="field"><span>Доступ</span><select name="visibility"><option value="public" ${v.visibility === 'public' ? 'selected' : ''}>Открытый</option><option value="private" ${v.visibility === 'private' ? 'selected' : ''}>Приватный</option></select></label><div class="form-error" role="alert"></div><div class="form-footer"><button class="btn btn-blue">Сохранить</button></div></form>`);
  } else if (name === 'grants') {
    const r = await api(`/videos/${enc(id)}/grants`);
    modal('Доступ к приватному видео', `<p class="dialog-intro">Укажите логины зарегистрированных зрителей через запятую. Удаление логина отзывает доступ. Доступ сохраняют владелец и указанные им зрители.</p><form data-form="grants" data-id="${enc(id)}"><label class="field"><span>Логины зрителей</span><textarea name="handles" placeholder="viewer, another_user">${esc(r.handles.join(', '))}</textarea></label><div class="form-error" role="alert"></div><div class="form-footer"><button class="btn btn-blue">Сохранить доступ</button></div></form>`);
  } else if (name === 'delete-video' || name === 'delete-playlist') {
    modal(name === 'delete-video' ? 'Удалить видео?' : 'Удалить плейлист?', `<p class="dialog-intro">${name === 'delete-video' ? 'Видео, комментарии и отметки будут удалены. Восстановить их не получится.' : 'Плейлист будет удалён. Сами видео останутся доступными.'}</p><form data-form="${name}" data-id="${enc(id)}"><div class="form-error" role="alert"></div><div class="form-footer"><button type="button" class="btn btn-neutral" data-action="close-dialog">Отмена</button><button class="btn btn-danger">Удалить</button></div></form>`);
  } else if (name === 'remove-playlist-video') { await api(`/playlists/${button.dataset.playlist}/videos/${enc(id)}`, { method: 'DELETE' }); await renderRoute(false); }
  else if (name === 'retry-upload') modal('Загрузить файл повторно', `<form data-form="retry-upload" data-id="${enc(id)}"><label class="field"><span>Видео</span><input type="file" name="video" accept="video/*" required></label><div id="retry-status"></div><div class="form-error" role="alert"></div><div class="form-footer"><button class="btn btn-blue">Загрузить</button></div></form>`);
  else if (name === 'edit-channel') modal('Настроить канал', `<form data-form="edit-channel"><label class="field"><span>Название канала</span><input name="name" value="${esc(session.user.name)}" maxlength="80" required></label><label class="field"><span>Описание канала</span><textarea name="description" maxlength="2000">${esc(session.user.description)}</textarea></label><div class="form-error" role="alert"></div><div class="form-footer"><button class="btn btn-blue">Сохранить</button></div></form>`);
  else if (name === 'moderate') modal(button.dataset.hidden === 'true' ? 'Скрыть видео' : 'Оставить доступным', `<form data-form="moderate" data-id="${enc(id)}" data-hidden="${button.dataset.hidden}"><label class="field"><span>Причина решения</span><textarea name="reason" minlength="3" maxlength="500" required></textarea></label><div class="form-error" role="alert"></div><div class="form-footer"><button class="btn btn-blue">Сохранить решение</button></div></form>`);
  else if (name === 'more-videos') {
    const offset = Number(button.dataset.offset);
    const r = await api(`${button.dataset.endpoint}&offset=${offset}`);
    document.querySelector('#video-list').insertAdjacentHTML('beforeend', r.items.map(card).join(''));
    button.dataset.offset = offset + 24;
    if (!r.has_more) button.parentElement.remove();
  }
}
async function submitForm(form) {
  const name = form.dataset.form, values = Object.fromEntries(new FormData(form));
  const id = decodeURIComponent(form.dataset.id || '');
  const errorBox = form.querySelector('.form-error'); if (errorBox) errorBox.textContent = '';
  const submit = form.querySelector('button[type="submit"],button:not([type])');
  if (submit) submit.disabled = true;
  try {
    if (name === 'login' || name === 'register') {
      const r = await api(`/auth/${name}`, { method: 'POST', data: values });
      session.user = r.user; session.csrf = r.csrf_token; dialog.close(); shell(); await renderRoute();
      toast(name === 'register' ? 'Аккаунт создан. Добро пожаловать!' : 'Вы вошли в аккаунт');
    } else if (name === 'comment') {
      const r = await api(`/videos/${enc(currentVideo.id)}/comments`, { method: 'POST', data: values });
      currentComments.unshift(r); document.querySelector('#comments-list').innerHTML = commentsHTML(currentComments);
      document.querySelector('#comments-count').textContent = Number(document.querySelector('#comments-count').textContent) + 1;
      form.reset(); toast('Комментарий добавлен');
    } else if (name === 'upload' || name === 'retry-upload') {
      const file = form.elements.video.files[0];
      if (!file) throw new Error('Выберите видеофайл');
      const config = await api('/config');
      if (file.size === 0 || file.size > config.max_upload_bytes) throw new Error(`Выберите непустой файл до ${Math.round(config.max_upload_bytes / 1048576)} МБ`);
      const v = name === 'upload' ? await api('/videos', { method: 'POST', data: { title: values.title, description: values.description, category: values.category, visibility: values.visibility } }) : { id };
      const target = document.querySelector(name === 'upload' ? '#upload-status' : '#retry-status');
      target.innerHTML = '<div class="upload-progress"><strong>Загрузка файла · <span id="progress-number">0%</span></strong><progress max="100" value="0" aria-label="Прогресс загрузки"></progress><p>Не закрывайте страницу до завершения загрузки.</p></div>';
      uploadBusy = true;
      try { await uploadSource(v.id, file, progress => { document.querySelector('#progress-number').textContent = `${progress}%`; target.querySelector('progress').value = progress; }); }
      finally { uploadBusy = false; }
      toast('Файл загружен. Готовим видео к просмотру'); await navigate('/studio');
    } else if (name === 'new-playlist') { const r = await api('/playlists', { method: 'POST', data: values }); dialog.close(); toast('Плейлист создан'); if (location.pathname.startsWith('/watch/') && currentVideo) { await api(`/playlists/${enc(r.id)}/videos/${enc(currentVideo.id)}`, { method: 'PUT' }); toast('Плейлист создан, видео добавлено'); } else await navigate(`/playlist/${enc(r.id)}`); }
    else if (name === 'report') { await api(`/videos/${enc(currentVideo.id)}/reports`, { method: 'POST', data: values }); dialog.close(); toast('Жалоба отправлена модератору'); }
    else if (name === 'edit-video') { await api(`/videos/${enc(id)}`, { method: 'PATCH', data: values }); dialog.close(); await renderRoute(false); toast('Изменения сохранены'); }
    else if (name === 'grants') { await api(`/videos/${enc(id)}/grants`, { method: 'PUT', data: { handles: values.handles.split(/[,\n]/).map(x => x.trim()).filter(Boolean) } }); dialog.close(); toast('Доступ обновлён'); }
    else if (name === 'delete-video') { await api(`/videos/${enc(id)}`, { method: 'DELETE' }); dialog.close(); await renderRoute(false); toast('Видео удалено'); }
    else if (name === 'delete-playlist') { await api(`/playlists/${enc(id)}`, { method: 'DELETE' }); dialog.close(); await navigate('/playlists'); toast('Плейлист удалён'); }
    else if (name === 'edit-channel') { await api('/channel', { method: 'PATCH', data: values }); await refreshSession(); dialog.close(); shell(); await renderRoute(); toast('Канал обновлён'); }
    else if (name === 'moderate' || name === 'restore') {
      const videoId = name === 'restore' ? values.video.split('/').filter(Boolean).pop().split('?')[0] : id;
      await api(`/moderation/videos/${enc(videoId)}`, { method: 'PUT', data: { hidden: name === 'moderate' && form.dataset.hidden === 'true', reason: values.reason } });
      dialog.close(); await renderRoute(false); toast('Решение сохранено');
    }
  } catch (error) { if (errorBox?.isConnected) errorBox.textContent = error.message; else toast(error.message); }
  finally { if (submit?.isConnected) submit.disabled = false; }
}
document.addEventListener('click', async event => {
  const link = event.target.closest('a[data-link]');
  if (link && event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey) { event.preventDefault(); await navigate(link.getAttribute('href')); return; }
  const button = event.target.closest('[data-action]');
  if (!button || button.disabled) return;
  try { button.disabled = true; await action(button.dataset.action, button); }
  catch (error) { toast(error.message); }
  finally { if (button.isConnected) button.disabled = false; }
});
document.addEventListener('submit', async event => {
  if (event.target.id === 'search-form') { event.preventDefault(); const q = event.target.elements.q.value.trim(); await navigate(q ? `/results?search_query=${enc(q)}` : '/'); }
  else if (event.target.matches('[data-form]')) { event.preventDefault(); await submitForm(event.target); }
});
document.addEventListener('change', async event => {
  if (!event.target.matches('[data-role-user]')) return;
  const select = event.target; select.disabled = true;
  try { await api(`/admin/users/${select.dataset.roleUser}/role`, { method: 'PUT', data: { role: select.value } }); await refreshSession(); toast('Роль обновлена'); }
  catch (error) { toast(error.message); await renderRoute(false); }
  finally { if (select.isConnected) select.disabled = false; }
});
window.addEventListener('popstate', () => renderRoute());
window.addEventListener('beforeunload', event => { if (uploadBusy) { event.preventDefault(); event.returnValue = ''; } });
dialog.addEventListener('click', event => { if (event.target === dialog && !uploadBusy) dialog.close(); });
dialog.addEventListener('cancel', event => { if (uploadBusy) event.preventDefault(); });
try { await refreshSession(); } catch { /* Show usable shell and a page-level connection error. */ }
shell();
await renderRoute();
