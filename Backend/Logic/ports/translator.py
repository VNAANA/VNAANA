from typing import Protocol


class Translator(Protocol):
    def translate(self, texts: list[str], *, source: str, target: str) -> list[str]:
        """Translate every text, returning them in the same order.

        Raises TranslationUnavailableError when the translation service can't
        be reached, refuses the request, or runs out of quota.
        """
        ...
