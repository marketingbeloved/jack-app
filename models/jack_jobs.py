"""Фоновая генерация рилс-скриптов — переживает сбросы соединения Streamlit Cloud.

Проблема: на бесплатном Streamlit Community Cloud долгий (30-90 сек) LLM-запрос прямо
в веб-сессии часто обрывается сбросом websocket → результат теряется («Джек не пишет»).

Решение: запускаем генерацию в ФОНОВОМ ПОТОКЕ внутри того же процесса приложения,
поток пишет результат в общую базу (Supabase). Веб-страница опрашивает базу и
показывает готовый скрипт, когда он готов — даже если соединение сбрасывалось или
вкладку перезагрузили (job_id хранится в URL).
"""

from __future__ import annotations

import os
import threading
import uuid


def _key(job_id: str) -> str:
    return f"job_{job_id}"


def _hydrate_env_for_thread() -> None:
    """Скопировать секреты в env, чтобы фоновый поток (без ScriptRunContext) их видел.
    st.secrets надёжно читается только в главном потоке — поэтому делаем это ДО спавна."""
    try:
        import streamlit as st
        for k in ("GEMINI_API_KEY", "SUPABASE_URL", "SUPABASE_KEY",
                  "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL"):
            try:
                if k in st.secrets and not os.environ.get(k):
                    os.environ[k] = str(st.secrets[k]).strip()
            except Exception:
                pass
    except Exception:
        pass


def _run_job(job_id: str, req: dict) -> None:
    """Тело фонового потока: генерим скрипт и пишем результат в общую базу."""
    from models import shared_store
    try:
        # ОДИН проход (а не глубокий 2-проходный) — бережём бесплатный суточный лимит
        # Gemini (deep жёг вдвое). Фон сохраняем — он и решает проблему надёжности.
        from models.jack_engine import generate_concepts
        res = generate_concepts(req, save=False)
        if res and isinstance(res[0], dict) and "error" in res[0]:
            shared_store.put_json(_key(job_id), {"status": "error", "result": None,
                                                 "error": str(res[0].get("error", "ошибка"))[:300]})
        elif res:
            shared_store.put_json(_key(job_id), {"status": "done", "result": res[0], "error": ""})
        else:
            shared_store.put_json(_key(job_id), {"status": "error", "result": None,
                                                 "error": "Пустой ответ от движка."})
    except Exception as e:  # noqa: BLE001
        shared_store.put_json(_key(job_id), {"status": "error", "result": None,
                                             "error": f"{type(e).__name__}: {str(e)[:200]}"})


def start_job(req: dict) -> str:
    """Запустить фоновую генерацию. Возвращает job_id; результат потом в get_job()."""
    job_id = uuid.uuid4().hex[:10]
    from models import shared_store
    shared_store.put_json(_key(job_id), {"status": "pending", "result": None, "error": ""})
    _hydrate_env_for_thread()
    threading.Thread(target=_run_job, args=(job_id, req), daemon=True).start()
    return job_id


def get_job(job_id: str) -> dict | None:
    """Текущее состояние задачи: {'status': pending|done|error, 'result':…, 'error':…} или None."""
    if not job_id:
        return None
    from models import shared_store
    return shared_store.get_json(_key(job_id), None)
