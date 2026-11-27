import unittest
from uuid import uuid4

from pydantic import ValidationError

from app.contracts import AnalysisResult, Evidence

# Every identifier and excerpt in these tests is synthetic.
REQUIREMENT = {
    "requirement_id": "synthetic",
    "requirement_text": "Синтетический текст для проверки схемы.",
    "source_reference": {
        "order_number": "117",
        "revision": "synthetic",
        "clause": "synthetic",
    },
    "explanation": "Синтетическое обоснование.",
}


def evidence(relation: str) -> Evidence:
    return Evidence(
        document_id=uuid4(),
        filename="synthetic.pdf",
        excerpt="Синтетический фрагмент.",
        location={"kind": "pdf_page", "page": 1},
        relation=relation,
    )


class AnalysisResultTests(unittest.TestCase):
    def test_insufficient_data_without_evidence(self):
        result = AnalysisResult(
            **REQUIREMENT, status="недостаточно данных", evidence=[]
        )
        self.assertEqual(result.evidence, [])
        self.assertIsNone(result.review)

    def test_compliance_requires_support(self):
        with self.assertRaises(ValidationError):
            AnalysisResult(**REQUIREMENT, status="соответствует", evidence=[])

        result = AnalysisResult(
            **REQUIREMENT, status="соответствует", evidence=[evidence("supports")]
        )
        self.assertEqual(result.evidence[0].location.kind, "pdf_page")

    def test_noncompliance_requires_contradiction(self):
        with self.assertRaises(ValidationError):
            AnalysisResult(
                **REQUIREMENT, status="не соответствует", evidence=[evidence("context")]
            )

    def test_expert_status_keeps_original_status(self):
        result = AnalysisResult(
            **REQUIREMENT,
            status="требуется проверка",
            evidence=[evidence("contradicts")],
            review={
                "comment": "Эксперт подтвердил противоречие.",
                "corrected_status": "не соответствует",
            },
        )
        self.assertEqual(result.status, "требуется проверка")
        self.assertEqual(result.review.corrected_status, "не соответствует")

    def test_pdf_pages_are_one_based(self):
        with self.assertRaises(ValidationError):
            Evidence(
                document_id=uuid4(),
                filename="synthetic.pdf",
                excerpt="Синтетический фрагмент.",
                location={"kind": "pdf_page", "page": 0},
                relation="context",
            )
