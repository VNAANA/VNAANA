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

    def test_summary_supports_all_english_dutch_language_directions(self):
        cases = (
            ("The bridge reopened today.", "en", "The bridge reopened today."),
            ("De brug werd vandaag heropend.", "en", "The bridge reopened today."),
            ("The bridge reopened today.", "nl", "De brug werd vandaag heropend."),
            ("De brug werd vandaag heropend.", "nl", "De brug werd vandaag heropend."),
        )
        for article, language, summary in cases:
            with self.subTest(article=article, language=language):
                fake = FakeModel({"text": summary})
                result = AIService(fake.generate).summarize(article, language)
                self.assertEqual(result["text"], summary)
                self.assertEqual(len(fake.calls), 1)
                self.assertIn("clear, plain language", fake.calls[0][0])

    def test_wrong_language_summary_is_corrected_once(self):
        article = "De brug werd vandaag opnieuw geopend."
        responses = iter([
            {"text": "De brug werd vandaag geopend."},
            {"text": "The bridge reopened today."},
        ])
        calls = []

        def generate(system, prompt):
            calls.append((system, prompt))
            return json.dumps(next(responses))

        result = AIService(generate).summarize(article, "en")

        self.assertEqual(result["text"], "The bridge reopened today.")
        self.assertEqual(len(calls), 2)
        self.assertIn("Rewrite only the supplied summary in natural English", calls[1][0])
        self.assertNotIn(article, calls[1][1])

    def test_failed_summary_language_correction_is_not_returned(self):
        article = "De brug werd vandaag opnieuw geopend."
        responses = iter([
            {"text": "De brug werd vandaag geopend."},
            {"text": "De brug werd gisteren geopend."},
        ])

        with self.assertRaises(AIModelError):
            AIService(lambda _system, _prompt: json.dumps(next(responses))).summarize(article, "en")

    def test_answer_requires_exact_article_evidence(self):
        fake = FakeModel({"status": "answered", "text": "Today.", "evidence": "reopened today"})
        result = AIService(fake.generate).ask("The bridge reopened today.", "When?", "en")
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["text"], "Today.")
        self.assertIn("When?", fake.calls[0][1])

    def test_preview_question_requires_evidence_from_supplied_preview(self):
        preview = "Fuel prices remain high.\n\nThe government is reviewing refinery capacity."
        fake = FakeModel({
            "status": "answered",
            "text": "The government is reviewing refinery capacity.",
            "evidence": "The government is reviewing refinery capacity.",
        })

        result = AIService(fake.generate).ask(preview, "What is the government reviewing?", "en")

        self.assertEqual(result["status"], "answered")
        self.assertIn(result["text"], preview)
        self.assertEqual(fake.calls[0][1], f"ARTICLE:\n{preview}\n\nQUESTION:\nWhat is the government reviewing?")

    def test_unsupported_preview_question_returns_insufficient_information(self):
        preview = "Fuel prices remain high.\n\nThe government is reviewing refinery capacity."
        fake = FakeModel({"status": "insufficient_information", "text": "", "evidence": ""})

        result = AIService(fake.generate).ask(preview, "Which company will buy the refinery?", "en")

        self.assertEqual(result["status"], "insufficient_information")

    def test_sequential_article_contexts_are_not_combined(self):
        responses = iter([
            {"status": "answered", "text": "The bridge reopened.", "evidence": "The bridge reopened."},
            {"status": "answered", "text": "The station closed.", "evidence": "The station closed."},
        ])
        calls = []

        def generate(system, prompt):
            calls.append((system, prompt))
            return json.dumps(next(responses))

        service = AIService(generate)
        service.ask("The bridge reopened.", "What happened?", "en")
        service.ask("The station closed.", "What happened?", "en")

        self.assertIn("ARTICLE:\nThe bridge reopened.", calls[0][1])
        self.assertNotIn("The station closed.", calls[0][1])
        self.assertIn("ARTICLE:\nThe station closed.", calls[1][1])
        self.assertNotIn("The bridge reopened.", calls[1][1])

    def test_dutch_unanswerable_question(self):
        fake = FakeModel({"status": "insufficient_information", "text": "", "evidence": ""})
        result = AIService(fake.generate).ask("De brug is open.", "Wie bouwde de brug?", "nl")
        self.assertEqual(result["status"], "insufficient_information")
        self.assertIn("onvoldoende informatie", result["uncertainty"])
        self.assertIn("Dutch", fake.calls[0][0])

    def test_unsupported_evidence_is_not_returned_as_an_answer(self):
        responses = iter([
            {"status": "answered", "text": "In 2024.", "evidence": "The bridge opened in 2024"},
            {"sentence_index": -1},
        ])
        result = AIService(lambda _system, _prompt: json.dumps(next(responses))).ask(
            "The bridge reopened today.", "When?", "en"
        )
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
        self.assertIn("text field MUST be in English", fake.calls[0][0])
        self.assertIn("evidence field MUST be an exact, continuous substring", fake.calls[0][0])

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
        self.assertEqual(result["text"], "Op maandag.")
        self.assertEqual(len(fake.calls), 1)
        self.assertIn("text field MUST be in Dutch", fake.calls[0][0])
        self.assertIn("Keep evidence in the article's original language", fake.calls[0][0])
        self.assertEqual(fake.calls[0][1], f"ARTICLE:\n{original}\n\nQUESTION:\nWanneer?")

    def test_translated_evidence_is_corrected_to_an_exact_original_quote(self):
        original = "The library opened on Monday."
        responses = iter([
            {"status": "answered", "text": "Op maandag.", "evidence": "De bibliotheek opende op maandag."},
            {"sentence_index": 0},
        ])
        calls = []

        def generate(system, prompt):
            calls.append((system, prompt))
            return json.dumps(next(responses))

        result = AIService(generate).ask(original, "What happened?", "nl")
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["text"], "Op maandag.")
        self.assertEqual(len(calls), 2)
        self.assertIn("numbered ORIGINAL ARTICLE sentence", calls[1][0])
        self.assertIn(f"[0] {original}", calls[1][1])
        self.assertIn("CANDIDATE ANSWER:\nOp maandag.", calls[1][1])

    def test_evidence_correction_rejects_fabricated_evidence(self):
        original = "The library opened on Monday."
        responses = iter([
            {"status": "answered", "text": "Op maandag.", "evidence": "De bibliotheek opende op maandag."},
            {"sentence_index": 99},
        ])
        with self.assertRaises(AIModelError):
            AIService(lambda _system, _prompt: json.dumps(next(responses))).ask(
                original, "What happened?", "nl"
            )

    def test_dutch_copied_english_answer_is_corrected_once(self):
        article = "The library opened on Monday."
        evidence = "The library opened on Monday."
        responses = iter([
            {"status": "answered", "text": evidence, "evidence": evidence},
            {"text": "De bibliotheek ging maandag open."},
        ])
        calls = []

        def generate(system, prompt):
            calls.append((system, prompt))
            return json.dumps(next(responses))

        result = AIService(generate).ask(article, "What happened?", "nl")
        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["text"], "De bibliotheek ging maandag open.")
        self.assertEqual(len(calls), 2)
        self.assertIn("candidate answer in natural Dutch", calls[1][0])
        self.assertIn(evidence, calls[1][1])

    def test_english_answer_copied_in_dutch_is_corrected_once(self):
        article = "De bibliotheek was overvol."
        evidence = article
        responses = iter([
            {"status": "answered", "text": "De bibliotheek was overvol.", "evidence": evidence},
            {"text": "The library was overcrowded."},
        ])

        result = AIService(lambda _system, _prompt: json.dumps(next(responses))).ask(
            article, "Why was the project funded?", "en"
        )

        self.assertEqual(result["status"], "answered")
        self.assertEqual(result["text"], "The library was overcrowded.")

    def test_dutch_correction_rejects_changed_evidence_or_english_text(self):
        article = "The library opened on Monday."
        first = {"status": "answered", "text": article, "evidence": article}
        invalid = (
            {"text": ""},
            {"text": article},
        )
        for second in invalid:
            with self.subTest(second=second):
                responses = iter([first, second])
                calls = []

                def generate(system, prompt):
                    calls.append((system, prompt))
                    return json.dumps(next(responses))

                with self.assertRaises(AIModelError):
                    AIService(generate).ask(article, "What happened?", "nl")
                self.assertEqual(len(calls), 2)

    def test_dutch_correction_model_failure_is_not_returned_as_english_answer(self):
        article = "The library opened on Monday."
        calls = []

        def generate(system, prompt):
            calls.append((system, prompt))
            if len(calls) == 2:
                raise AIModelError("offline")
            return json.dumps({"status": "answered", "text": article, "evidence": article})

        with self.assertRaises(AIModelError):
            AIService(generate).ask(article, "What happened?", "nl")
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
