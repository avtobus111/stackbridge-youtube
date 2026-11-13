# API

Интерактивная спецификация — `/docs`, машинная — `/openapi.json`. UI, API и media находятся на одном origin. Формат запросов — JSON, кроме бинарной загрузки source.

## Авторизация

POST `/api/auth/register` принимает `handle`, `name`, `password`; POST `/api/auth/login` — `handle`, `password`. Ответ содержит безопасное представление user и csrf_token; session устанавливается HttpOnly cookie. GET `/api/auth/me` возвращает текущего пользователя и CSRF. Для изменяющих действий отправляйте cookie и `X-CSRF-Token`. POST `/api/auth/logout` отзывает сессию.

```python
import requests
s = requests.Session()
r = s.post('http://localhost:8000/api/auth/login', json={'handle': 'viewer', 'password': DEMO_PASSWORD})
r.raise_for_status()
s.headers['X-CSRF-Token'] = r.json()['csrf_token']
```

## Маршруты

| Метод и путь | Назначение |
| --- | --- |
| GET `/api/config` | Открытые лимиты размера/длительности, без секретов |
| GET `/api/videos?q=&category=&feed=&offset=&limit=` | Поиск/лента; feed=subscriptions или liked требует входа |
| POST `/api/videos` | Создать metadata: title, description, category, visibility |
| PUT `/api/videos/{id}/source` | Передать тело файла; Content-Type: application/octet-stream; ответ 202 |
| GET `/api/videos/{id}` | Детали и состояние: uploading, receiving, queued, processing, ready, failed |
| PATCH `/api/videos/{id}` | Владелец задаёт полный набор metadata; title обязателен |
| DELETE `/api/videos/{id}` | Владелец удаляет видео и объекты; активную обработку сначала нужно дождаться |
| GET/HEAD `/api/videos/{id}/media` | Авторизованный MP4; один Range, включая suffix |
| GET/HEAD `/api/videos/{id}/thumbnail` | Авторизованная JPEG-обложка |
| GET/PUT `/api/videos/{id}/grants` | Только владелец; PUT принимает handles, заменяет весь список атомарно |
| POST `/api/videos/{id}/view` | Учёт одного просмотра на пользователя/анонимный visitor-cookie |
| GET `/api/studio` | До 100 последних собственных видео, включая необработанные |
| GET `/api/channels/{handle}` | Канал, доступные видео, открытые/свои плейлисты и счётчик подписчиков |
| PATCH `/api/channel` | Изменить название и описание своего канала |
| PUT/DELETE `/api/channels/{handle}/subscription` | Подписка/отмена; PUT идемпотентен |
| GET `/api/subscriptions` | Собственные подписки |
| PUT/DELETE `/api/videos/{id}/like` | Лайк/отмена; PUT идемпотентен |
| GET/POST `/api/videos/{id}/comments` | Комментарии и добавление непустого текста до 2000 символов |
| DELETE `/api/comments/{id}` | Свой комментарий или удаление сотрудником модерации |
| GET/POST `/api/playlists` | Собственные плейлисты / создание |
| GET/DELETE `/api/playlists/{id}` | Просмотр с фильтрацией входящих видео / удаление владельцем |
| PUT/DELETE `/api/playlists/{id}/videos/{video_id}` | Добавление/удаление владельцем; PUT идемпотентен |
| POST `/api/videos/{id}/reports` | Жалоба доступного зрителю видео; один report на пару user/video |
| GET `/api/moderation/reports` | Открытые жалобы для moderator/admin |
| PUT `/api/moderation/videos/{id}` | Скрыть/восстановить: hidden, reason; закрывает жалобы и пишет audit |
| GET `/api/admin/users?q=` | До 100 аккаунтов, только admin |
| PUT `/api/admin/users/{id}/role` | Смена роли, только admin; последний администратор защищён |
| GET `/healthz` | Готовность БД и bucket |

Общие ответы: 401 — требуется вход; 403 — недостаточно прав/CSRF; 404 — отсутствует или недоступно; 409 — конфликт состояния; 413 — размер; 416 — диапазон; 422 — данные; 429 — ограничение частоты; 503 — временная проблема хранилища. Подробности в JSON `detail`. Ошибка формата видео обнаруживается фоновым обработчиком и отображается как status=failed, а не как успешная публикация.

Пример полного сценария с проверкой приватности: `scripts/smoke.py`. Реальные HTTP-запросы UI находятся в `frontend/api.js` и `frontend/app.js`.
