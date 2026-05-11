# Архитектурные решения

Все важные "почему" в одном месте.

## 2026-05-11: Стек MVP

**Решение**: Python 3.11+, aiogram 3, openai SDK ≥1.50, replicate SDK, SQLite. Без Postgres, без Redis, без webhook.

**Альтернативы**:
- Webhook вместо long polling — нужен nginx-конфиг, SSL, public IP, лишняя сложность для MVP
- Postgres вместо SQLite — для 30-50 beta-тестов это overkill
- Claude Sonnet vision вместо GPT-5.4 Mini — в 1.4× дороже, JSON mode хуже

**Trade-off**: ограничены аккуратной 1-инстанс архитектурой (FSM в памяти, SQLite single-file). После 1000+ пользователей переезжаем.

**Триггер пересмотра**: >100 одновременных пользователей или WAL contention в SQLite.

## 2026-05-11: GPT-5.4 Mini для всех vision-задач

**Решение**: `OPENAI_VISION_MODEL=gpt-5.4-mini`.

**Альтернативы**:
- GPT-5.4 Nano для quality check (опция через `OPENAI_QUALITY_CHECK_MODEL`) — экономит ~$0.003/flow, точность ниже
- Claude Sonnet — 1.4× дороже, но потенциально точнее на сложных сценах
- GPT-4o — 3× дороже Mini

**Trade-off**: за $0.21/flow получаем full pipeline (quality + scene + description). Если ужать на Nano для QC — $0.20/flow, но больше ложных reject'ов.

**Триггер**: если в бенчмарке QC reject rate > 25% от реально хороших фото — переключаемся обратно на Mini для QC.

## 2026-05-11: 3 seeds на FLUX Fill Pro (best-of-N)

**Решение**: `n_seeds=3` через asyncio.gather, выбор лучшего по WOW score.

**Альтернативы**:
- 1 seed — экономия $0.10/flow, но variance большой (1 из 3 fail = 33% failure rate)
- 5 seeds — экономия времени минимальная, +$0.10/flow

**Trade-off**: $0.15 на генерацию × 3 = $0.45, но best-of-3 даёт ~75% success vs ~50% solo.

**Триггер пересмотра**: если на бенчмарке best-pick = seed[0] чаще 70% случаев — снизить до 2.

## 2026-05-11: 0x0.st для temporary image hosting

**Решение**: загружаем картинки на 0x0.st (anonymous, 1 час TTL), передаём URL в OpenAI/Replicate.

**Альтернативы**:
- Cloudflare R2 — нужен setup, $5/мес минимум
- ImgBB — лимит, требует API key
- base64 в OpenAI запросе — медленнее, дороже по tokens

**Trade-off**: бесплатно, без setup'а; зависим от стабильности 0x0.st. Если упадёт — fallback на ImgBB через env var `IMAGE_HOST_FALLBACK`.

**Триггер**: 0x0.st rate-limit'нул или умер → переключаемся на imgbb с API key.

## 2026-05-11: Деплой в Docker на 193.160.208.41

**Решение**: отдельный docker-compose в `/opt/aiflatdesigner/`, отдельная network `aiflatdesigner-net`, non-root user, без port mapping (long polling).

**Альтернативы**:
- systemd unit с venv — проще, но грязнее (deps смешиваются с системными)
- Отдельный VPS — $5-10/мес, чище, но нужно дополнительно настраивать SSH/мониторинг

**Trade-off**: переиспользуем существующую инфраструктуру; рискуем диском (88% занято).

**Триггер**: если упрёмся в `no space left on device` → выносим на отдельный VPS.

## 2026-05-11: FSM в MemoryStorage (без Redis)

**Решение**: aiogram MemoryStorage для FSM.

**Альтернативы**: RedisStorage — переживает рестарт бота, требует Redis-контейнер.

**Trade-off**: рестарт = пользователи теряют прогресс flow'а. Учитывая что pipeline идёт ~3 минуты и юзеры обычно не делают паузу на 10+ минут — приемлемо.

**Триггер**: если на бенчмарке частые рестарты бота из-за крашей — добавить Redis.

## 2026-05-11: Отказ от Replicate в пользу OpenAI gpt-image-2

**Решение**: Генерация финального фото идёт через **один вызов** OpenAI `images.edit` с моделью `gpt-image-2`. Передаём фото комнаты + фото товара (массив, до 16 reference) + текстовый промпт + `input_fidelity="high"`. Replicate целиком убран из активного pipeline.

**Альтернативы**:
- Replicate FLUX Fill Pro + GroundedSAM (для маски) + CLIP (для validation) + Grounding DINO (для presence) + Clarity Upscaler (5 этапов, $0.21/flow, ~75 секунд)
- Stable Diffusion XL Inpainting через Replicate (дешевле FLUX, но хуже качество)

**Trade-off**:
- Плюс: pipeline 5 этапов → 3, цена $0.21 → $0.033, время 75с → 20-30с, кода в 3 раза меньше
- Плюс: единый провайдер (OpenAI), один SDK
- Плюс: gpt-image-2 умеет хранить визуал товара через `input_fidelity="high"` — пользователь подтвердил по веб-интерфейсу
- Минус: зависимость от одного провайдера — если OpenAI ломается, встаём целиком
- Минус: меньше контроля над промежуточными шагами (всё в чёрной коробке)
- Минус: если `input_fidelity="high"` недостаточно — нет тонкого инструмента подкрутки

**Триггер пересмотра**: если в Шаге 5 (бенчмарк на 20-30 кейсах) у >50% результатов товар не узнаваем (catalog_sim < 0.7 на глаз) — возвращаем Replicate FLUX Fill Pro как fallback или основной путь.

**Текущее состояние Replicate в проекте**: SDK замёрз в `pyproject.toml` (на всякий случай), модули `ai/replicate.md` помечены архивом, заметки про FLUX остаются для возможного возврата.

---

## 2026-05-11: Не используем webhook

**Решение**: long polling.

**Альтернативы**: webhook через HTTPS endpoint на сервере.

**Trade-off**: long polling 1 RPS на бот (ничего страшного), simple. Webhook сложнее: нужен nginx, SSL cert, public IP, certificate refresh.

**Триггер**: >1000 пользователей одновременно — переходим на webhook (он эффективнее по latency).
