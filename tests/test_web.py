"""Local UI boundary tests: routing, credentials, validation and real retrieval."""

import io
import json
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from researchpilot.web import InputError, Query, Workspace, connect, make_handler


@pytest.fixture
def workspace(tmp_path, sample_corpus, built_index):
    ws = Workspace.__new__(Workspace)
    ws.root = tmp_path
    ws.default_groq_key = SecretStr("")
    ws.default_groq_model = "test-groq-model"
    ws.config = {"generate": {"abstention_threshold": 0}}
    ws.corpus = sample_corpus
    ws.index = built_index
    ws.papers = {p.paper_id: p for p in sample_corpus.manifest.papers}
    ws.lock = threading.BoundedSemaphore(2)
    ws.library_lock = threading.RLock()
    ws.import_lock = threading.Lock()
    ws.page_cache = None
    return ws


def request(ws, path, body=None, host="127.0.0.1:8765", origin=None, marker=True):
    """Drive the actual HTTP handler over in-memory streams without binding ports."""
    output = io.BytesIO()
    headers = f"Host: {host}\r\n"
    if origin:
        headers += f"Origin: {origin}\r\n"
    if marker:
        headers += "X-ResearchPilot: workspace\r\n"
    raw = b""
    if body is not None:
        raw = json.dumps(body).encode()
        headers += f"Content-Type: application/json\r\nContent-Length: {len(raw)}\r\n"
    payload = (
        f"{'POST' if body is not None else 'GET'} {path} HTTP/1.0\r\n{headers}\r\n".encode() + raw
    )

    class Socket:
        def settimeout(self, value):
            pass

        def makefile(self, mode, *args):
            return io.BytesIO(payload) if mode == "rb" else output

    handler = make_handler(ws)
    handler.wbufsize = 1024

    # BaseHTTPRequestHandler closes wfile after handling; retain bytes for assertions.
    class Capture(io.BytesIO):
        def close(self):
            pass

    output = Capture()
    handler(Socket(), ("127.0.0.1", 12345), SimpleNamespace(server_address=("127.0.0.1", 8765)))
    head, body = output.getvalue().split(b"\r\n\r\n", 1)
    return int(head.split()[1]), head.decode(), body


def test_workspace_and_assets(workspace):
    status, headers, body = request(workspace, "/api/workspace")
    assert status == 200
    assert len(json.loads(body)["papers"]) == 2
    assert "Cache-Control: no-store" in headers
    for path in ("/", "/app.js", "/style.css"):
        assert request(workspace, path)[0] == 200
    assert request(workspace, "/../../pyproject.toml")[0] == 404


def test_offline_ask_filters_sources_and_omits_internal_data(workspace):
    status, _, raw = request(
        workspace,
        "/api/ask",
        {"question": "depthwise separable convolutions computational cost", "papers": ["P01"]},
    )
    assert status == 200
    answer = json.loads(raw)["answer"]
    assert answer["retrieved_evidence"]
    assert all(r["evidence"]["paper_id"] == "P01" for r in answer["retrieved_evidence"])
    assert "prompt" not in answer and "raw_response" not in answer
    assert all("crop_path" not in r["evidence"] for r in answer["retrieved_evidence"])


@pytest.mark.parametrize(
    "overrides", [{"host": "evil.test:8765"}, {"origin": "https://evil.test"}, {"marker": False}]
)
def test_rejects_foreign_browser_requests(workspace, overrides):
    assert request(workspace, "/api/ask", {"question": "hello"}, **overrides)[0] == 403


@pytest.mark.parametrize(
    "changes",
    [
        {"question": " "},
        {"provider": "unknown"},
        {"provider": "openai"},
        {"task": "compare", "papers": ["P01"]},
        {"papers": ["P99"]},
        {"papers": ["P01", "P01"]},
        {"top_k": 100},
        {"mode": "unknown"},
    ],
)
def test_invalid_query(workspace, changes):
    assert request(workspace, "/api/ask", {"question": "question", **changes})[0] == 400


def test_provider_error_never_echoes_secret(workspace, monkeypatch):
    def broken(_):
        raise ValueError("upstream request api_key=sk-secret-test")

    monkeypatch.setattr(workspace, "query", broken)
    status, _, body = request(
        workspace, "/api/ask", {"question": "question", "api_key": "sk-secret-test"}
    )
    assert status == 500
    assert b"sk-secret-test" not in body


def test_openai_key_is_explicit_and_client_closed(workspace):
    from researchpilot.providers.llm import ExtractiveGenerator

    generator = ExtractiveGenerator()
    generator._client = SimpleNamespace(close=lambda: None)
    with (
        patch("researchpilot.web.OpenAIGenerator", return_value=generator) as factory,
        patch.object(generator._client, "close") as close,
    ):
        workspace.query(
            Query(
                question="depthwise convolutions",
                mode="text-rag",
                provider="openai",
                api_key=SecretStr("test-only-key"),
                model="test-model",
            )
        )
        factory.assert_called_once_with(
            model="test-model", api_key="test-only-key", provider="openai", language="vi"
        )
        close.assert_called_once()
    assert "api_key" not in workspace.config


def test_connection_check_does_not_generate():
    client = SimpleNamespace(
        models=SimpleNamespace(retrieve=lambda model: SimpleNamespace(id=model))
    )
    constructor = MagicMock()
    with patch.dict("sys.modules", {"openai": SimpleNamespace(OpenAI=constructor)}):
        constructor.return_value.__enter__.return_value = client
        assert connect("test-only-key", "test-model")["model"] == "test-model"
        constructor.assert_called_once_with(api_key="test-only-key", timeout=20, max_retries=0)
    with pytest.raises(InputError):
        connect("", "test-model")


def test_pdf_path_cannot_escape_project(workspace):
    workspace.papers["P01"].local_path = "../private.pdf"
    with pytest.raises(InputError):
        workspace.paper_path("P01")


def test_busy_server(workspace):
    workspace.lock.acquire()
    workspace.lock.acquire()
    assert request(workspace, "/api/ask", {"question": "question"})[0] == 429


def test_groq_default_never_returned_to_browser(workspace):
    workspace.default_groq_key = SecretStr("gsk_test-default")
    status, _, body = request(workspace, "/api/workspace")
    assert status == 200
    assert json.loads(body)["default_provider"] == "groq"
    assert json.loads(body)["has_default_groq_key"] is True
    assert b"gsk_test-default" not in body
    assert request(workspace, "/.env.local")[0] == 404


@pytest.mark.parametrize(
    "provider,key,model,expected",
    [
        ("auto", "", "", ("groq", "gsk_test-default", "test-groq-model")),
        ("openai", "", "gpt-4o-mini", ("groq", "gsk_test-default", "test-groq-model")),
        ("groq", "", "custom-model", ("groq", "gsk_test-default", "custom-model")),
        ("groq", "gsk_custom", "custom", ("groq", "gsk_custom", "custom")),
        ("openai", "sk-custom", "custom", ("openai", "sk-custom", "custom")),
        ("auto", "gsk_custom", "", ("groq", "gsk_custom", "test-groq-model")),
        ("offline", "", "", ("offline", "", "")),
    ],
)
def test_provider_precedence(workspace, provider, key, model, expected):
    workspace.default_groq_key = SecretStr("gsk_test-default")
    assert workspace.resolve_provider(provider, key, model) == expected


@pytest.mark.parametrize("provider,key", [("openai", "gsk_test"), ("groq", "sk-test")])
def test_key_cannot_be_sent_to_wrong_provider(workspace, provider, key):
    with pytest.raises(InputError):
        workspace.resolve_provider(provider, key, "")


def test_groq_connection_uses_default_and_fixed_endpoint(workspace):
    workspace.default_groq_key = SecretStr("gsk_test-default")
    from researchpilot.web import Connection

    with patch("researchpilot.web.connect", return_value={"ok": True}) as connect_mock:
        assert workspace.connection(Connection()) == {"ok": True}
        connect_mock.assert_called_once_with("gsk_test-default", "test-groq-model", "groq")


def test_groq_generator_model_label_and_answer_language():
    from researchpilot.providers.llm import OpenAIGenerator

    constructor = MagicMock()
    response = constructor.return_value.chat.completions.create.return_value
    response.choices = [
        SimpleNamespace(message=SimpleNamespace(content="Answer"), finish_reason="stop")
    ]
    response.usage = None
    response.model = "groq-test"
    response.model_dump.return_value = {}
    with patch.dict("sys.modules", {"openai": SimpleNamespace(OpenAI=constructor)}):
        llm = OpenAIGenerator(model="groq-test", api_key="gsk_test", provider="groq", language="en")
        result = llm.generate("question", "system")
        assert llm.model_id == result.model_id == "groq/groq-test"
        assert constructor.call_args.kwargs["base_url"] == "https://api.groq.com/openai/v1"
        assert (
            "English"
            in constructor.return_value.chat.completions.create.call_args.kwargs["messages"][0][
                "content"
            ]
        )


@pytest.mark.parametrize(
    "citation,accepted",
    [
        ("【P01, p.1, ev-P01-p1-t0】", True),
        ("【P01, p.99, ev-P01-p1-t0】", False),
        ("【P02, p.1, ev-P01-p1-t0】", False),
    ],
)
def test_typographic_citations_still_validate_provenance(sample_evidence, citation, accepted):
    from researchpilot.generate import generate_answer
    from researchpilot.providers.llm import LLMResponse
    from researchpilot.schema import AnswerMode, RetrievalResult

    response = LLMResponse(text="Computation is reduced " + citation + ".", model_id="test")
    llm = SimpleNamespace(generate=lambda **kwargs: response, model_id="test")
    answer = generate_answer(
        "computation?",
        [RetrievalResult(evidence=sample_evidence[0], score=1, rank=1)],
        llm,
        AnswerMode.TABLE_RAG,
    )
    assert answer.abstained is not accepted
    assert answer.raw_response == response.text


def test_import_url_http_route(workspace):
    with (
        patch(
            "researchpilot.web.download_pdf",
            return_value=(b"%PDF-test", "https://example.com/p.pdf"),
        ),
        patch(
            "researchpilot.web.import_pdf", return_value={"paper_id": "U1", "duplicate": False}
        ) as importer,
    ):
        status, _, body = request(
            workspace, "/api/import/url", {"url": "https://example.com/p.pdf", "title": "Title"}
        )
        assert status == 200 and json.loads(body)["paper_id"] == "U1"
        importer.assert_called_once_with(
            workspace, b"%PDF-test", "Title", "https://example.com/p.pdf"
        )
    assert (
        request(
            workspace,
            "/api/import/url",
            {"url": "http://example.com"},
            origin="https://evil.example",
        )[0]
        == 403
    )


def test_import_validation_and_busy_state(workspace):
    assert request(workspace, "/api/import/url", {"url": 42})[0] == 400
    workspace.import_lock.acquire()
    assert request(workspace, "/api/import/url", {"url": "http://example.com"})[0] == 409


def test_gemini_routing_and_no_key_fallback(workspace):
    workspace.default_groq_key = SecretStr("gsk_test-default")
    assert workspace.resolve_provider("auto", "AIza-test", "") == (
        "gemini",
        "AIza-test",
        "gemini-3.8-flash",
    )
    assert workspace.resolve_provider("gemini", "", "gemini-custom")[0] == "groq"
    with pytest.raises(InputError):
        workspace.resolve_provider("openai", "AIza-test", "")
    with pytest.raises(InputError):
        workspace.resolve_provider("gemini", "gsk_test", "")


def test_gemini_generator_endpoint_json_and_supported_options():
    from researchpilot.providers.llm import OpenAIGenerator

    constructor = MagicMock()
    response = constructor.return_value.chat.completions.create.return_value
    response.choices = [
        SimpleNamespace(message=SimpleNamespace(content="{}"), finish_reason="stop")
    ]
    response.usage = None
    response.model = "gemini-test"
    response.model_dump.return_value = {}
    with patch.dict("sys.modules", {"openai": SimpleNamespace(OpenAI=constructor)}):
        llm = OpenAIGenerator(model="gemini-test", api_key="AIza-test", provider="gemini")
        llm._json_mode = True
        result = llm.generate("question", "system", seed=42)
    assert (
        constructor.call_args.kwargs["base_url"]
        == "https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    kwargs = constructor.return_value.chat.completions.create.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["reasoning_effort"] == "low" and "seed" not in kwargs
    assert result.model_id == "gemini/gemini-test"


def test_gemini_connection_accepts_models_prefix():
    from researchpilot.web import connect

    constructor = MagicMock()
    constructor.return_value.__enter__.return_value.models.list.return_value.data = [
        SimpleNamespace(id="models/gemini-test")
    ]
    with patch.dict("sys.modules", {"openai": SimpleNamespace(OpenAI=constructor)}):
        assert connect("AIza-test", "gemini-test", "gemini")["ok"]
    assert (
        constructor.call_args.kwargs["base_url"]
        == "https://generativelanguage.googleapis.com/v1beta/openai/"
    )


def test_pdf_reading_preview_is_sharp_but_covers_stay_small(workspace):
    import fitz

    path = workspace.root / "preview.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((60, 60), "Table 3: attention heads = 8")
        doc.save(path)
    with patch.object(workspace, "paper_path", return_value=path):
        status, _, body = request(workspace, "/api/papers/P01/preview?page=1")
        assert status == 200
        assert fitz.Pixmap(body).width >= 2000
        status, _, body = request(workspace, "/api/papers/P01/preview?page=1&width=240")
        assert status == 200 and fitz.Pixmap(body).width <= 241
        assert request(workspace, "/api/papers/P01/preview?page=2")[0] == 404


def test_gemini_invalid_key_is_not_misreported_as_model_configuration():
    from researchpilot.web import safe_error

    error = type("BadRequestError", (Exception,), {})()
    error.body = {"error": {"status": "INVALID_ARGUMENT", "message": "Please pass a valid API key"}}
    status, message = safe_error(error)
    assert status == 401 and "API key không hợp lệ" in message


def test_rate_limit_does_not_assume_billing_is_exhausted():
    from researchpilot.web import safe_error

    error = type("RateLimitError", (Exception,), {})()
    status, message = safe_error(error)
    assert status == 429 and "không nhất thiết là hết tiền" in message


def test_gemini_empty_response_and_nullable_usage():
    from researchpilot.providers.llm import OpenAIGenerator, ProviderResponseError

    constructor = MagicMock()
    response = constructor.return_value.chat.completions.create.return_value
    response.choices = []
    with patch.dict("sys.modules", {"openai": SimpleNamespace(OpenAI=constructor)}):
        llm = OpenAIGenerator(model="gemini-test", api_key="AIza-test", provider="gemini")
        with pytest.raises(ProviderResponseError):
            llm.generate("question")
        response.choices = [SimpleNamespace(message=SimpleNamespace(content="{}"), finish_reason="stop")]
        response.usage = SimpleNamespace(total_tokens=None, prompt_tokens=None, completion_tokens=None)
        response.model = None
        response.model_dump.return_value = {}
        result = llm.generate("question")
        assert result.total_tokens == 0
        assert result.model_version == "gemini-test"


def test_provider_response_error_is_actionable():
    from researchpilot.providers.llm import ProviderResponseError
    from researchpilot.web import safe_error

    status, message = safe_error(ProviderResponseError("sensitive upstream details"))
    assert status == 502
    assert "sensitive" not in message
    assert "model" in message.lower()
