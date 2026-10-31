import json
import unittest

from Backend.Logic.ai_service import (
    AIInputError,
    AIModelError,
    AIService,
    MAX_ARTICLE_CHARS,
    MAX_QUESTION_CHARS,
)


class FakeModel:
    def __init__(self, answer: dict | None = None, failure: bool = False):
        self.answer = answer or {"text": "A short summary."}
        self.failure = failure
        self.calls = []

    def generate(self, system: str, prompt: str) -> str:
        self.calls.append((system, prompt))
        if self.failure:
            raise AIModelError("offline")
        return json.dumps(self.answer)


class AIServiceTests(unittest.TestCase):
    def test_summary_english_with_source(self):
        fake = FakeModel()
        result = AIService(fake.generate).summarize("The bridge reopened today.", "en", "https://example.org/news")
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["text"], "A short summary.")
        self.assertEqual(result["sources"], ["https://example.org/news"])
        self.assertIn("English", fake.calls[0][0])
        self.assertIn("The bridge reopened today.", fake.calls[0][1])

    def test_summary_dutch_without_source(self):
        fake = FakeModel({"text": "De brug is weer open."})
        result = AIService(fake.generate).summarize("The bridge reopened today.", "nl")
        self.assertEqual(result["sources"], [])
        self.assertIn("Dutch", fake.calls[0][0])
        self.assertIn("Alleen het aangeleverde artikel", result["uncertainty"])

    def test_answer_requires_exact_article_evidence(self):
        fake = FakeModel({"status": "answered", "text": "Today.", "evidence": "reopened today"})
        result = AIService(fake.generate).ask("The bridge reopened today.", "When?", "en")
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["text"], "Today.")
        self.assertIn("When?", fake.calls[0][1])

    def test_dutch_unanswerable_question(self):
        fake = FakeModel({"status": "insufficient_information", "text": "", "evidence": ""})
        result = AIService(fake.generate).ask("De brug is open.", "Wie bouwde de brug?", "nl")
        self.assertEqual(result["status"], "insufficient_information")
        self.assertIn("onvoldoende informatie", result["uncertainty"])
        self.assertIn("Dutch", fake.calls[0][0])

    def test_unsupported_evidence_is_not_returned_as_an_answer(self):
        fake = FakeModel({"status": "answered", "text": "In 2024.", "evidence": "The bridge opened in 2024"})
        result = AIService(fake.generate).ask("The bridge reopened today.", "When?", "en")
        self.assertEqual(result["status"], "insufficient_information")

    def test_rejects_blank_and_oversized_inputs_without_model_call(self):
        fake = FakeModel()
        service = AIService(fake.generate)
        for text in ("", "  ", "a" * (MAX_ARTICLE_CHARS + 1)):
            with self.subTest(text_length=len(text)), self.assertRaises(AIInputError):
                service.summarize(text, "en")
        for question in ("", "  ", "q" * (MAX_QUESTION_CHARS + 1)):
            with self.subTest(question_length=len(question)), self.assertRaises(AIInputError):
                service.ask("A short article.", question, "en")
        with self.assertRaises(AIInputError):
            service.summarize("A short article.", "fr")
        self.assertEqual(fake.calls, [])

    def test_model_failure_and_invalid_json(self):
        with self.assertRaises(AIModelError):
            AIService(FakeModel(failure=True).generate).summarize("Article.", "en")
        with self.assertRaises(AIModelError):
            AIService(lambda _system, _prompt: "not json").summarize("Article.", "en")

    def test_summary_rejects_unfinished_or_overlong_output(self):
        article = " ".join(["The library opened on Monday and welcomed readers today."] * 4)
        for output in ('The mayor said:', 'The mayor said: "Welcome.', article):
            with self.subTest(output=output), self.assertRaises(AIModelError):
                AIService(FakeModel({"text": output}).generate).summarize(article, "en")

    def test_answer_prompt_explicitly_requires_requested_language(self):
        fake = FakeModel({"status": "answered", "text": "Two million euros.", "evidence": "2 miljoen euro"})
        result = AIService(fake.generate).ask("Het gebouw kostte 2 miljoen euro.", "How much?", "en")
        self.assertEqual(result["status"], "answered")
        self.assertIn("MUST be in English", fake.calls[0][0])
        self.assertIn("keep the evidence as an exact quote", fake.calls[0][0])

    def test_english_summary_uses_original_dutch_article(self):
        original = "De bibliotheek is maandag geopend."
        fake = FakeModel({"text": "The library opened on Monday."})
        result = AIService(fake.generate).summarize(original, "en")
        self.assertEqual(result["status"], "answered")
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("entirely in English", fake.calls[0][0])
        self.assertEqual(fake.calls[0][1], f"ARTICLE:\n{original}")

    def test_dutch_answer_uses_original_english_article_as_evidence(self):
        original = "The library opened on Monday."
        fake = FakeModel({"status": "answered", "text": "Op maandag.", "evidence": "opened on Monday"})
        result = AIService(fake.generate).ask(original, "Wanneer?", "nl")
        self.assertEqual(result["status"], "answered")
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("MUST be in Dutch", fake.calls[0][0])
        self.assertEqual(fake.calls[0][1], f"ARTICLE:\n{original}\n\nQUESTION:\nWanneer?")


if __name__ == "__main__":
    unittest.main()
