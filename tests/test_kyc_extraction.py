from banking_common.kyc import extract_fields_from_text


def test_extract_fields_from_demo_text() -> None:
    fields = extract_fields_from_text("Name: Ayse Yilmaz\nDate of Birth: 1990-01-01\nTC No: 12345678901")

    assert fields["name"] == "Ayse Yilmaz"
    assert fields["date_of_birth"] == "1990-01-01"
    assert fields["tc_no"] == "12345678901"
    assert fields["national_id"] == "12345678901"
    assert fields["confidence"] == 1
