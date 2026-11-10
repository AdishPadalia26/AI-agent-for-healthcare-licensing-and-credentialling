import pytest

from credentialing.extract import reconcile
from credentialing.fields import clean_field_name
from credentialing.llm import redact_candidates
from credentialing.normalize import normalize_date, normalize_value, split_name, value_kind
from credentialing.ocr import parse_textract_pages
from credentialing.schema import coerce_record, mapping_candidates
from credentialing.validators import is_dob, is_email, is_npi, is_phone


@pytest.mark.parametrize("value", ["(202) 555-0148", "202-555-0148", "2025550148", "+1 202 555 0148"])
def test_phone_formats_accepted(value):
    assert is_phone(value)


@pytest.mark.parametrize("value", ["555-0148", "12345", None, ["x"], 3.5])
def test_phone_rejects_without_raising(value):
    assert not is_phone(value)


def test_npi_requires_ten_digits_and_luhn():
    assert is_npi("1234567893")
    assert is_npi(1234567893)
    assert not is_npi("1234567890")
    assert not is_npi("12345678")
    assert not is_npi("123456789012345")


def test_iso_date_of_birth_accepted():
    assert is_dob("1985-03-12")


def test_non_string_values_do_not_raise():
    assert not is_email(["a"])
    assert not is_dob({"x": 1})


@pytest.mark.parametrize(
    "name,first,middle,last",
    [
        ("Sanjay Rajiv Mehra, MD", "Sanjay", "Rajiv", "Mehra"),
        ("Ananya Suresh, MD", "Ananya", "", "Suresh"),
        ("Dr. Jane Example", "Jane", "", "Example"),
        ("Example, Jane Q", "Jane", "Q", "Example"),
        ("Dr. Nia Mensah, MD, FACP", "Nia", "", "Mensah"),
    ],
)
def test_split_name(name, first, middle, last):
    assert split_name(name) == {"first": first, "middle": middle, "last": last}


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2019", "2019"),
        ("06/2008", "06/2008"),
        ("June 2015", "06/2015"),
        ("Present", "Present"),
        ("March 12, 1985", "03/12/1985"),
        ("1985-03-12", "03/12/1985"),
        ("06/17/78", "06/17/1978"),
    ],
)
def test_dates_never_invent_precision(raw, expected):
    assert normalize_date(raw) == expected


def test_normalize_by_descriptor():
    assert normalize_value("Telephone", "2025550148") == "(202) 555-0148"
    assert normalize_value("Social Security Number", "123456789") == "123-45-6789"
    assert normalize_value("Place of Birth", "New Delhi 110029") == "New Delhi 110029"
    assert normalize_value("Middle School Attended", "Lincoln Middle School") == "Lincoln Middle School"
    assert normalize_value("Malpractice history", True) == "Yes"


def test_key_decides_format_when_descriptor_is_generic():
    assert value_kind("Text12", "licensure[0].expiration_date") == "date"
    assert value_kind("Text13", "peer_references[1].phone") == "phone"


def test_clean_field_name():
    assert clean_field_name("4 NPI National Provider Identifier") == "NPI National Provider Identifier"
    assert clean_field_name("5 Place ofBirth") == "Place of Birth"
    assert clean_field_name("Email_3") == "Email"
    assert clean_field_name("Text42") is None
    assert clean_field_name("Check Box98") is None


def test_candidates_exclude_bookkeeping_and_nulls():
    record = coerce_record({"npi": "1", "ssn": None})
    record.update(_provenance={"x": 1}, full_text="t", kv_raw={"a": "b"}, tables=[[["c"]]])
    keys = mapping_candidates(record)
    assert keys == {"npi": "1"}


def test_coerce_handles_llm_shapes():
    record = coerce_record({"npi": 1780953210, "contact_information": "1 Main St", "licensure": {"state": "TX"}})
    assert record["npi"] == "1780953210"
    assert record["contact_information"]["address"] == "1 Main St"
    assert record["licensure"] == [{"state": "TX"}]


def test_identifiers_redacted_before_mapping_call():
    payload = redact_candidates({"ssn": "123-45-6789", "date_of_birth": "1/1/1980", "full_name": "A B"})
    values = {p["key"]: p["value"] for p in payload}
    assert values == {"ssn": "[redacted]", "date_of_birth": "[redacted]", "full_name": "A B"}


class TestReconcile:
    def test_agreement_is_highest(self):
        assert reconcile("(202) 555-0148", "202.555.0148", is_phone)[1]["status"] == "agreed"

    def test_conflict_goes_low(self):
        value, provenance = reconcile("a@x.com", "b@x.com", is_email)
        assert value == "a@x.com"
        assert provenance["status"] == "conflict"
        assert provenance["confidence"] < 0.8

    def test_invalid_llm_falls_back_to_ocr(self):
        value, provenance = reconcile("nope", "a@x.com", is_email)
        assert value == "a@x.com"
        assert provenance["source"] == "ocr"

    def test_missing(self):
        assert reconcile(None, None)[1]["status"] == "missing"


def test_textract_parsing():
    blocks = [
        {"Id": "1", "BlockType": "LINE", "Text": "Hello"},
        {"Id": "w1", "BlockType": "WORD", "Text": "Name"},
        {"Id": "w2", "BlockType": "WORD", "Text": "Jane"},
        {"Id": "k", "BlockType": "KEY_VALUE_SET", "EntityTypes": ["KEY"],
         "Relationships": [{"Type": "CHILD", "Ids": ["w1"]}, {"Type": "VALUE", "Ids": ["v"]}]},
        {"Id": "v", "BlockType": "KEY_VALUE_SET", "EntityTypes": ["VALUE"],
         "Relationships": [{"Type": "CHILD", "Ids": ["w2"]}]},
    ]
    result = parse_textract_pages([{"Blocks": blocks}])
    assert result.lines == ["Hello"]
    assert result.kv == {"Name": "Jane"}
