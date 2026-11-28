import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from uuid import UUID

from ...contracts import AnalysisResult, Evidence, Requirement
from ..documents.models import Document, Fragment
from .models import AnalysisDocument

WORD = re.compile(r"[^\W\d_]{3,}")
STOP_WORDS = set("""
    для или при над под как это того если быть должен должна должны должно
    требуется обеспечение необходимо который которая которые также каждого
    каждый каждой быть более менее согласно настоящий
""".split())
MAX_EVIDENCE = 6
MAX_EXCERPT = 800


@dataclass(frozen=True)
class MatchSource:
    document: Document
    fragment: Fragment


def terms(text: str) -> set[str]:
    return {match.group().casefold() for match in WORD.finditer(text) if match.end() - match.start() <= 96} - STOP_WORDS


class Search:
    def __init__(self, sources: list[MatchSource]):
        self.sources = sources
        self.index: dict[str, list[int]] = defaultdict(list)
        for index, source in enumerate(sources):
            for term in terms(source.fragment.text):
                self.index[term].append(index)

    def candidates(self, query: set[str]) -> list[Evidence]:
        # Rank using up to twelve of the rarest matching terms.
        matching = sorted(query & self.index.keys(), key=lambda term: (len(self.index[term]), term))[:12]
        anchors = set(matching)
        scores = Counter(index for term in matching for index in self.index[term])
        threshold = min(2, len(query))
        # Include per-document leaders before filling slots with any further results.
        ranked = sorted(
            (index for index, score in scores.items() if score >= threshold),
            key=lambda index: (-scores[index], index),
        )
        preferred: dict[UUID, Evidence] = {}
        seen: set[tuple[UUID, str, str]] = set()
        evidence = []
        for index in ranked:
            source = self.sources[index]
            if source.document.id in preferred and len(evidence) >= MAX_EVIDENCE:
                continue
            text = source.fragment.text
            hit = next(match for match in WORD.finditer(text) if match.group().casefold() in anchors)
            start = max(0, hit.start() - 180)
            quote = text[start:start + MAX_EXCERPT]
            key = (source.document.id, source.fragment.location.model_dump_json(), quote)
            if key in seen:
                continue
            seen.add(key)
            item = Evidence(
                document_id=source.document.id, filename=source.document.filename,
                excerpt=quote, location=source.fragment.location, relation="context",
            )
            if source.document.id not in preferred:
                preferred[source.document.id] = item
                if len(preferred) >= MAX_EVIDENCE:
                    break
            elif len(evidence) < MAX_EVIDENCE:
                evidence.append(item)
        return (list(preferred.values()) + evidence)[:MAX_EVIDENCE]


def evaluate(
    requirements: list[Requirement], documents: list[AnalysisDocument], sources: list[MatchSource],
) -> list[AnalysisResult]:
    search = Search(sources)
    limited = any(document.state != "extracted" or not document.fragment_count for document in documents)
    results = []
    for requirement in requirements:
        evidence = search.candidates(terms(requirement.requirement_text))
        if evidence:
            status = "требуется проверка"
            explanation = (
                "Найдены фрагменты с общими терминами. Эксперту нужно проверить их смысл, "
                "в том числе возможные противоречия."
            )
        else:
            status = "недостаточно данных"
            explanation = "Поиск не нашёл фрагментов с достаточным совпадением терминов."
        if limited:
            explanation += " У выбранных документов есть ограничения извлечения. См. замечания к документам."
        if any(item.location.kind == "unknown" for item in evidence):
            explanation += " У части цитат точное местоположение не установлено."
        results.append(AnalysisResult(
            **requirement.model_dump(), evidence=evidence, status=status, explanation=explanation,
        ))
    return results
