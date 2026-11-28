import re
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException

from ..contracts import Evidence
from .analysis.matching import MatchSource, Search, terms
from .documents import storage
from .documents.models import Document, Fragment

OVERVIEW = re.compile(
    r"перескаж|прочитай|резюм|суммариз|выжимк|кратк[а-яё]* излож|о ч[её]м|"
    r"что (?:написано|содержится|внутри)|содержани|summari"
)
FILE_WORD = re.compile(r"\b(?:файл|документ|вложени|приложен[а-яё]* файл)")
ORDER_WORD = re.compile(r"\b(?:приказ|фстэк)")
CHUNK_SIZE = 680
MAX_EXCERPTS = 4


def sample(document: Document, fragments: list[Fragment], limit: int) -> tuple[list[Evidence], bool]:
    chunks: list[Fragment] = []
    for fragment in fragments:
        text = fragment.text.strip()
        if not text:
            continue
        if chunks and chunks[-1].location == fragment.location and len(chunks[-1].text) + len(text) + 2 <= CHUNK_SIZE:
            chunks[-1] = Fragment(chunks[-1].text + "\n\n" + text, fragment.location)
        else:
            chunks.extend(Fragment(text[i:i + CHUNK_SIZE], fragment.location) for i in range(0, len(text), CHUNK_SIZE))
    complete = len(chunks) <= limit
    if not complete:
        chunks = [chunks[i * (len(chunks) - 1) // (limit - 1)] for i in range(limit)] if limit > 1 else chunks[:1]
    return [
        Evidence(document_id=document.id, filename=document.filename, excerpt=item.text, location=item.location,
                 relation="context")
        for item in chunks
    ], complete


def context(
    path: Path, dialog_id: UUID, question: str, previous: str, document_id: UUID | None,
) -> tuple[list[Evidence], str | None, bool]:
    documents = storage.list_documents(path, dialog_id)
    query = question.casefold()
    named = [document for document in documents if document.filename.casefold() in query]
    order_request = ORDER_WORD.search(query)
    file_request = bool(document_id or named or (FILE_WORD.search(query) and not order_request)
                        or re.search(r"\b(?:мо[йегою]|прикрепл[а-яё]*|загруженн[а-яё]*)\s+(?:файл|документ)", query))
    overview = bool(OVERVIEW.search(query) and (file_request or (documents and not order_request)))
    if document_id:
        doc = storage.get_document(path, document_id, dialog_id)
        if doc is None:
            raise HTTPException(404, "Файл не найден в текущем диалоге.")
        documents = [doc]
    elif named:
        documents = named

    if not documents:
        return [], "В этом диалоге нет файлов. Прикрепите PDF или DOCX." if file_request else None, file_request

    if not overview:
        words = terms(question) - {"приказ", "пункт", "требования", "фстэк", "файл", "документ", "покажи", "найди", "скажи", "какие"}
        if words or previous:
            sources = [
                MatchSource(document, fragment)
                for document in documents[:8]
                for fragment in storage.read_fragments(path, document.id, dialog_id)
            ]
            search = Search(sources)
            evidence = search.candidates(words) or search.candidates(terms(previous))
            if evidence:
                return evidence[:2], "Модели переданы найденные фрагменты файла." if file_request else None, file_request
        if not file_request:
            return [], None, False

    evidence = []
    notes = []
    selected = documents[:3]
    budget, spare = divmod(MAX_EXCERPTS, len(selected))
    for i, document in enumerate(selected):
        fragments = storage.read_fragments(path, document.id, dialog_id)
        excerpts, complete = sample(document, fragments, budget + (i < spare))
        evidence.extend(excerpts)
        if not excerpts:
            notes.append(f"«{document.filename}»: извлечённого текста нет.")
        elif not complete:
            notes.append(f"«{document.filename}»: модели передана часть извлечённого текста.")
        if document.issue and excerpts:
            notes.append(f"«{document.filename}»: {document.issue.message}")
    if len(documents) > len(selected):
        notes.append("Для общего запроса использованы три последних файла. Выберите нужный файл для отдельного вопроса.")
    return evidence, " ".join(notes) or None, overview or file_request
