# Jack app — инструкция для Claude Code

Проект передан Маше от Дарьи (Marketing, Beloved Pets). Джек — Streamlit-приложение для SMM Beloved Pets и Tobydic:
контент-план, рилсы и карусели, подписи к видео, ТЗ Дине в Notion.

## Установка
1. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
2. Проверь `.streamlit/secrets.toml`: нужны APP_PASSWORD, SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY, NOTION_TOKEN.
   Файл уже лежит в папке. Если его нет, сделай по `secrets.toml.example` и спроси значения у Маши. Ключи не выводи в чат и не коммить.
3. Запуск: `streamlit run app.py` → http://localhost:8501
4. Скилл `/jack`: скопируй `../_context/claude-skill-jack/SKILL.md` в `~/.claude/skills/jack/SKILL.md`.
5. Прочитай `../_context/история-и-грабли/*.md` до первой правки.

## Как устроено
- Прод: https://jacksmm-app.streamlit.app (Streamlit Cloud). Деплой = `git push` в `main` репозитория
  `marketingbeloved/jack-app`, сайт пересобирается сам. ngrok и `bin/run_jack_forever.sh` не использовать.
- Репозиторий ПУБЛИЧНЫЙ. Ключи, `brand_data/` и `cache/` не коммитить (они в .gitignore).
- Данные общие для команды и живут в Supabase (`plan_briefs`, `models/shared_store.py`). Локальный `cache/` — только бэкап.
  База общая с Content Factory: ничего не удалять.
- LLM: локально `claude` CLI, в облаке Gemini (`models/llm.py:smart_text`). Облачные ключи хранятся в Streamlit → Settings → Secrets,
  менять их может только человек.
- Notion: база Videos `2182452d-f1db-803d-ba88-d5bee781a6fd` (`scripts/jack_notion.py`).

## Правила
- Перед push покажи Маше, что меняешь. Наружу (Notion, коллегам, публикации) ничего не отправлять без её «да».
- Не тестировать отправку через `push_post`: она пишет ссылки в общую базу. Тестируй через `build_concept` + `publish_to_notion`.
- «Джек не пишет» обычно значит, что протух GEMINI_API_KEY в облаке (формат `AQ.…` временный, нужен `AIzaSy…`)
  или Google снял модель (404). Проверь список моделей: `GET /v1beta/models`.
- В текстах нельзя писать «Made in USA» и «vet-developed». В видео ничего не должно дёргаться:
  никаких пружин, зума и прыгающих субтитров.
- На этом маке нет Content Factory. Вкладка CF покажет, что ключей Telegram и GeeLark нет, это нормально.
