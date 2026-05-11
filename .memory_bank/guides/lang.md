# Правила языка

В проекте две зоны с разными правилами.

## Документация — РУССКИЙ

Всё что читает человек — на русском.

✅ Русский:
- README, CLAUDE.md, всё в `.memory_bank/`
- Комментарии в коде
- Docstrings функций
- Commit-сообщения
- Названия инлайн-кнопок в боте
- Сообщения от бота пользователю
- Тексты ошибок если их видит пользователь

## Код — АНГЛИЙСКИЙ

Всё что читает компилятор / интерпретатор — на английском.

✅ Английский:
- Имена переменных: `scene_url`, `target_class`, `pipeline_result`
- Имена функций: `check_scene_quality`, `process_user_request`
- Имена файлов: `bot.py`, `pipeline.py`, `quality_check.py`
- Имена папок: `ai/`, `bot/`, `utils/`
- Команды Git, Docker, shell
- Переменные окружения: `TG_BOT_TOKEN`, `OPENAI_BASE_URL`
- Технические термины без устоявшегося русского аналога: API, JSON, async, FSM

## Смешанные случаи

**Docstring**:
```python
async def check_scene_quality(image_url: str) -> dict:
    """Проверка качества фото сцены через GPT-5.4 Mini vision.

    Args:
        image_url: публичный URL фото на 0x0.st

    Returns:
        dict с полями recommendation, user_message, issues, ...
    """
```
Текст описания — русский. Имя функции, параметров, тип возврата — английский.

**Лог-сообщения**:
```python
logger.info("Pipeline started for user %d", user_id)
logger.error("Quality check failed: %s", exc)
```
Логи — на английском (читаем мы, не пользователи; стандартная практика).

**Сообщение боту пользователю**:
```python
await message.answer("⚠️ Фото получилось тёмное. Можем продолжить, но качество может пострадать.")
```
Текст — русский.

## Если устоявшийся английский термин

Если в индустрии чаще говорят "API endpoint" чем "конечная точка API" — оставляем "API endpoint". Принцип: используем то, что **быстрее распознаётся** при чтении.

✅ оставляем: API, JSON, JWT, OAuth, async, await, callback, webhook, polling, container, image (docker), stage (в pipeline), prompt
✅ переводим: rate limit → лимит частоты, response → ответ, request → запрос (когда термин из контекста ясен)

## Антипаттерны

❌ Русское описание + English title в одном файле:
```markdown
## Authentication flow

Аутентификация работает так...
```
Либо весь заголовок русский, либо весь английский. Не смешивать.

❌ Транслит: "Сделай post_request к sajdu API endpoint'у" → "Сделай POST-запрос к API"

❌ Полу-русские имена: `proverit_kachestvo()` → `check_quality()`

## Для общения с пользователем (не разработчик)

В чате с пользователем — всё на русском, **включая** технические термины. Если использую "Docker" или "API" — даю пояснение в скобках.

Это исключение из правил выше — потому что собеседник не разработчик. См. `auto-memory feedback_simple_language.md`.
