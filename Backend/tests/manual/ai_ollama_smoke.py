"""Manual only: run from repository root with `python -m Backend.tests.manual.ai_ollama_smoke`."""

from Backend.Logic.ai_service import AIModelError
from Backend.Presentation.dependencies import get_ai_service


def main() -> None:
    service = get_ai_service()
    article = "The city opened a new library on Monday. It has two reading rooms."
    try:
        summary = service.summarize(article, "en")
        answer = service.ask(article, "When did the city open the library?", "en")
        unknown = service.ask(article, "Who designed the library?", "en")
    except AIModelError as exc:
        print(f"Smoke test unavailable: {exc}")
        raise SystemExit(1) from exc
    print("summary:", summary)
    print("answer:", answer)
    print("unknown:", unknown)
    if summary["status"] != "answered" or answer["status"] != "answered" or unknown["status"] != "insufficient_information":
        raise SystemExit("Smoke test failed: review model output")


if __name__ == "__main__":
    main()
