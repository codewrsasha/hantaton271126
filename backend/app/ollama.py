import json
from contextlib import closing
from http.client import HTTPConnection, HTTPException

MODEL = "qwen3:4b-instruct"
PORT = 11435


class ModelError(Exception):
    pass


def request(path: str, *, payload: dict | None = None, timeout: int = 3) -> dict:
    try:
        with closing(HTTPConnection("127.0.0.1", PORT, timeout=timeout)) as connection:
            if payload is None:
                connection.request("GET", path)
            else:
                connection.request("POST", path, json.dumps(payload), {"Content-Type": "application/json"})
            response = connection.getresponse()
            if response.status == 404:
                raise ModelError("Модель Qwen3 4B Instruct не найдена в локальной Ollama.")
            if response.status != 200:
                raise ModelError("Локальная Ollama не смогла выполнить запрос.")
            body = json.loads(response.read(256 * 1024))
    except TimeoutError:
        raise
    except (OSError, HTTPException):
        raise ModelError("Не удалось подключиться к локальной Ollama. Проверьте, запущена ли она.") from None
    except ValueError:
        raise ModelError("Локальная Ollama вернула некорректный ответ.") from None
    if not isinstance(body, dict):
        raise ModelError("Локальная Ollama вернула некорректный ответ.")
    return body


def available() -> bool:
    try:
        models = request("/api/tags").get("models")
        return isinstance(models, list) and any(isinstance(item, dict) and item.get("name") == MODEL for item in models)
    except (ModelError, TimeoutError):
        return False


def answer(messages: list[dict[str, str]]) -> str:
    body = request("/api/chat", payload={
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "keep_alive": "5m",
        "options": {"num_ctx": 4096, "num_predict": 500, "temperature": 0.2},
    }, timeout=120)
    message = body.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ModelError("Локальная модель вернула пустой ответ.")
    return content.strip()
