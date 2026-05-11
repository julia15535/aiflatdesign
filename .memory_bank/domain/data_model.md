# Domain: Data model (SQLite)

База — один файл `data/prototype.db`. Используем встроенный `sqlite3`, без ORM.

## Таблицы

### users

| Поле | Тип | Описание |
|---|---|---|
| `tg_user_id` | INTEGER PRIMARY KEY | Telegram ID пользователя |
| `username` | TEXT | Telegram @username (может быть NULL) |
| `onboarded` | BOOLEAN DEFAULT FALSE | Прошёл ли туториал |
| `first_seen` | TIMESTAMP | UTC, первое появление |
| `last_seen` | TIMESTAMP | UTC, обновляется при каждом действии |
| `total_generations` | INTEGER DEFAULT 0 | Счётчик успешных генераций (для лимита 5/день) |

### sessions

| Поле | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `tg_user_id` | INTEGER | FK на users (без CASCADE для истории) |
| `scene_url` | TEXT | URL фото комнаты в 0x0.st |
| `product_url` | TEXT | URL фото товара |
| `target_class` | TEXT | sofa / armchair / bed / ... |
| `room_dims_m` | TEXT (JSON) | `[5, 4]` или NULL |
| `product_dims_cm` | TEXT (JSON) | `[220, 90, 85]` или NULL |
| `scene_quality_json` | TEXT (JSON) | Полный ответ QC сцены |
| `product_quality_json` | TEXT (JSON) | Полный ответ QC товара |
| `scene_analysis_json` | TEXT (JSON) | Полный ответ Stage 1 |
| `created_at` | TIMESTAMP | UTC |

### generations

| Поле | Тип | Описание |
|---|---|---|
| `id` | INTEGER PK AUTOINCREMENT | |
| `session_id` | INTEGER | FK на sessions |
| `success` | BOOLEAN | true/false из pipeline |
| `error_type` | TEXT | `scene_rejected` / `size_mismatch` / `all_seeds_failed` / etc |
| `result_url` | TEXT | URL итоговой картинки (NULL если fail) |
| `variants_json` | TEXT (JSON) | список URL топ-3 |
| `validation_json` | TEXT (JSON) | `{wow_score, catalog_sim, ...}` |
| `size_check_json` | TEXT (JSON) | `{fits, max_deviation, verdict, ...}` |
| `wow_score` | REAL | Дублируется для удобства аналитики |
| `cost_usd` | REAL | Накопленная стоимость flow'а |
| `duration_sec` | INTEGER | Сколько секунд занял pipeline |
| `user_rating` | TEXT | NULL / `good` / `mid` / `bad` |
| `user_note` | TEXT | Свободная заметка от пользователя |
| `created_at` | TIMESTAMP | UTC |

## Запросы для аналитики

```sql
-- WOW распределение
SELECT
    CASE
        WHEN wow_score >= 4 THEN '4+'
        WHEN wow_score >= 3 THEN '3-4'
        WHEN wow_score >= 2 THEN '2-3'
        ELSE '<2'
    END as wow_bucket,
    COUNT(*) as cnt
FROM generations
WHERE success = 1
GROUP BY wow_bucket;

-- Success rate по target_class
SELECT
    s.target_class,
    SUM(g.success) * 100.0 / COUNT(*) as success_pct,
    COUNT(*) as total
FROM sessions s
JOIN generations g ON g.session_id = s.id
GROUP BY s.target_class;

-- Failure breakdown
SELECT error_type, COUNT(*) FROM generations WHERE success = 0 GROUP BY error_type;

-- Cost per success
SELECT AVG(cost_usd) FROM generations WHERE success = 1;

-- User feedback (rating coverage)
SELECT user_rating, COUNT(*) FROM generations WHERE user_rating IS NOT NULL GROUP BY user_rating;
```

## Лимит 5 регенераций / день

```sql
SELECT COUNT(*)
FROM generations g
JOIN sessions s ON s.id = g.session_id
WHERE s.tg_user_id = ?
  AND g.created_at >= datetime('now', '-24 hours');
```

Если ≥ 5 — отказываем с "Лимит 5 генераций в сутки исчерпан, возвращайтесь завтра".

## Изоляция между запусками

При повторном `init_db()` — `CREATE TABLE IF NOT EXISTS` оставляет данные. Если нужно сбросить — удалить `data/prototype.db`. В тестах используем `data/prototype_test.db`.

## Не храним

- ❌ Содержимое картинок — только URL'ы (0x0.st сам подчищает через час).
- ❌ FSM state — он в памяти.
- ❌ Полные ответы Replicate — только то что вошло в validation_json и result_url.

## Бэкап

В прод: ежедневный `sqlite3 .backup` через cron → выгрузка на S3-совместимое (или копия в `/opt/backups/`). На MVP — не делаем, файл в Docker volume и достаточно.
