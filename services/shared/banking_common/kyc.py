import re
from typing import Any


def extract_fields_from_text(text: str, nlp: Any | None = None) -> dict:
    person = None
    if nlp is not None:
        doc = nlp(text)
        person = next((ent.text for ent in doc.ents if ent.label_ in {"PERSON", "PER"}), None)

    date_match = re.search(r"\b(\d{4}-\d{2}-\d{2}|\d{2}[./-]\d{2}[./-]\d{4})\b", text)
    tc_match = re.search(r"\b[1-9]\d{10}\b", text)
    name_match = re.search(r"name\s*:\s*(.+)", text, re.IGNORECASE)

    fields = {
        "name": person or (name_match.group(1).strip() if name_match else None),
        "date_of_birth": date_match.group(1) if date_match else None,
        "tc_no": tc_match.group(0) if tc_match else None,
    }
    present = sum(1 for value in fields.values() if value)
    fields["national_id"] = fields["tc_no"]
    fields["confidence"] = round(present / 3, 2)
    return fields
