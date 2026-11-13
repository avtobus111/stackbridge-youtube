# Сверка с исходным заданием

Основание: [исходное ТЗ](requirements.txt). Таблица связывает требования с реализацией и способами проверки; она не заменяет фактические результаты в [verification.md](verification.md).

| Требование | Реализация | Подтверждение |
| --- | --- | --- |
| Главная: лента и превью | `frontend/app.js`, `GET /api/videos` | `tests/test_frontend.py`, браузерные сценарии и скриншоты |
| Просмотр: плеер, лайки, комментарии | Авторизованная выдача MP4/Range, HTML5-плеер, social API | `tests/test_pipeline.py`, `test_ranges.py`, `test_social.py`; реальный HTTP smoke |
| Канал: видео, плейлисты, подписка | `/api/channels/{handle}`, playlist/subscription API и экран канала | `tests/test_access.py`, `test_social.py`; браузерный сценарий |
| Поиск по названию | Параметр `q` у `/api/videos`, экранирование поисковых wildcard | `tests/test_access.py`, браузерный поиск |
| Загрузка: файл, прогресс, metadata | XHR с настоящим прогрессом, бинарный PUT, отдельный FFmpeg worker, студия | `tests/test_pipeline.py`, `test_recovery_races.py`; browser/API upload → playback |
| Вход и регистрация | Сессии в БД, scrypt, HttpOnly cookie, CSRF/Origin и throttling | `tests/test_auth.py`, `test_social.py` |
| Жалобы и скрытие видео | Экран модерации, изменение видимости, журнал решений | `tests/test_access.py`, `test_staff_privacy.py` |
| User/moderator/admin | Серверная проверка роли, защита последнего администратора | `tests/test_access.py`, запрет role injection в `test_auth.py` |
| Приватное видео только с разрешения владельца | Общая политика для выдачи, metadata, поиска, каналов, плейлистов, Range и обложек; действует и для staff | `tests/test_access.py`, `test_staff_privacy.py`, `test_social.py`; выдача/отзыв grants в real-stack smoke |
| Загрузка, хранение и раздача настоящего видео | Закрытый S3, очередь PostgreSQL, отдельный FFmpeg worker; браузер получает файл через API | `scripts/smoke.py`, `scripts/check_storage.py`, тесты pipeline/ranges/recovery |
| Python + FastAPI, PostgreSQL, Swagger | `backend/`, `migrations/`, локальный Swagger `/docs` | Полный набор тестов на настоящей PostgreSQL; браузерный `/docs` |
| Ubuntu: одна команда | `sudo bash start.sh`, Docker/Compose, init/migration/seed, web/worker/db/storage | Реальная Ubuntu 24.04: установщик Docker, запуск, пустые тома и повторный запуск; точная последовательность в `verification.md` |
| Демо: пользователи, видео, комментарии | Повторяемый `backend/seed.py`, 12 локальных фотоэтюдов и шесть каналов | `tests/test_seed.py`, заполнение настоящей Ubuntu БД; источники в [asset-credits.md](asset-credits.md) |
| README, docs, критичные автотесты | Инструкции запуска/проверки, архитектура/API/эксплуатация/безопасность | [README](../README.md), [architecture](architecture.md), [operations](operations.md), [security](security.md), `tests/` |
| Схема и связи БД | SQLAlchemy models, ограничения/индексы, начальная миграция Alembic | [architecture.md](architecture.md), `backend/models.py`, `migrations/versions/` |
| Осмысленная история Git целиком | Локальная ветка с отдельными этапами и исправлениями, ZIP включает `.git` | `scripts/package.py`; распаковка, `git fsck --full` и чистый working tree |
| Реальные материалы работы с ИИ | Проектные `AGENTS.md`, исходные снимки прочитанных скиллов, манифест хешей, фактическое ревью | [ai/README.md](../ai/README.md), `ai/skills/`, `ai/skills-manifest.json`, `ai/review-invocation.json` |
| Нативные диалоги в общем ZIP | **Пока отдельно по прямому решению пользователя:** полный оригинал основного чата и ревью, без редактирования | `scripts/export_ai.py`; отдельный `AI_ORIGINALS_REVIEW_ONLY.zip`. Включение в сдачу ждёт личной проверки пользователя |

Новые функции сверх указанного состава не считаются обязательными: HLS, live streaming, промышленная рекомендательная система, email recovery и распределённая отказоустойчивость не реализованы. Оценка сходства с YouTube остаётся визуальной оценкой интерфейса; наличие перечисленных экранов не доказывает полное соответствие всему продукту YouTube.

Публикация, отправка задания и включение непроверенных оригиналов не выполняются автоматически.
