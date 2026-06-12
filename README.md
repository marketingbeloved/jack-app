# Jack Web App — SMM Hub for Beloved Pets

Единое приложение для всей контент-операции BelovedPets (потом TOBYDIC).

## Что это

Streamlit web-app, который:

- даёт удобный UI для создания контент-плана и ТЗ
- использует Claude Code как мозг (через subprocess, бесплатно через твою подписку)
- публикует ТЗ в Notion для Дины
- пишет в Sheets контент-план
- держит сводку всей команды в одном окне

## Запуск

```bash
cd ~/Databases/jack-app
source .venv/bin/activate
streamlit run app.py
```

Открывается в браузере: <http://localhost:8501>

## Структура проекта

```
jack-app/
  app.py                  # главный файл Streamlit, sidebar + routing
  requirements.txt        # streamlit + lottie + requests
  .streamlit/config.toml  # тема (cream + sage-green)
  models/
    llm.py                # абстракция Claude / Kimi / DeepSeek
  views/
    home.py               # главный экран
    create_plan.py        # форма создания КП на месяц
    queue.py              # очереди команды (на approve / Дина / Вика)
    brand_brief.py        # viewer для BP-Brand-Brief.md
    neural_stack.py       # обзор доступных нейронок
  assets/                 # картинки, lottie-анимации (потом)
  scripts/                # bundled jack_notion.py и т.п.
```

## Бесплатный стек

| Компонент | Стоимость |
|---|---|
| Claude Code (мозг) | $0 — через подписку Дарьи |
| Streamlit | $0 — open source |
| Streamlit Cloud (если деплоить) | $0 — free tier |
| Kimi K2.6 для ресёрча | $0 — чат kimi.com |
| DeepSeek V3 для batch | $0.14/1M (5M free на старт) |
| Notion API | $0 |
| Google Sheets API | $0 |

## Текущий статус MVP

- ✅ Главный экран с навигацией
- ✅ Форма создания КП
- ✅ Очередь (читает Notion)
- ✅ Brand Brief viewer
- ✅ Neural stack info
- ⏳ Реальная генерация концептов через Claude
- ⏳ Kanban для approve
- ⏳ Lottie-аватар Джека (живой)
- ⏳ Google OAuth для multi-user
- ⏳ Sheets интеграция
- ⏳ Phase 2: Content Factory интеграция
- ⏳ TOBYDIC бренд
