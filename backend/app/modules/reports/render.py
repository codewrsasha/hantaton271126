from html import escape
from urllib.parse import urlencode

from ...contracts import AnalysisResult, Location
from ..analysis.models import AnalysisRun

CSP = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
RELATIONS = {"supports": "Подтверждает", "contradicts": "Противоречит", "context": "Контекст"}
STATES = {
    "received": "Получен",
    "extracted": "Текст извлечён",
    "needs_review": "Требуется проверка извлечения",
    "failed": "Ошибка извлечения",
}


def link(origin: str, page: str, label: str, **params: str) -> str:
    address = f"{origin}/#{page}?{urlencode(params)}"
    return f'<a href="{escape(address)}">{escape(label)}</a>'


def location_label(location: Location) -> str:
    if location.kind == "pdf_page":
        return f"Страница {location.page}"
    if location.kind == "docx_section":
        return f"Раздел {location.section}"
    return "Точное местоположение не установлено"


def result_section(result: AnalysisResult, origin: str) -> str:
    source = result.source_reference
    catalog_link = link(origin, "requirements", f"Приказ № {source.order_number}, пункт {source.clause}",
                        requirement=result.requirement_id, revision=source.revision, clause=source.clause)
    review = result.review
    effective = (review.corrected_status if review else None) or result.status
    comment = escape(review.comment) if review else "Экспертная проверка не выполнена."
    fragments = []
    for index, item in enumerate(result.evidence):
        relation = review.evidence_relations.get(index, item.relation) if review else item.relation
        document = link(origin, "documents", item.filename, document=str(item.document_id))
        fragments.append(
            f"<li>{document} · <code>{item.document_id}</code> · {escape(location_label(item.location))}"
            f" · {RELATIONS[relation]}<blockquote>{escape(item.excerpt)}</blockquote></li>"
        )
    evidence = f"<ul>{''.join(fragments)}</ul>" if fragments else "<p>Подходящих фрагментов нет.</p>"
    return (
        f"<section><h2>{escape(result.requirement_id)}</h2>"
        f"<p>{catalog_link} · редакция {escape(source.revision)}</p>"
        f'<p class="original">{escape(result.requirement_text)}</p>'
        f"<dl><dt>Текущий статус</dt><dd>{escape(effective)}</dd>"
        f"<dt>Исходный статус</dt><dd>{escape(result.status)}</dd>"
        f"<dt>Обоснование</dt><dd>{escape(result.explanation)}</dd>"
        f"<dt>Экспертный комментарий</dt><dd>{comment}</dd></dl>"
        f"<h3>Доказательства</h3>{evidence}</section>"
    )


def render(run: AnalysisRun, origin: str) -> str:
    documents = []
    for doc in run.documents:
        title = link(origin, "documents", doc.filename, document=str(doc.id))
        issue = f" · {escape(doc.issue.message)}" if doc.issue else ""
        documents.append(
            f"<li>{title} · <code>{doc.id}</code> · {STATES[doc.state]} · "
            f"фрагментов: {doc.fragment_count}{issue}</li>"
        )
    results = "".join(result_section(result, origin) for result in run.results)
    run_link = link(origin, "analysis", str(run.id), run=str(run.id))
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Предварительный отчёт о пробелах</title>
<style>
body {{font: 1rem/1.5 system-ui,sans-serif; max-width: 70ch; margin: 2rem auto; padding: 0 1rem; color: #171717; overflow-wrap: anywhere}}
section {{border-top: 1px solid #ccc; padding: 0.7rem 0}}
blockquote, .original, dd {{white-space: pre-wrap; tab-size: 4}}
blockquote {{border-left: 2px solid #888; margin-inline: 0; padding-inline: 1rem}}
dt {{font-weight: 650}} dd {{margin: 0 0 0.5rem}}
</style></head><body>
<h1>Предварительный отчёт о пробелах</h1>
<p>Отчёт предназначен для экспертной проверки и не является юридическим заключением.
Статусы «недостаточно данных» и «требуется проверка» отражают неопределённость.
Несоответствия указываются отдельным статусом.</p>
<dl><dt>Запуск проверки</dt><dd>{run_link}</dd>
<dt>Дата запуска (UTC)</dt><dd>{escape(run.created_at.isoformat())}</dd>
<dt>Редакция</dt><dd>{escape(run.revision)}</dd>
<dt>Дата редакции</dt><dd>{run.revision_date.isoformat()}</dd>
<dt>Дата получения</dt><dd>{run.obtained_on.isoformat()}</dd>
<dt>Источник требований</dt><dd>{escape(run.source)}</dd>
<dt>SHA-256 пакета требований</dt><dd><code>{escape(run.revision_sha256)}</code></dd></dl>
<h2>Исходные документы</h2><ul>{''.join(documents)}</ul>
{results}</body></html>"""
