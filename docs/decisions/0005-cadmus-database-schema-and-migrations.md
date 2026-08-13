# ADR-0005: Cadmus application schema and Alembic ownership

- Статус: Accepted
- Дата: 2026-08-13
- Jira: BH-179

## Контекст

BH-179 має підтвердити upgrade і downgrade реальною початковою міграцією, але
предметні моделі належать наступним Stories. Порожня revision не перевіряє
зміну схеми, а технічна таблиця без предметної відповідальності створила б
штучну сутність. Application metadata також потребує стабільного namespace,
який не залежить від стандартної PostgreSQL schema `public`.

## Рішення

Використовувати PostgreSQL schema `cadmus` для таблиць application persistence.
Спільна SQLAlchemy `MetaData` має `schema="cadmus"`; Alembic використовує саме
цю metadata для autogenerate. Початкова revision `bh179_0001` створює schema
`cadmus`, а downgrade видаляє її. Таблиця `alembic_version` залишається в
`public`, щоб Alembic міг завершити bookkeeping після видалення application
schema.

На поточному етапі використовується один синхронний SQLAlchemy 2 engine із
psycopg 3. Async persistence layer не додається без use case, який його
потребує.

## Наслідки

- початкова migration є реальною, reversible і не вигадує доменні таблиці;
- майбутні ORM mappings мають реєструватися на спільній application metadata;
- права PostgreSQL повинні дозволяти Cadmus role використовувати schema
  `cadmus`;
- domain code не імпортує SQLAlchemy; mappings залишаються infrastructure
  concerns;
- перенесення таблиць до іншої schema в майбутньому вимагатиме явної міграції.

## Відхилені альтернативи

- порожня baseline revision: не перевіряє керовану зміну schema;
- технічна health-check таблиця: не має предметного власника й створює зайвий
  persistence contract;
- доменні таблиці: передчасно реалізують scope наступних Stories;
- `Base.metadata.create_all()`: обходить Alembic history і rollback contract.
