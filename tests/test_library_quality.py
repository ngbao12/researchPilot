import json
import threading
from types import SimpleNamespace
from unittest.mock import patch

import fitz
import pytest

from researchpilot.library import (
    ImportFailure,
    active_directory,
    import_pdf,
    normalize_url,
    public_addresses,
)
from researchpilot.quality import checked_claims, rank_pages
from researchpilot.schema import CorpusData, Evidence, ExtractionMethod, Modality


def pdf_bytes(
    text="Research about networks. Our method achieves 81.3 percent accuracy on dataset Alpha. "
    * 4,
):
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(40, 40, 550, 700), text)
        return doc.tobytes()


@pytest.fixture
def library(tmp_path, sample_corpus):
    w = SimpleNamespace(
        root=tmp_path,
        corpus=sample_corpus.model_copy(deep=True),
        config={},
        library_lock=threading.RLock(),
        page_cache=None,
    )
    w.summary = lambda: {"papers": [{"id": p.paper_id} for p in w.corpus.manifest.papers]}
    return w


def test_import_is_persistent_and_duplicate_safe(library):
    content = pdf_bytes()
    result = import_pdf(library, content, "New paper")
    assert not result["duplicate"]
    folder = active_directory(library.root)
    assert (folder / "index/index.faiss").exists()
    saved = CorpusData.model_validate_json((folder / "corpus/corpus.json").read_text())
    assert saved.manifest.papers[-1].title == "New paper"
    assert (library.root / saved.manifest.papers[-1].local_path).read_bytes() == content
    again = import_pdf(library, content)
    assert again["duplicate"] and len(library.corpus.manifest.papers) == 3


def test_failed_index_preserves_library(library):
    first = import_pdf(library, pdf_bytes(), "First")
    old = active_directory(library.root)
    with patch("researchpilot.library.build_index", side_effect=RuntimeError("test failure")):
        with pytest.raises(ImportFailure):
            import_pdf(
                library,
                pdf_bytes("Different valid paper. Evidence about experiments and results. " * 10),
                "Second",
            )
    assert active_directory(library.root) == old
    assert len(library.corpus.manifest.papers) == 3
    assert library.corpus.manifest.papers[-1].paper_id == first["paper_id"]


@pytest.mark.parametrize("data", [b"not pdf", b"%PDF-broken", pdf_bytes("")])
def test_invalid_or_scanned_pdf_rejected(library, data):
    with pytest.raises(ImportFailure):
        import_pdf(library, data)
    assert not (library.root / "artifacts/library-active.json").exists()


def test_normalize_arxiv():
    assert (
        normalize_url("https://arxiv.org/abs/1706.03762v7") == "https://arxiv.org/pdf/1706.03762v7"
    )


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/a.pdf",
        "https://user:pass@example.com/x",
        "https://example.com:8000/x",
    ],
)
def test_unsupported_urls(url):
    with pytest.raises(ImportFailure):
        normalize_url(url)


@pytest.mark.parametrize(
    "ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "192.168.1.1", "::ffff:127.0.0.1"]
)
def test_private_dns_rejected(ip):
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", (ip, 443))]):
        with pytest.raises(ImportFailure):
            public_addresses("anything.example", 443)


def test_mixed_public_private_dns_rejected():
    with patch(
        "socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("1.1.1.1", 443)), (2, 1, 6, "", ("127.0.0.1", 443))],
    ):
        with pytest.raises(ImportFailure):
            public_addresses("anything.example", 443)


def evidence(pid="X", page=1, text="Accuracy is 81.3 percent on Alpha."):
    return Evidence(
        evidence_id=f"page-{pid}-{page}",
        paper_id=pid,
        page=page,
        text=text,
        source_url="local-upload",
        modality=Modality.TEXT,
        extraction_method=ExtractionMethod.PYMUPDF_TEXT,
    )


def test_citations_resolved_by_server_and_quotes_checked():
    refs = {"E1": evidence()}
    valid = {
        "abstain": False,
        "claims": [
            {
                "text": "Accuracy is 81.3%.",
                "sources": [{"id": "E1", "quote": "Accuracy is 81.3 percent on Alpha."}],
            }
        ],
    }
    lines, citations, error = checked_claims(valid, refs)
    assert lines and not error
    assert citations[0].paper_id == "X" and citations[0].page == 1
    valid["claims"][0]["sources"][0]["id"] = "E999"
    assert not checked_claims(valid, refs)[0]
    valid["claims"][0]["sources"][0] = {"id": "E1", "quote": "Accuracy is 99.9 percent on Alpha."}
    assert not checked_claims(valid, refs)[0]


def test_compare_requires_both_sources():
    valid = {
        "abstain": False,
        "claims": [
            {
                "text": "Accuracy",
                "sources": [{"id": "E1", "quote": "Accuracy is 81.3 percent on Alpha."}],
            }
        ],
    }
    assert not checked_claims(valid, {"E1": evidence()}, ["X", "Y"])[0]


def test_page_retrieval_preserves_short_table_row():
    page = evidence(
        text="Table 3. 10-crop testing on validation.\nmodel top-1 top-5\nResNet-152 21.43 5.71"
    )
    unrelated = evidence(page=2, text="Table 4. Single-model results. ResNet-152 19.38 4.49")
    results = rank_pages("Table 3 ResNet-152 top-1 top-5 10-crop", [unrelated, page], {"X"}, 1)
    assert results[0][0].page == 1
    assert "21.43 5.71" in results[0][0].text


def test_page_retrieval_filters_paper():
    assert not rank_pages("accuracy", [evidence()], {"Y"}, 3)


def test_tampered_library_pointer_rejected(tmp_path):
    (tmp_path / "artifacts").mkdir()
    (tmp_path / "artifacts/library-active.json").write_text(json.dumps({"path": "../../escape"}))
    with pytest.raises(ValueError):
        active_directory(tmp_path)


def test_excerpt_budgets_preserve_matches():
    from researchpilot.quality import page_excerpt

    text = (
        "Background text. " * 400
        + "Target metric accuracy 81.3 percent. "
        + "Other section. " * 300
    )
    excerpt = page_excerpt(text, "target metric accuracy", 3000)
    assert "81.3 percent" in excerpt
    assert len(excerpt) < 3100


def test_public_redirect_to_private_is_blocked():
    from researchpilot.library import download_pdf

    response = SimpleNamespace(
        status=302, getheader=lambda name, default="": "http://127.0.0.1/admin"
    )
    connection = SimpleNamespace(
        request=lambda *a, **kw: None, getresponse=lambda: response, close=lambda: None
    )
    with (
        patch(
            "researchpilot.library.public_addresses",
            side_effect=[["1.1.1.1"], ImportFailure("private")],
        ),
        patch("http.client.HTTPConnection", return_value=connection),
        patch("socket.create_connection", return_value=SimpleNamespace()),
    ):
        with pytest.raises(ImportFailure):
            download_pdf("http://example.com/paper.pdf")


def test_answer_exposes_only_verified_quotes_and_matching_terms(sample_evidence):
    from researchpilot.providers.llm import LLMResponse
    from researchpilot.quality import answer_workspace
    from researchpilot.web import Query

    evidence = sample_evidence[0].model_copy(
        update={"text": "Our network achieves 81.3 percent accuracy on dataset Alpha."}
    )
    payload = {
        "abstain": False,
        "claims": [
            {
                "text": "Accuracy is 81.3 percent.",
                "sources": [{"id": "E1", "quote": "81.3 percent accuracy on dataset Alpha."}],
            }
        ],
    }
    llm = SimpleNamespace(
        model_id="test",
        generate=lambda **kw: LLMResponse(text=json.dumps(payload), model_id="test"),
    )
    with patch("researchpilot.quality.pages_for", return_value=[evidence]):
        answer = answer_workspace(
            SimpleNamespace(), Query(question="What accuracy on Alpha?", language="en"), llm
        )
        assert not answer.abstained
        assert answer.support_quotes[evidence.evidence_id] == [
            "81.3 percent accuracy on dataset Alpha."
        ]
        assert answer.evidence_terms[evidence.evidence_id] == ["accuracy", "alpha"]
        payload["claims"][0]["sources"][0]["quote"] = "Invented result with 99.9 percent accuracy."
        rejected = answer_workspace(
            SimpleNamespace(), Query(question="What accuracy on Alpha?", language="en"), llm
        )
        assert rejected.abstained and not rejected.support_quotes


@pytest.mark.parametrize("repair_ok", [True, False])
def test_quote_repair_is_bounded_and_revalidated(sample_evidence, repair_ok):
    from unittest.mock import Mock
    from researchpilot.providers.llm import LLMResponse
    from researchpilot.quality import answer_workspace
    from researchpilot.web import Query

    ev = sample_evidence[0].model_copy(
        update={"text": "The measured accuracy is 81.3 percent on Alpha."}
    )
    bad = {
        "abstain": False,
        "claims": [
            {
                "text": "Accuracy is 81.3 percent.",
                "sources": [{"id": "E1", "quote": "An invented source quote about accuracy."}],
            }
        ],
    }
    good = {
        "abstain": False,
        "claims": [
            {"text": "Accuracy is 81.3 percent.", "sources": [{"id": "E1", "quote": ev.text}]}
        ],
    }
    llm = SimpleNamespace(
        model_id="test",
        generate=Mock(
            side_effect=[
                LLMResponse(text=json.dumps(bad), model_id="test", total_tokens=30),
                LLMResponse(
                    text=json.dumps(good if repair_ok else bad), model_id="test", total_tokens=20
                ),
            ]
        ),
    )
    with patch("researchpilot.quality.pages_for", return_value=[ev]):
        result = answer_workspace(
            SimpleNamespace(), Query(question="Accuracy on Alpha?", language="en"), llm
        )
    assert llm.generate.call_count == 2
    assert result.abstained is not repair_ok
    assert result.usage["total_tokens"] == 50
    assert bool(result.support_quotes) is repair_ok


@pytest.mark.parametrize(
    "question,lookup",
    [
        ("đâu là paper nói về attention", True),
        ("Which of these two papers discusses attention?", True),
        ("Which paper uses attention?", True),
        ("Compare how both papers use residual connections.", False),
        ("So sánh hai paper này khác nhau thế nào?", False),
    ],
)
def test_identify_paper_is_not_substantive_comparison(question, lookup):
    from researchpilot.quality import source_lookup

    assert source_lookup(question) is lookup


@pytest.mark.parametrize(
    "question,abstained",
    [
        ("Which paper discusses attention?", False),
        ("Compare how the two papers use attention.", True),
    ],
)
def test_two_paper_selection_retains_comparison_guard(sample_evidence, question, abstained):
    from researchpilot.quality import answer_workspace
    from researchpilot.providers.llm import LLMResponse
    from researchpilot.web import Query

    ev = sample_evidence[0].model_copy(
        update={"text": "This paper introduces attention for sequence models."}
    )
    payload = {
        "abstain": False,
        "claims": [
            {"text": "This paper discusses attention.", "sources": [{"id": "E1", "quote": ev.text}]}
        ],
    }
    llm = SimpleNamespace(
        model_id="test",
        generate=lambda **kw: LLMResponse(text=json.dumps(payload), model_id="test"),
    )
    with patch("researchpilot.quality.pages_for", return_value=[ev]):
        result = answer_workspace(
            SimpleNamespace(),
            Query(question=question, task="compare", papers=[ev.paper_id, "P99"], language="en"),
            llm,
        )
    assert result.abstained is abstained


def test_passage_selectors_resolve_exact_source_and_reject_wrong_ids(sample_evidence):
    from researchpilot.quality import source_passages

    ev = sample_evidence[0].model_copy(
        update={
            "text": "Residual connections help optimize deeper networks.\nAttention relates sequence elements directly.\n"
        }
    )
    claim = {
        "abstain": False,
        "claims": [{"text": "A supported claim.", "sources": [{"id": "E1", "passage_id": "S1"}]}],
    }
    lines, citations, reason = checked_claims(claim, {"E1": ev})
    assert lines and citations and not reason
    assert source_passages(ev.text)["S1"] == ev.text
    claim["claims"][0]["sources"][0]["passage_id"] = "S99"
    assert not checked_claims(claim, {"E1": ev})[0]
    claim["claims"][0]["sources"][0]["passage_id"] = ["S1"]
    assert not checked_claims(claim, {"E1": ev})[0]


def test_broad_comparison_keeps_both_overviews_and_exports_original_passages(sample_evidence):
    from researchpilot.quality import answer_workspace
    from researchpilot.providers.llm import LLMResponse
    from researchpilot.web import Query
    from unittest.mock import Mock

    a = sample_evidence[0].model_copy(
        update={
            "paper_id": "A",
            "page": 1,
            "evidence_id": "overview-A",
            "text": "We propose residual learning for deep image recognition networks.",
        }
    )
    b = a.model_copy(
        update={
            "paper_id": "B",
            "evidence_id": "overview-B",
            "text": "Our Transformer uses attention for sequence transduction.",
        }
    )
    noise = a.model_copy(
        update={
            "page": 9,
            "evidence_id": "noise",
            "text": "Learn lessons insights overview design " * 80,
        }
    )
    llm = SimpleNamespace(
        model_id="test",
        generate=Mock(
            return_value=LLMResponse(
                text=json.dumps(
                    {
                        "abstain": False,
                        "claims": [
                            {
                                "text": "A lesson from A.",
                                "sources": [{"id": "E1", "passage_id": "S1"}],
                            },
                            {
                                "text": "A lesson from B.",
                                "sources": [{"id": "E3", "passage_id": "S1"}],
                            },
                        ],
                    }
                ),
                model_id="test",
            )
        ),
    )
    with patch("researchpilot.quality.pages_for", return_value=[a, noise, b]):
        answer = answer_workspace(
            SimpleNamespace(),
            Query(
                question="What lessons can we learn from these models?",
                task="compare",
                papers=["A", "B"],
                language="en",
            ),
            llm,
        )
    assert not answer.abstained
    assert answer.support_quotes == {"overview-A": [a.text], "overview-B": [b.text]}
    prompt = json.loads(llm.generate.call_args.kwargs["prompt"])
    assert prompt["sources"][0]["page"] == 1 and prompt["sources"][2]["page"] == 1
    assert "passages" in prompt["sources"][0] and "text" not in prompt["sources"][0]


def test_partial_answer_keeps_supported_claim_and_states_missing_information(sample_evidence):
    from researchpilot.providers.llm import LLMResponse
    from researchpilot.quality import answer_workspace
    from researchpilot.web import Query

    ev = sample_evidence[0].model_copy(update={"text": "The model used 8 P100 GPUs for training."})
    payload = {
        "abstain": False,
        "claims": [
            {"text": "Training used 8 P100 GPUs.", "sources": [{"id": "E1", "passage_id": "S1"}]}
        ],
        "limitations": ["Measured electricity in kWh is not supplied in the excerpts."],
    }
    llm = SimpleNamespace(
        model_id="test",
        generate=lambda **kw: LLMResponse(text=json.dumps(payload), model_id="test"),
    )
    with patch("researchpilot.quality.pages_for", return_value=[ev]):
        answer = answer_workspace(
            SimpleNamespace(), Query(question="How many GPUs and how many kWh?", language="en"), llm
        )
    assert not answer.abstained and len(answer.citations) == 1
    assert answer.limitations == payload["limitations"]
    assert answer.support_quotes[ev.evidence_id] == [ev.text]


def test_missing_information_note_is_separated_without_dropping_supported_answer(sample_evidence):
    from unittest.mock import Mock
    from researchpilot.providers.llm import LLMResponse
    from researchpilot.quality import answer_workspace
    from researchpilot.web import Query

    ev = sample_evidence[0].model_copy(update={"text": "We trained the model using 8 P100 GPUs."})
    supported = {
        "text": "The model used 8 P100 GPUs.",
        "sources": [{"id": "E1", "passage_id": "S1"}],
    }
    bad = {
        "abstain": False,
        "claims": [supported, {"text": "Measured kWh is missing.", "sources": []}],
    }
    repaired = {
        "abstain": False,
        "claims": [supported],
        "limitations": ["Measured kWh is missing."],
    }
    llm = SimpleNamespace(
        model_id="test",
        generate=Mock(
            side_effect=[
                LLMResponse(text=json.dumps(data), model_id="test") for data in [bad, repaired]
            ]
        ),
    )
    with patch("researchpilot.quality.pages_for", return_value=[ev]):
        answer = answer_workspace(
            SimpleNamespace(), Query(question="What GPUs and measured kWh?", language="en"), llm
        )
    assert llm.generate.call_count == 1
    assert not answer.abstained and len(answer.citations) == 1
    assert answer.limitations == repaired["limitations"]


def test_unreferenced_factual_claim_is_not_disguised_as_a_limitation():
    from researchpilot.quality import normalize_answer

    data = {
        "abstain": False,
        "claims": [{"text": "This model achieves 99 percent accuracy.", "sources": []}],
    }
    normalized = normalize_answer(data)
    assert not normalized["limitations"]
    assert checked_claims(normalized, {})[2] == "Claim missing supporting quote"


def test_semantic_selection_can_choose_passage_without_question_keywords(sample_evidence):
    from researchpilot.quality import semantic_pages
    from researchpilot.providers.llm import LLMResponse
    from unittest.mock import Mock

    source = sample_evidence[0].model_copy(update={
        "text": "Identity shortcuts allow signals to propagate directly across layers.",
        "page": 1,
    })
    llm = SimpleNamespace(generate=Mock(return_value=LLMResponse(
        text=json.dumps({"selections": [{"id": "C0", "passage_ids": ["S1"]}]}),
        model_id="test", total_tokens=25,
    )))
    selected, usage, method = semantic_pages(
        "What can I learn from this design?", "lessons", [source],
        [source.paper_id], llm, [],
    )
    assert method == "semantic" and usage == 25
    assert selected[0][0].text == source.text


def test_semantic_selection_rejects_invented_passages(sample_evidence):
    from researchpilot.quality import semantic_pages
    from researchpilot.providers.llm import LLMResponse
    from unittest.mock import Mock

    source = sample_evidence[0]
    fallback = [(source, 1.0)]
    llm = SimpleNamespace(generate=Mock(return_value=LLMResponse(
        text='{"selections":[{"id":"C0","passage_ids":["S999"]}]}', model_id="test",
    )))
    selected, _, method = semantic_pages("lessons", "lessons", [source], [], llm, fallback)
    assert selected == fallback and method == "lexical_fallback"
