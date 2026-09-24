"""Single-user localhost web workspace. User keys are request-only; an optional local default stays server-side."""

from __future__ import annotations

import argparse
import copy
import json
import logging
import mimetypes
import os
import re
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from researchpilot.library import (
    ImportFailure,
    MAX_BYTES,
    PDF_LOCK,
    active_directory,
    download_pdf,
    import_pdf,
)
from researchpilot.quality import answer_workspace
from researchpilot.compare import compare_papers
from researchpilot.pipeline import ask_question, load_index
from researchpilot.providers.llm import API_ENDPOINTS, ExtractiveGenerator, OpenAIGenerator
from researchpilot.schema import AnswerMode, CorpusData

ASSETS = Path(__file__).parent / "web_assets"


class InputError(ValueError):
    """A safe validation message intended for the user."""


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=3000)
    papers: list[str] = Field(default_factory=list, max_length=20)
    mode: str = "table-rag"
    task: str = "ask"
    provider: str = "auto"
    language: str = "vi"
    model: str = Field(default="", max_length=120)
    api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    top_k: int = Field(default=5, ge=1, le=15)


class Connection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = "auto"
    api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    model: str = Field(default="", max_length=120)


def connect(key: str, model: str, provider: str = "openai") -> dict:
    if not key.strip():
        raise InputError("Hãy nhập API key trước khi kiểm tra kết nối.")
    from openai import OpenAI

    options = {"base_url": API_ENDPOINTS[provider]} if provider != "openai" else {}
    with OpenAI(api_key=key, timeout=20, max_retries=0, **options) as client:
        if provider in {"groq", "gemini"}:
            # Groq model IDs may contain slashes; use the supported list endpoint.
            item = next(
                (
                    m
                    for m in client.models.list().data
                    if m.id.removeprefix("models/") == model.removeprefix("models/")
                ),
                None,
            )
            if item is None:
                raise InputError("Model không tồn tại hoặc key chưa có quyền truy cập model này.")
        else:
            item = client.models.retrieve(model)
    return {
        "ok": True,
        "model": item.id,
        "message": "Key có quyền truy cập model. Chưa thực hiện sinh câu trả lời.",
    }


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()
        local = dotenv_values(self.root / ".env.local")
        self.default_groq_key = SecretStr(
            os.environ.get("GROQ_API_KEY") or local.get("GROQ_API_KEY") or ""
        )
        self.default_groq_model = (
            os.environ.get("GROQ_MODEL") or local.get("GROQ_MODEL") or "openai/gpt-oss-120b"
        )
        self.config = yaml.safe_load((root / "configs/default.yaml").read_text())
        active = active_directory(self.root)
        self.corpus = CorpusData.model_validate_json((active / "corpus/corpus.json").read_text())
        self.index = load_index(active / "index", self.config)
        self.library_lock = threading.RLock()
        self.import_lock = threading.Lock()
        self.page_cache = None
        self.papers = {p.paper_id: p for p in self.corpus.manifest.papers}
        self.lock = threading.BoundedSemaphore(2)

    def summary(self):
        health = {e.paper_id: e for e in self.corpus.extractions}
        counts = Counter(e.paper_id for e in self.corpus.all_evidence)
        return {
            "papers": [
                {
                    "id": p.paper_id,
                    "title": p.title,
                    "authors": p.authors,
                    "year": p.year,
                    "pages": health[p.paper_id].page_count,
                    "evidence_count": counts[p.paper_id],
                    "tables": health[p.paper_id].tables,
                    "extraction_warnings": len(health[p.paper_id].errors),
                    "source_url": p.source_url,
                    "license": p.license,
                }
                for p in self.papers.values()
            ],
            "chunks": self.index.size,
            "pages": sum(e.page_count for e in health.values()),
            "evidence_count": len(self.corpus.all_evidence),
            "default_provider": "groq" if self.default_groq_key.get_secret_value() else "offline",
            "default_model": self.default_groq_model,
            "has_default_groq_key": bool(self.default_groq_key.get_secret_value()),
        }

    def resolve_provider(self, provider, key, model):
        if provider not in {"auto", "offline", "groq", "openai", "gemini"}:
            raise InputError("Cấu hình không được hỗ trợ.")
        key = key.strip()
        if provider == "offline":
            return provider, "", ""
        if not key:
            if self.default_groq_key.get_secret_value():
                return (
                    "groq",
                    self.default_groq_key.get_secret_value(),
                    (model if provider == "groq" and model else self.default_groq_model),
                )
            if provider == "auto":
                return "offline", "", ""
            raise InputError("Nhập API key trong phần Kết nối model.")
        if provider == "auto":
            provider = (
                "groq"
                if key.startswith("gsk_")
                else "gemini"
                if key.startswith("AIza")
                else "openai"
            )
        prefix_provider = (
            "groq"
            if key.startswith("gsk_")
            else "openai"
            if key.startswith("sk-")
            else "gemini"
            if key.startswith("AIza")
            else None
        )
        if prefix_provider and prefix_provider != provider:
            raise InputError("API key không khớp nhà cung cấp đã chọn.")
        return (
            provider,
            key,
            model
            or (
                self.default_groq_model
                if provider == "groq"
                else "gemini-3.8-flash"
                if provider == "gemini"
                else "gpt-4o-mini"
            ),
        )

    def connection(self, request):
        provider, key, model = self.resolve_provider(
            request.provider, request.api_key.get_secret_value(), request.model
        )
        if provider == "offline":
            raise InputError("Nhập API key trong phần Kết nối model.")
        return connect(key, model, provider)

    def paper_path(self, paper_id):
        if paper_id not in self.papers:
            raise InputError("Không tìm thấy tài liệu.")
        path = (self.root / self.papers[paper_id].local_path).resolve()
        if not path.is_relative_to(self.root) or path.suffix.lower() != ".pdf":
            raise InputError("Đường dẫn tài liệu không hợp lệ.")
        return path

    def query(self, request: Query):
        with self.library_lock:
            return self._query(request)

    def _query(self, request: Query):
        if not request.question.strip():
            raise InputError("Hãy nhập câu hỏi của bạn.")
        if request.provider not in {
            "auto",
            "offline",
            "openai",
            "groq",
            "gemini",
        } or request.task not in {
            "ask",
            "compare",
        }:
            raise InputError("Cấu hình không được hỗ trợ.")
        if request.mode not in {"text-rag", "table-rag", "caption-rag"}:
            raise InputError("Chế độ truy xuất không được hỗ trợ.")
        if any(p not in self.papers for p in request.papers) or len(set(request.papers)) != len(
            request.papers
        ):
            raise InputError("Danh sách tài liệu không hợp lệ.")
        if request.task == "compare" and len(request.papers) != 2:
            raise InputError("Chọn đúng hai tài liệu để so sánh.")
        if request.language not in {"vi", "en"}:
            raise InputError("Ngôn ngữ không được hỗ trợ.")
        provider, key, model = self.resolve_provider(
            request.provider, request.api_key.get_secret_value(), request.model
        )
        config = copy.deepcopy(self.config)
        if provider == "groq" and model.startswith("openai/gpt-oss-"):
            config.setdefault("generate", {})["max_tokens"] = 2048
        llm = (
            OpenAIGenerator(model=model, api_key=key, provider=provider, language=request.language)
            if provider != "offline"
            else ExtractiveGenerator()
        )
        try:
            if provider != "offline" and request.mode == "table-rag":
                answer = answer_workspace(self, request, llm)
                flags = []
            elif request.task == "compare":
                result = compare_papers(
                    request.question,
                    *request.papers,
                    self.index,
                    llm,
                    mode=AnswerMode(request.mode),
                    top_k=request.top_k,
                    max_tokens=config.get("generate", {}).get("max_tokens", 512),
                    abstention_threshold=config.get("generate", {}).get(
                        "abstention_threshold", 0.15
                    ),
                )
                answer = result.answer
                flags = result.unsupported_flags
            else:
                answer = ask_question(
                    request.question,
                    AnswerMode(request.mode),
                    self.index,
                    llm,
                    config,
                    request.top_k,
                    set(request.papers) or None,
                )
                flags = []
            # UI does not need model prompts, rejected raw content or server filesystem paths.
            payload = answer.model_dump(
                mode="json", exclude={"prompt", "system_prompt", "raw_response"}
            )
            for result in payload["retrieved_evidence"]:
                result["evidence"].pop("crop_path", None)
            return {"answer": payload, "unsupported": flags, "provider": provider, "model": model}
        finally:
            if provider != "offline":
                llm._client.close()


def safe_error(exc: Exception):
    """Never reflect upstream errors containing credentials or request bodies."""
    name = type(exc).__name__
    if name == "AuthenticationError":
        return 401, "API key không hợp lệ hoặc đã hết hiệu lực. Kiểm tra lại trong Kết nối model."
    if name == "RateLimitError":
        return 429, "Tài khoản API đã chạm giới hạn hoặc hết hạn mức. Kiểm tra billing rồi thử lại."
    if name in {"APIConnectionError", "APITimeoutError"}:
        return 502, "Chưa kết nối được nhà cung cấp API. Kiểm tra mạng và thử lại."
    if name in {"NotFoundError", "PermissionDeniedError"}:
        return 400, "Model không tồn tại hoặc key chưa có quyền truy cập model này."
    if name == "BadRequestError":
        return (
            400,
            "Model không hỗ trợ cấu hình sinh hiện tại. Thử model tương thích Chat Completions như gpt-4o-mini.",
        )
    if isinstance(exc, ImportError):
        return 503, "Thiếu SDK OpenAI. Cài thêm gói API theo hướng dẫn README."
    return 500, "Yêu cầu chưa hoàn thành. Thử lại hoặc kiểm tra pipeline trong Terminal."


def make_handler(workspace: Workspace):
    class Handler(BaseHTTPRequestHandler):
        server_version = "ResearchPilot"

        def log_message(self, *args):
            pass  # No request bodies, keys, questions or provider errors in access logs.

        def allowed(self):
            host = self.headers.get("Host", "")
            port = self.server.server_address[1]
            return host in {f"127.0.0.1:{port}", f"localhost:{port}"}

        def send_body(self, status, body, content_type="application/json; charset=utf-8"):
            if isinstance(body, dict):
                body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'",
            )
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if not self.allowed():
                return self.send_body(403, {"error": "Host không được phép."})
            url = urlsplit(self.path)
            try:
                if url.path == "/api/workspace":
                    return self.send_body(200, workspace.summary())
                match = re.fullmatch(r"/api/papers/([A-Za-z0-9_-]+)/(preview|pdf)", url.path)
                if match:
                    path = workspace.paper_path(match[1])
                    if match[2] == "pdf":
                        return self.send_body(200, path.read_bytes(), "application/pdf")
                    import fitz

                    page = int(parse_qs(url.query).get("page", ["1"])[0])
                    with PDF_LOCK, fitz.open(path) as doc:
                        if not 1 <= page <= len(doc):
                            raise InputError("Số trang không hợp lệ.")
                        # Render at reading resolution, independently from small library covers.
                        width = max(
                            200, min(2400, int(parse_qs(url.query).get("width", ["2000"])[0]))
                        )
                        pdf_page = doc[page - 1]
                        rect = pdf_page.rect
                        scale = min(
                            width / rect.width, (12_000_000 / (rect.width * rect.height)) ** 0.5
                        )
                        pix = pdf_page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                        return self.send_body(200, pix.tobytes("png"), "image/png")
                files = {
                    "/": "index.html",
                    "/app.js": "app.js",
                    "/i18n.js": "i18n.js",
                    "/style.css": "style.css",
                }
                if url.path in files:
                    path = ASSETS / files[url.path]
                    return self.send_body(
                        200, path.read_bytes(), mimetypes.guess_type(path)[0] + "; charset=utf-8"
                    )
                self.send_body(404, {"error": "Không tìm thấy nội dung."})
            except (ValueError, OSError):
                self.send_body(404, {"error": "Không tìm thấy tài liệu hoặc trang yêu cầu."})

        def import_request(self):
            if not workspace.import_lock.acquire(blocking=False):
                return self.send_body(409, {"error": "Đang nhập một paper khác. Hãy đợi hoàn tất."})
            try:
                self.connection.settimeout(90)
                length = int(self.headers.get("Content-Length", "0"))
                path = urlsplit(self.path)
                is_file = path.path == "/api/import/file"
                if not 0 < length <= (MAX_BYTES if is_file else 5000):
                    raise ImportFailure("Chọn file PDF hợp lệ, tối đa 30 MB.")
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ImportFailure("File tải lên chưa đầy đủ. Hãy thử lại.")
                if is_file:
                    title = parse_qs(path.query).get("title", [""])[0][:300]
                    result = import_pdf(workspace, raw, title)
                else:
                    data = json.loads(raw)
                    if (
                        not isinstance(data, dict)
                        or not isinstance(data.get("url"), str)
                        or not isinstance(data.get("title", ""), str)
                    ):
                        raise ImportFailure("Nhập link PDF hoặc arXiv hợp lệ.")
                    content, source = download_pdf(data["url"])
                    result = import_pdf(workspace, content, data.get("title", "")[:300], source)
                self.send_body(200, result)
            except (ImportFailure, ValueError) as exc:
                message = (
                    str(exc) if isinstance(exc, ImportFailure) else "Dữ liệu nhập không hợp lệ."
                )
                self.send_body(400, {"error": message})
            except Exception:
                self.send_body(
                    500, {"error": "Không nhập được paper. Thư viện cũ vẫn được giữ nguyên."}
                )
            finally:
                workspace.import_lock.release()

        def do_POST(self):
            origin = self.headers.get("Origin")
            if (
                not self.allowed()
                or self.headers.get("X-ResearchPilot") != "workspace"
                or origin
                and origin != "http://" + self.headers.get("Host", "")
            ):
                return self.send_body(403, {"error": "Yêu cầu phải đến từ giao diện trên máy này."})
            if urlsplit(self.path).path in {"/api/import/file", "/api/import/url"}:
                return self.import_request()
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.send_body(415, {"error": "Yêu cầu JSON."})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 24000:
                    return self.send_body(413, {"error": "Yêu cầu vượt giới hạn."})
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise InputError()
                request = (
                    Connection.model_validate(data)
                    if self.path == "/api/connection"
                    else Query.model_validate(data)
                )
            except (ValueError, TypeError):
                return self.send_body(
                    400,
                    {"error": "Dữ liệu không hợp lệ. Kiểm tra câu hỏi, model và số bằng chứng."},
                )
            if self.path not in {"/api/ask", "/api/connection"}:
                return self.send_body(404, {"error": "Không tìm thấy chức năng."})
            if not workspace.lock.acquire(blocking=False):
                return self.send_body(
                    429, {"error": "Đang xử lý yêu cầu khác. Vui lòng thử lại sau."}
                )
            try:
                result = (
                    workspace.connection(request)
                    if self.path == "/api/connection"
                    else workspace.query(request)
                )
                self.send_body(200, result)
            except InputError as exc:
                self.send_body(400, {"error": str(exc)})
            except Exception as exc:
                status, message = safe_error(exc)
                self.send_body(status, {"error": message})
            finally:
                workspace.lock.release()

    return Handler


def main():
    parser = argparse.ArgumentParser(description="ResearchPilot local research workspace")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    logging.getLogger("httpx").setLevel(logging.CRITICAL)
    try:
        workspace = Workspace(args.root)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(workspace))
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Cannot start workspace: {exc}\nRun scripts/build_corpus.py first.\n")
    print(f"ResearchPilot → http://127.0.0.1:{args.port}\nCtrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
