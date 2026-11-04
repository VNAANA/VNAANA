# AI API (Sprint 2)

The AI API uses only text supplied in the request. It does not query the article
database, fetch a URL, or store questions and article text. Ollama runs locally at
`OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`); `OLLAMA_MODEL` defaults to
`llama3.2`. The model must already be installed. No model download is automatic.

For summary and Q&A, `language` selects the **answer language** (`en` or `nl`),
not the article's original language. Always send the original article text, even
when a translated version is displayed. Keep original and displayed text separate
in the client; these endpoints do not fetch an article by ID or use chat history.

## Summarize

`POST /ai/summarize`

This endpoint produces a short, plain-language explanation. The frontend uses it
for the **Explain it simpler** action. It is separate from factual questions sent
to `/ai/ask`.

```json
{
  "article_text": "The city opened a new library on Monday. It has two reading rooms.",
  "source_url": "https://example.org/library",
  "language": "en"
}
```

## Ask about the article

`POST /ai/ask`

```json
{
  "article_text": "The city opened a new library on Monday. It has two reading rooms.",
  "question": "When did the library open?",
  "source_url": "https://example.org/library",
  "language": "en"
}
```

Both endpoints return the same shape:

```json
{
  "text": "It opened on Monday.",
  "sources": ["https://example.org/library"],
  "uncertainty": "Only the supplied article was checked; other sources were not verified.",
  "status": "answered"
}
```

`sources` contains the submitted URL only, or `[]` when omitted; it is **not** an
independently verified citation. Each request is grounded in one supplied article,
not multiple corroborated sources. An unsupported question returns HTTP 200 with
`status: "insufficient_information"`, a clear explanation in `text` and
`uncertainty`, and no invented answer. Empty or over-limit inputs receive HTTP 422;
an unavailable model or invalid model response receives HTTP 503. The article limit
is 12,000 characters and the question limit is 500 characters. `language` is `en`
or `nl` and controls the output language.

The frontend maps `/articles/random` results to feed stories in
`Frontend/src/utils/articles.ts` and distinguishes two grounding modes:

- `full_article`: send the exact, nonempty `ArticleRead.content`.
- `preview`: when content is missing, send only the unshortened title and
  normalized description that the API already supplied. If no description is
  available, send only the headline.

Preview mode is clearly identified in the chat. It does not fetch the submitted
URL and must not imply that Nova read the full article. Factual preview answers use
the same exact-evidence validation as full-article answers, so unsupported cause,
future, or detail questions return `insufficient_information`. Summaries do not
return evidence; they remain limited to prompt-based grounding and the uncertainty
notice. The real `canonical_url` is included only when available and is not an
independently verified citation.

The chat remains unavailable when the selected grounding text exceeds 12,000
characters; text is never silently truncated for AI. `Frontend/src/utils/nova.ts`
uses the same `VITE_API_BASE_URL` helper as article fetching. The UI must not claim
multiple verified sources based on this single-context API.

Run offline unit tests with `python -m pytest -c Backend/pytest.ini
Backend/tests/unit/logic/test_ai_service.py Backend/tests/unit/logic/test_ollama_client.py`.
Once Ollama is running and the configured model is installed, run the separate
manual smoke test with `python -m Backend.tests.manual.ai_ollama_smoke`.
