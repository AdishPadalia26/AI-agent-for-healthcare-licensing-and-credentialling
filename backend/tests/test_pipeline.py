"""Exercises the real form and PyMuPDF. Only the LLM and OCR services are substituted."""
import pymupdf
import pytest

from credentialing.fields import extract_fields
from credentialing.fill import fill_pdf
from credentialing.llm import LLMError, LocalProvider
from credentialing.mapping import Mapper, fuzzy_match
from credentialing.ocr import DocumentRef, LocalPdfOcr, OcrError, OcrResult, TextractOcr
from credentialing.pipeline import FormError, run_pipeline
from credentialing.retrieval import InMemoryStore, NullStore, ResilientStore, chunk_lines, rrf


def widgets(pdf: bytes) -> dict:
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    values = {w.field_name: w.field_value for page in doc for w in (page.widgets() or [])}
    doc.close()
    return values


def by_name(mapped):
    return {m["field_name"]: m for m in mapped}


@pytest.fixture(scope="module")
def fields(form_bytes):
    return extract_fields(form_bytes)


class StubLLM(LocalProvider):
    name = "stub"

    def __init__(self, answers=None, error=False):
        self.answers, self.error, self.batches = answers or {}, error, []

    def map_fields(self, fields, candidates):
        self.batches.append(fields)
        if self.error:
            raise LLMError("503")
        return [{"id": f["id"], **self.answers[f["field_name"]]} for f in fields if f["field_name"] in self.answers]


def test_field_ids_are_stable(form_bytes):
    assert [f["id"] for f in extract_fields(form_bytes)] == [f["id"] for f in extract_fields(form_bytes)]


def test_labels_no_longer_contain_form_blanks(fields):
    assert len(fields) == 418
    assert all("__" not in (f["label"] or "") for f in fields)


def test_rules_and_normalization_on_real_form(fields, record, settings):
    result = by_name(Mapper(StubLLM(), settings).map(fields, record))
    assert result["1 Name"]["value"] == "David Chen, MD"
    assert result["3 Social Security Number"]["value"] == "567-89-2341"
    assert result["4 NPI National Provider Identifier"]["chosen_key"] == "npi"
    assert result["EMail Address"]["chosen_key"] == "contact_information.email"
    assert result["18 Federal DEARegistrationNo"]["value"] == "BC7834521"
    assert result["16 Languagesother than EnglishSpokenin Your Office by You"]["value"].startswith("English")


def test_anchor_uses_neighbouring_record_entry(fields, record, settings):
    result = by_name(Mapper(StubLLM(), settings).map(fields, record))
    assert result["Date Expires_2"]["chosen_key"] == "licensure[2].expiration_date"
    assert result["Date Expires_2"]["value"] == "04/30/2026"
    assert result["Expiration Date_2"]["chosen_key"] == "professional_liability_insurance.effective_end_date"


def test_llm_cannot_write_invented_values_or_keys(fields, record, settings):
    llm = StubLLM({"Text1": {"chosen_key": "made.up.key", "value": "HALLUCINATED", "confidence": 0.99},
                   "Text2": {"chosen_key": "gender", "value": "HALLUCINATED", "confidence": 0.99}})
    result = by_name(Mapper(llm, settings).map(fields, record))
    assert result["Text1"]["value"] is None
    assert result["Text2"]["value"] == "Male"


def test_llm_never_receives_bookkeeping_keys(fields, record, settings):
    captured = {}

    class Capture(StubLLM):
        def map_fields(self, batch, candidates):
            captured.update(candidates)
            return []

    record.update(_provenance={"x": {"confidence": 1}}, full_text="body", kv_raw={"a": "b"})
    Mapper(Capture(), settings).map(fields, record)
    assert captured and not [k for k in captured if k.startswith(("_prov", "full_text", "kv_raw"))]


def test_gemini_outage_uses_fallback_and_warns(fields, record, settings):
    mapper = Mapper(StubLLM(error=True), settings)
    result = mapper.map(fields, record)
    assert len(result) == 418 and mapper.warnings


def test_fuzzy_fallback_works_on_flat_keys(record):
    from credentialing.schema import mapping_candidates

    candidates = mapping_candidates(record)
    assert fuzzy_match("Citizenship", candidates)[0] == "citizenship"
    assert fuzzy_match("Phone", candidates)[0] == "contact_information.phone"
    assert fuzzy_match("xy", candidates)[0] is None


def test_fill_writes_text_and_checkboxes_on_real_form(form_bytes, fields):
    box = next(f for f in fields if f["field_type"] == "checkbox")
    off_box = [f for f in fields if f["field_type"] == "checkbox"][1]
    text = next(f for f in fields if f["field_name"] == "1 Name")
    mapped = [{**box, "value": "Yes"}, {**off_box, "value": "No"}, {**text, "value": "Test Name"}]
    pdf, report = fill_pdf(form_bytes, mapped)
    assert report.written == 3 and not report.errors
    values = widgets(pdf)
    assert values["1 Name"] == "Test Name"
    assert values[box["field_name"]] not in ("Off", "", None, False)
    assert values[off_box["field_name"]] in ("Off", "", None, False)


def test_unknown_checkbox_value_is_not_toggled(form_bytes, fields):
    box = next(f for f in fields if f["field_type"] == "checkbox")
    pdf, report = fill_pdf(form_bytes, [{**box, "value": "Female"}])
    assert report.written == 0
    assert widgets(pdf)[box["field_name"]] in ("Off", "", None, False)


def test_fill_does_not_write_to_merely_nearby_widget(form_bytes, fields):
    text = next(f for f in fields if f["field_name"] == "1 Name")
    stray = {**text, "field_name": "Not In PDF", "bbox": [v + 20 for v in text["bbox"]], "value": "WRONG"}
    pdf, report = fill_pdf(form_bytes, [stray])
    assert report.written == 0 and "WRONG" not in str(widgets(pdf).values())


def test_end_to_end_local(form_bytes, cv_bytes, settings):
    llm = LocalProvider()
    result = run_pipeline(DocumentRef(data=cv_bytes), form_bytes, LocalPdfOcr(), llm, InMemoryStore(llm.embed), settings, "job")
    assert len(result.mapped) == 418 and not result.report.errors
    auto = [m for m in result.mapped if m["band"] == "auto_fill"]
    values = widgets(result.filled_pdf)
    assert all(values[m["field_name"]] == m["value"] for m in auto if m["field_type"] == "text")
    review = [m for m in result.mapped if m["band"] == "needs_review"]
    assert all(values[m["field_name"]] in ("", None) for m in review if m["field_type"] == "text")


def test_form_without_widgets_rejected(cv_bytes, settings):
    llm = LocalProvider()
    with pytest.raises(FormError):
        run_pipeline(DocumentRef(data=cv_bytes), cv_bytes, LocalPdfOcr(), llm, NullStore(), settings)


class TestRetrieval:
    def store(self):
        return InMemoryStore(LocalProvider().embed)

    def test_rrf_rewards_agreement(self):
        scores = rrf([["a", "b"], ["b", "c"]])
        assert max(scores, key=scores.get) == "b"

    def test_chunks_scoped_by_job(self):
        store = self.store()
        store.index_chunks("one", ["Texas license TX1"])
        store.index_chunks("two", ["Ohio license OH2"])
        assert store.search_chunks("two", "license") == ["Ohio license OH2"]
        store.purge_job("two")
        assert store.search_chunks("two", "license") == []

    def test_chunking(self):
        assert len(chunk_lines(["x" * 300, "y" * 300], 500)) == 2

    def test_confirmed_mapping_changes_result(self, form_bytes, record, settings):
        fields = [f for f in extract_fields(form_bytes) if f["field_name"] == "Name Affiliated wfaxID"]
        store = self.store()
        before = Mapper(StubLLM(), settings, store).map(fields, record)[0]
        assert before["chosen_key"] is None
        store.add_confirmed("Name Affiliated wfax ID", "employment_history[0].employer")
        after = Mapper(StubLLM(), settings, store).map(fields, record)[0]
        assert after["chosen_key"] == "employment_history[0].employer"
        assert after["layer"] == "confirmed"

    def test_retrieved_context_reaches_llm(self, form_bytes, record, settings):
        fields = [f for f in extract_fields(form_bytes) if f["field_name"] == "Text1"]
        store = self.store()
        store.index_chunks("job", ["Education Stanford University School of Medicine"])
        llm = StubLLM()
        Mapper(llm, settings, store).map(fields, record, "job")
        assert llm.batches[0][0]["retrieved_document_text"]

    def test_store_failure_is_degraded_not_fatal(self):
        class Broken(NullStore):
            def search_confirmed(self, query, k=3):
                raise ConnectionError

        store = ResilientStore(Broken())
        assert store.search_confirmed("x") == [] and store.degraded


class FakeTextract:
    def __init__(self, statuses):
        self.statuses, self.calls = list(statuses), 0

    def start_document_analysis(self, **kwargs):
        return {"JobId": "j"}

    def get_document_analysis(self, **kwargs):
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        return {"JobStatus": status, "Blocks": [{"Id": "1", "BlockType": "LINE", "Text": "Hi"}]}


class TestTextractFlow:
    ref = DocumentRef(bucket="b", key="k")

    def test_partial_success_keeps_data_and_warns(self, settings):
        result = TextractOcr(settings, FakeTextract(["PARTIAL_SUCCESS"]), poll_seconds=0).analyze(self.ref)
        assert result.lines == ["Hi"] and result.warnings

    def test_timeout(self, settings):
        with pytest.raises(OcrError):
            TextractOcr(settings, FakeTextract(["IN_PROGRESS"]), poll_seconds=0, timeout_seconds=0.01).analyze(self.ref)

    def test_failed(self, settings):
        with pytest.raises(OcrError):
            TextractOcr(settings, FakeTextract(["FAILED"]), poll_seconds=0).analyze(self.ref)


def test_llm_extraction_failure_keeps_ocr_evidence():
    from credentialing.extract import build_provider_record

    class Down(LocalProvider):
        def extract_provider(self, text):
            raise LLMError("down")

    record = build_provider_record(OcrResult(lines=["Email: a@example.com"]), Down())
    assert record["contact_information"]["email"] == "a@example.com"
    assert record["_warnings"]
