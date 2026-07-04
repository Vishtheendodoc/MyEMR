"""English → Kannada prescription instruction phrases."""

import re

# Longest phrases first when applying replacements
PHRASE_MAP: list[tuple[str, str]] = [
    ("take with plenty of water", "ಹೆಚ್ಚು ನೀರಿನ ಜೊತೆ ತಿನಸಿ"),
    ("take with water", "ನೀರಿನ ಜೊತೆ ತಿನಸಿ"),
    ("do not skip doses", "ಡೋಸ್ ಬಿಟ್ಟುಬಿಡಬೇಡಿ"),
    ("do not skip", "ಬಿಟ್ಟುಬಿಡಬೇಡಿ"),
    ("take after meals", "ಊಟದ ನಂತರ ತಿನಸಿ"),
    ("take before meals", "ಊಟಕ್ಕೆ ಮುನ್ನ ತಿನಸಿ"),
    ("take after food", "ಊಟದ ನಂತರ ತಿನಸಿ"),
    ("take before food", "ಊಟಕ್ಕೆ ಮುನ್ನ ತಿನಸಿ"),
    ("take with food", "ಊಟದ ಜೊತೆ ತಿನಸಿ"),
    ("after meals", "ಊಟದ ನಂತರ"),
    ("before meals", "ಊಟಕ್ಕೆ ಮುನ್ನ"),
    ("after food", "ಊಟದ ನಂತರ"),
    ("before food", "ಊಟಕ್ಕೆ ಮುನ್ನ"),
    ("with food", "ಊಟದ ಜೊತೆ"),
    ("empty stomach", "ಖಾಲಿ ಹೊಟ್ಟೆಯಲ್ಲಿ"),
    ("at bedtime", "ಮಲಗುವ ಮೊದಲು"),
    ("before breakfast", "ಬೆಳಗಿನ ಊಟಕ್ಕೆ ಮುನ್ನ"),
    ("after breakfast", "ಬೆಳಗಿನ ಊಟದ ನಂತರ"),
    ("before dinner", "ರಾತ್ರಿ ಊಟಕ್ಕೆ ಮುನ್ನ"),
    ("after dinner", "ರಾತ್ರಿ ಊಟದ ನಂತರ"),
    ("as needed", "ಅಗತ್ಯವಿದ್ದಾಗ"),
    ("as directed", "ವೈದ್ಯರ ಸೂಚನೆಯಂತೆ"),
    ("once daily", "ದಿನಕ್ಕೆ ಒಂದು ಬಾರಿ"),
    ("twice daily", "ದಿನಕ್ಕೆ ಎರಡು ಬಾರಿ"),
    ("three times daily", "ದಿನಕ್ಕೆ ಮೂರು ಬಾರಿ"),
    ("four times daily", "ದಿನಕ್ಕೆ ನಾಲ್ಕು ಬಾರಿ"),
    ("every day", "ಪ್ರತಿದಿನ"),
    ("every week", "ಪ್ರತಿ ವಾರ"),
    ("every month", "ಪ್ರತಿ ತಿಂಗಳು"),
    ("monitor blood sugar", "ರಕ್ತದಲ್ಲಿನ ಸಕ್ಕರೆ ಪರೀಕ್ಷಿಸಿ"),
    ("check blood sugar", "ರಕ್ತದಲ್ಲಿನ ಸಕ್ಕರೆ ಪರೀಕ್ಷಿಸಿ"),
    ("avoid alcohol", "ಮದ್ಯಪಾನ ತಪ್ಪಿಸಿ"),
    ("avoid driving", "ವಾಹನ ಚಲಾಯಿಸುವುದನ್ನು ತಪ್ಪಿಸಿ"),
    ("continue same dose", "ಅದೇ ಡೋಸ್ ಮುಂದುವರಿಸಿ"),
    ("if hypoglycemia", "ರಕ್ತದಲ್ಲಿನ ಸಕ್ಕರೆ ಕಡಿಮೆಯಾದರೆ"),
    ("if symptoms persist", "ಲಕ್ಷಣಗಳು ಮುಂದುವರಿದರೆ"),
    ("review after", "ನಂತರ ಪರೀಕ್ಷೆ"),
    ("take regularly", "ನಿಯಮಿತವಾಗಿ ತಿನಸಿ"),
    ("complete the course", "ಪೂರ್ಣ ಕೋರ್ಸ್ ಮುಗಿಸಿ"),
    ("with meals", "ಊಟದ ಜೊತೆ"),
    ("without food", "ಊಟ ಇಲ್ಲದೆ"),
    ("in the morning", "ಬೆಳಿಗ್ಗೆ"),
    ("in the afternoon", "ಮಧ್ಯಾಹ್ನ"),
    ("at night", "ರಾತ್ರಿ"),
    ("weekly once", "ವಾರಕ್ಕೆ ಒಂದು ಬಾರಿ"),
    ("monthly once", "ತಿಂಗಳಿಗೆ ಒಂದು ಬಾರಿ"),
    ("take", "ತಿನಸಿ"),
    ("tablet", "ಗೋಳಿ"),
    ("tablets", "ಗೋಳಿಗಳು"),
    ("capsule", "ಕ್ಯಾಪ್ಸುಲ್"),
    ("capsules", "ಕ್ಯಾಪ್ಸುಲ್‌ಗಳು"),
    ("days", "ದಿನಗಳು"),
    ("weeks", "ವಾರಗಳು"),
    ("months", "ತಿಂಗಳುಗಳು"),
]

MEAL_TIMING_MAP = {
    "Before Food": "ಊಟಕ್ಕೆ ಮುನ್ನ",
    "After Food": "ಊಟದ ನಂತರ",
    "With Food": "ಊಟದ ಜೊತೆ",
    "Empty Stomach": "ಖಾಲಿ ಹೊಟ್ಟೆಯಲ್ಲಿ",
    "Bedtime": "ಮಲಗುವ ಮೊದಲು",
}


def contains_kannada(text: str) -> bool:
    return any("\u0c80" <= ch <= "\u0cff" for ch in text)


def translate_to_kannada(text: str) -> str:
    if not text or contains_kannada(text):
        return text.strip()

    result = text.strip()
    for english, kannada in PHRASE_MAP:
        pattern = re.compile(re.escape(english), re.IGNORECASE)
        result = pattern.sub(kannada, result)

    # Clean duplicate spaces
    result = re.sub(r"\s+", " ", result).strip()
    return result


def format_bilingual_instructions(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None
    if contains_kannada(cleaned):
        return cleaned

    kannada = translate_to_kannada(cleaned)
    if not kannada or kannada.lower() == cleaned.lower():
        return cleaned

    return f"{cleaned} ({kannada})"


def translate_meal_timing(label: str | None) -> str | None:
    if not label:
        return None
    return MEAL_TIMING_MAP.get(label.strip(), translate_to_kannada(label))
