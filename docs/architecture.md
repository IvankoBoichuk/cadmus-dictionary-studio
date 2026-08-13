# Cadmus Dictionary Studio — архітектура MVP

Статус: **Accepted**  
Jira: **BH-175**  
Дата: **2026-08-13**

## 1. Мета документа

Документ фіксує межі першої версії Cadmus Dictionary Studio, відповідальність компонентів і дозволені залежності. Cadmus перетворює цифрові копії друкованих словників на структуровані лексикографічні записи зі збереженням зв'язку з першоджерелом і ручною перевіркою результату.

Архітектура першої версії — **модульний моноліт із окремим фоновим worker-процесом**. API та предметні модулі розміщуються в одному backend-коді й одній транзакційній базі, а довгі операції виконуються через чергу.

## 2. Межі MVP

### 2.1. Обов'язковий наскрізний сценарій

1. Користувач реєструється та входить у систему.
2. Створює проєкт словника й заповнює основні метадані та правовий статус.
3. Завантажує PDF і вибирає діапазон сторінок.
4. Система перетворює PDF на сторінкові зображення.
5. Користувач запускає OCR для вибраних сторінок.
6. Worker виконує preprocessing та OCR, зберігаючи текст, координати й confidence.
7. Інтерфейс накладає OCR-області на скан.
8. Система пропонує межі словникової статті та поля `headword`, `part_of_speech`, `definition`, `example`.
9. Редактор підтверджує або виправляє результат, не змінюючи оригінальний OCR-шар.
10. Перевірені записи експортуються щонайменше у JSON.

### 2.2. Функції MVP

- email/password authentication;
- один власник або редактор проєкту з базовим контролем доступу;
- PDF upload із перевіркою MIME, розміру та checksum;
- метадані й правовий статус джерела;
- конвертація PDF у сторінкові зображення;
- асинхронний, повторюваний pipeline;
- Tesseract як перший OCR-провайдер через спільний інтерфейс;
- OCR-токени, bounding boxes, confidence та сирий результат;
- базовий preprocessing зі збереженням перетворення координат;
- перегляд скану з OCR overlay;
- ручне виділення і редагування статей;
- baseline-сегментація статей і чотирьох типів полів;
- `source_text` окремо від `normalized_text`;
- provenance для структурованих полів;
- Human-in-the-Loop статуси перевірки;
- JSON export;
- базові метрики тривалості й помилок pipeline.

### 2.3. Out of scope першої версії

- Kubernetes, мікросервіси, Kafka та service mesh;
- real-time collaborative editing;
- автоматичне донавчання моделей та active learning loop;
- підтримка всіх типів словникових полів;
- семантичний пошук, embeddings, RAG і knowledge graph;
- автоматична нормалізація історичного правопису без підтвердження;
- повноцінний crowdsourcing і publisher workflow;
- нативні мобільні застосунки;
- on-premise інсталяційний продукт;
- гарантії production-scale високої доступності;
- білінг;
- TEI Lex-0 як блокувальна вимога першого наскрізного інкременту (архітектура має дозволяти додати його без зміни доменної моделі).

## 3. Контекст системи

```mermaid
flowchart LR
    User["Дослідник / редактор"] --> Web["React web client"]
    Web --> API["FastAPI modular monolith"]
    API --> DB[(PostgreSQL)]
    API --> Files[(S3-compatible storage)]
    API --> Queue[(Redis queue)]
    Queue --> Worker["Pipeline worker"]
    Worker --> DB
    Worker --> Files
```

Web-клієнт не звертається напряму до БД, Redis або файлового сховища. Worker не є окремою предметною системою: він запускає application use cases з того самого backend-коду.

## 4. Компоненти розгортання

| Компонент | Відповідальність | Технологічна основа |
|---|---|---|
| `web` | UI, OCR overlay, редактор, статуси задач | React, TypeScript, Vite |
| `api` | HTTP API, auth, use cases, транзакції, постановка jobs | Python 3.12, FastAPI |
| `worker` | preprocessing, OCR, layout/extraction, exports | Python, Celery або RQ |
| `postgres` | транзакційне ядро, JSONB, provenance, audit | PostgreSQL |
| `redis` | broker і короткочасний стан черги | Redis |
| `object-storage` | PDF, зображення сторінок, артефакти pipeline | MinIO локально, S3-compatible у production |

Усі компоненти локально запускаються Docker Compose. API і worker збираються з одного backend source tree, але запускаються різними процесами.

## 5. Bounded modules

| Модуль | Володіє | Не відповідає за |
|---|---|---|
| `identity` | користувачі, credentials, sessions, ролі | словники та OCR |
| `projects` | проєкти словників, членство й доступ | файли та pipeline |
| `sources` | джерела, метадані, правовий статус, файли, сторінки | OCR-семантику |
| `processing` | processing run, етапи, статуси, конфігурації, retries | реалізацію конкретного OCR engine |
| `document` | normalized page geometry, blocks, lines, tokens, reading order | лексикографічні значення |
| `lexicography` | entries, fields, senses, source/normalized text | запуск pipeline |
| `review` | annotations, validation status, corrections, audit trail | автоматичне розпізнавання |
| `exports` | snapshots та serializers JSON/TEI | редагування записів |
| `quality` | gold samples, measurements, run statistics | production decisions без експериментів |

## 6. Правило залежностей

Залежності спрямовані всередину: transport та infrastructure залежать від application/domain, але domain не імпортує FastAPI, Celery, SQLAlchemy, Redis, S3 SDK або OCR SDK.

```mermaid
flowchart TD
    UI["Web UI"] --> HTTP["API transport"]
    HTTP --> App["Application use cases"]
    Jobs["Worker entrypoints"] --> App
    App --> Domain["Domain modules"]
    Infra["DB / Queue / Storage / Providers"] --> App
    Infra --> Domain
```

Дозволені предметні залежності:

```text
identity
projects -> identity
sources -> projects
processing -> sources
document -> sources
lexicography -> document
review -> lexicography, identity
exports -> lexicography, review
quality -> processing, document, lexicography, review
```

Зворотні імпорти заборонені. Наприклад, `document` не знає про `lexicography`, а `lexicography` не запускає `processing`. Взаємодія між модулями відбувається через application services, IDs, DTO та доменні події після commit.

## 7. Основні потоки даних

### 7.1. Завантаження

1. API перевіряє доступ і метадані файлу.
2. Файл проходить MIME/size validation та отримує SHA-256 checksum.
3. Бінарні дані зберігаються в object storage.
4. У PostgreSQL створюється `SourceDocument` з URI, checksum, MIME, розміром і правовим статусом.
5. Потенційно небезпечний або юридично невизначений матеріал не публікується.

### 7.2. Обробка

1. API створює immutable `ProcessingRun` із версією pipeline та конфігурацією.
2. API ставить у Redis лише job ID, а не бінарний файл.
3. Worker читає source з object storage.
4. Кожний stage записує статус і versioned artifact.
5. Повторний запуск того самого stage з однаковими input checksum та config hash не створює дубліката.
6. Помилка етапу не видаляє успішні результати попередніх етапів.

### 7.3. Валідація

1. Автоматичний результат створюється як proposal.
2. Поле посилається на сторінку, координати, OCR-токени, run і confidence.
3. Ручне виправлення зберігається окремою revision/annotation.
4. `source_text` є незмінним спостереженням; `normalized_text` — окреме підтверджуване значення.
5. Експорт використовує лише дозволений validation status.

## 8. Канонічні контракти

OCR-провайдер реалізує порт на кшталт:

```python
class OcrProvider(Protocol):
    def recognize(self, page: PageInput, config: OcrConfig) -> OcrPage: ...
```

`OcrPage` містить provider/version, raw artifact reference, blocks, lines і tokens. Кожний token має `text`, `bounding_box`, `confidence` та стабільний ID. Provider-specific відповідь не потрапляє безпосередньо в доменну модель.

Тривала HTTP-операція повертає `202 Accepted` і `processing_run_id`. Прогрес читається через окремий endpoint. Контракти API документуються OpenAPI, а TypeScript DTO генеруються з нього.

## 9. Дані та provenance

Реляційно зберігаються стабільні сутності: user, project, source, page, processing run, entry, revision, annotation, export. JSONB використовується для provider output, конфігурацій і словниково-специфічних полів, але не замінює ключові зв'язки.

Мінімальний provenance структурованого поля:

- `source_document_id`;
- `page_id`;
- bounding box або список token IDs;
- `processing_run_id` та stage version;
- `source_text`;
- `normalized_text`, якщо існує;
- confidence;
- спосіб походження: `ocr`, `rule`, `model`, `manual`;
- автор і час ручної зміни.

## 10. Безпека й операційні обмеження

- недовірені PDF не обробляються всередині API-процесу;
- credentials та signed storage URLs не зберігаються в логах;
- доступ перевіряється в application use case, а не лише в UI;
- публікація залежить від правового статусу джерела;
- processing jobs мають timeout, retry policy та concurrency limits;
- health checks розрізняють liveness і readiness;
- audit trail є append-oriented;
- секрети надходять через environment/secrets provider і не комітяться.

## 11. Структура репозиторію

```text
cadmus-dictionary-studio/
├── apps/
│   ├── api/
│   ├── worker/
│   └── web/
├── packages/
│   └── backend/
│       └── src/cadmus/
│           ├── identity/
│           ├── projects/
│           ├── sources/
│           ├── processing/
│           ├── document/
│           ├── lexicography/
│           ├── review/
│           ├── exports/
│           └── quality/
├── infrastructure/
├── docs/
│   └── decisions/
├── fixtures/
└── tests/
```

Це логічні межі, а не вимога створювати дев'ять окремо опублікованих Python packages. До появи реальної потреби модулі залишаються частинами одного deployable backend.

## 12. Перевірка Acceptance Criteria BH-175

- [x] Компоненти та потоки даних описані.
- [x] MVP і out-of-scope сформульовані явно.
- [x] Напрямки залежностей визначені й не утворюють циклів.
- [x] Ключові рішення зафіксовані ADR у `docs/decisions/`.
- [x] Реалізація авторизації, OCR, layout analysis і словникової логіки не входить у цю зміну.

