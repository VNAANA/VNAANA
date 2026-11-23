# Ask Nova – Backend API Guide

Ask Nova allows users to ask questions about news Stories, request simpler explanations, and continue conversations with follow-up questions.

The new implementation works with Stories containing one or multiple linked Articles. The backend retrieves the original Article content, sends it to the selected AI model, and checks supporting evidence before returning an answer.

This guide explains how to configure Ask Nova and connect it to the Story-based frontend.

## 1. AI Provider Configuration

Ask Nova supports local Ollama and the Fontys-hosted AI model.

Configure the provider in the backend environment or `Backend/.env`.

| Variable | Default | Purpose |
|---|---|---|
| `AI_PROVIDER` | `ollama` | Choose `ollama` or `fontys`. |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama server address. |
| `OLLAMA_MODEL` | `llama3.2` | Installed Ollama model. |
| `OLLAMA_TIMEOUT_SECONDS` | `90` | Request timeout in seconds. |
| `FONTYS_API_KEY` | Not set | Required when using Fontys. |
| `FONTYS_MODEL` | `fontys-gpt-5.6-sol` | Fontys model alias. |
| `FONTYS_ENDPOINT` | `https://api.portkey.ai/v1/chat/completions` | Fontys gateway endpoint. |
| `FONTYS_TIMEOUT_SECONDS` | `90` | Request timeout in seconds. |

Ollama is used by default. To use the Fontys model, set `AI_PROVIDER=fontys` and provide `FONTYS_API_KEY`.

The Fontys client sends requests through the configured gateway using the `x-portkey-api-key` header. It requests JSON output with a maximum of 4,096 completion tokens.

Keep API keys in the backend environment. Never include them in frontend code or commit them to Git.

## 2. Story-based Ask Nova

**Endpoint:** `POST /ai/stories/{story_id}/ask`

This is the main endpoint for the new Story-based frontend.

The frontend sends the Story ID, the user's question, and the selected language. The backend retrieves the linked Articles and uses their original content to generate an answer.

The same endpoint supports:
- Questions about a Story.
- Simpler explanations of news.
- Follow-up questions in a conversation.
- Stories containing one or multiple Articles.

### Request

```json
{
  "question": "When did that happen?",
  "language": "en",
  "history": [
    {
      "role": "user",
      "content": "What happened in this story?"
    },
    {
      "role": "assistant",
      "content": "The city opened a new library."
    }
  ]
}
```

| Field | Description |
|---|---|
| `story_id` | Story UUID included in the endpoint URL. |
| `question` | Required question, maximum 500 characters. |
| `language` | Answer language: `nl` (Dutch) or `en` (English). |
| `history` | Optional previous messages for follow-up questions. |

The language field controls Nova's answer language, not the language of the original Articles. For example, Nova can read Dutch Articles and answer in English.

For a new conversation, omit `history` or send `[]`.

### Conversation History

Ask Nova supports follow-up questions by including recent conversation messages in the request.

The frontend manages the chat history for each Story. The backend does not store conversations in the database.

History requirements:
- Maximum four messages (two completed user/assistant exchanges).
- Messages must alternate between `user` and `assistant`, starting with `user`.
- Each message must contain nonblank text, maximum 500 characters.
- Messages must be sent oldest first.
- The complete serialized history cannot exceed 2,000 UTF-8 bytes.

Invalid history returns HTTP 422.

The model uses previous messages to understand the conversation, but the original linked Articles remain the factual evidence for every answer.

### Response

```json
{
  "text": "The library opened on Monday.",
  "sources": [
    "https://example.org/local/library-opening"
  ],
  "uncertainty": "Text from 1 of 2 linked articles was supplied. Other sources were not verified.",
  "status": "answered"
}
```

| Field | Description |
|---|---|
| `text` | Nova's answer in the requested language. |
| `sources` | Original URLs of the Articles cited in the answer. |
| `uncertainty` | Information about source coverage or reported differences. |
| `status` | `answered` or `insufficient_information`. |

The backend checks that the model's cited Article IDs and evidence quotes match the stored linked Articles. Only validated source URLs are returned.

This confirms where the evidence came from, but does not independently prove that every statement in the answer is correct.

If Articles report conflicting information, Nova can explain the differences using evidence from at least two distinct Articles. Later updates should not automatically be treated as disagreements.

If the linked Articles cannot support an answer, Nova returns `insufficient_information` instead of making up information.

### Frontend Integration

For the new Story-based frontend:

1. Open Ask Nova using the selected Story ID.
2. Send the question and selected language to the Story endpoint.
3. Include recent completed exchanges in `history` when the user asks a follow-up.
4. Display `text` as Nova's answer and `sources` as clickable links. Use publisher names as labels if the Story's Article metadata is available.
5. Display the `uncertainty` message so users understand which Article content was checked.

Suggested questions, such as "Wait, what happened?", "Why does this matter?", or "Can you explain it more simply?", can be handled through the same endpoint. The frontend does not need a separate API for these actions.

Keep conversation state separate for each Story. The frontend can display the full chat while sending only the latest two completed exchanges to the backend.

### Error Handling and Limitations

| Response | Meaning |
|---|---|
| HTTP 200, `answered` | Nova returned an answer with validated supporting evidence. |
| HTTP 200, `insufficient_information` | The available Articles do not provide enough evidence. |
| HTTP 404 | The Story does not exist or is not published. |
| HTTP 422 | Invalid input or context exceeds the allowed limit. |
| HTTP 503 | AI provider unavailable or its response cannot be validated. |

The current limitations are:

- The combined Article bodies, metadata, and current question are limited to **12,000 UTF-8 bytes**.
- Conversation history has a separate **2,000 UTF-8 byte** limit.
- Article bodies without usable content are excluded. Nova reports how many linked Articles were included.
- The backend does not shorten Article content automatically when it exceeds the limit.
- Chat history is not saved on the backend. If the frontend loses its chat state, the conversation context is also lost.
- Source validation checks evidence quotes and Article IDs, but does not guarantee complete factual accuracy.

## 3. Legacy Article Endpoints

These endpoints belong to the previous Article-based frontend and remain available during the transition to Stories.

| Endpoint | Purpose |
|---|---|
| `POST /ai/ask` | Answer questions using one Article's text. |
| `POST /ai/summarize` | Explain one Article more simply. Used by the existing "Explain it simpler" button. |

Unlike Story-based Ask Nova, these endpoints receive Article text directly from the frontend. They do not retrieve linked Articles from the database or support conversation history.

**For the frontend developer:** Once Ask Nova is fully integrated with Story cards, use `POST /ai/stories/{story_id}/ask` for all questions, including simpler explanations.

After confirming the old Article endpoints are no longer used, they can be removed together with their unused frontend helpers, backend functions, tests, and documentation. Keep any shared code still needed by the new Story endpoint.

Until the migration is complete, leave the old endpoints unchanged to avoid breaking the current frontend.

## 4. Testing

Run the offline AI tests from the repository root:

```powershell
python -m pytest tests/backend/unit/logic/test_ai_service.py tests/backend/unit/logic/test_ollama_client.py tests/backend/unit/presentation/test_ai_routes.py tests/backend/unit/presentation/test_story_ai_routes.py tests/backend/unit/logic/test_fontys_client.py
```

For the existing manual Ollama test, start Ollama and make sure the configured model is installed:

```powershell
python -m tests.backend.manual.ai_ollama_smoke
```

### Current Validation

Story-based Ask Nova has passed 68 targeted offline tests.

A live test was also completed using an existing published Story containing two Articles from NOS and NRC. With Fontys enabled, Nova successfully answered a factual question using the non-primary NRC Article and understood a Dutch follow-up question using conversation history. Both answers returned validated source URLs.

The frontend integration has not yet been tested. English follow-up conversations, conflicting Article reports, and larger Stories still require further validation.

The separate Story Summarization pipeline is not part of this Ask Nova API. It is planned to generate the short summaries displayed on Story cards.
