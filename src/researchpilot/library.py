"""Bounded PDF imports and atomic, versioned local library snapshots."""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import os
import socket
import ssl
import threading
import uuid
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import fitz

from researchpilot.index import build_index
from researchpilot.ingest import ingest_paper
from researchpilot.schema import IndexConfig, PaperMeta

MAX_BYTES = 30 * 1024 * 1024
PDF_LOCK = threading.RLock()


class ImportFailure(ValueError):
    pass


def public_addresses(host: str, port: int):
    try:
        addresses = list(
            dict.fromkeys(a[4][0] for a in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))
        )
    except OSError:
        raise ImportFailure("Không tìm thấy máy chủ của link.") from None
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ImportFailure("Chỉ chấp nhận link Internet công khai, không dùng địa chỉ nội bộ.")
    return addresses


def normalize_url(url: str):
    p = urlsplit(url.strip())
    if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
        raise ImportFailure("Link phải là http/https công khai tới PDF hoặc arXiv.")
    try:
        port = p.port or (443 if p.scheme == "https" else 80)
    except ValueError:
        raise ImportFailure("Port trong link không hợp lệ.") from None
    if port not in {80, 443}:
        raise ImportFailure("Link chỉ hỗ trợ port 80 hoặc 443.")
    if p.hostname.lower() in {"arxiv.org", "www.arxiv.org"} and p.path.startswith("/abs/"):
        p = p._replace(scheme="https", netloc="arxiv.org", path="/pdf/" + p.path[5:], query="")
    return urlunsplit(p._replace(fragment=""))


def download_pdf(url: str):
    """Pin each connection to a validated public IP; validate every redirect."""
    url = normalize_url(url)
    for _ in range(6):
        p = urlsplit(url)
        host = p.hostname.encode("idna").decode()
        port = p.port or (443 if p.scheme == "https" else 80)
        addresses = public_addresses(host, port)
        conn = http.client.HTTPConnection(host, port, timeout=30)
        try:
            sock = socket.create_connection((addresses[0], port), timeout=30)
            if p.scheme == "https":
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
            conn.sock = sock
            target = p.path or "/"
            if p.query:
                target += "?" + p.query
            conn.request(
                "GET",
                target,
                headers={"User-Agent": "ResearchPilot/0.1", "Accept": "application/pdf"},
            )
            response = conn.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                url = normalize_url(urljoin(url, response.getheader("Location", "")))
                continue
            if response.status != 200:
                raise ImportFailure(f"Máy chủ PDF trả lỗi HTTP {response.status}.")
            if int(response.getheader("Content-Length", "0")) > MAX_BYTES:
                raise ImportFailure("PDF vượt giới hạn 30 MB.")
            content = response.read(MAX_BYTES + 1)
            if len(content) > MAX_BYTES:
                raise ImportFailure("PDF vượt giới hạn 30 MB.")
            if not content.startswith(b"%PDF-"):
                raise ImportFailure(
                    "Link chưa trỏ tới PDF. Hãy dùng link PDF trực tiếp hoặc trang arXiv /abs/."
                )
            return content, url
        except (OSError, http.client.HTTPException):
            raise ImportFailure(
                "Không tải được PDF. Kiểm tra link hoặc tải file lên trực tiếp."
            ) from None
        finally:
            conn.close()
    raise ImportFailure("Link chuyển hướng quá nhiều lần.")


def import_pdf(ws, content: bytes, title: str = "", source_url: str = ""):
    if len(content) > MAX_BYTES or not content.startswith(b"%PDF-"):
        raise ImportFailure("Chọn file PDF hợp lệ, tối đa 30 MB.")
    digest = hashlib.sha256(content).hexdigest()
    with ws.library_lock:
        existing = next((p for p in ws.corpus.manifest.papers if p.sha256 == digest), None)
        if existing:
            return {"paper_id": existing.paper_id, "duplicate": True, "workspace": ws.summary()}
        with PDF_LOCK:
            try:
                with fitz.open(stream=content, filetype="pdf") as doc:
                    if doc.needs_pass or not 1 <= len(doc) <= 200:
                        raise ImportFailure("PDF phải có 1–200 trang và không khóa mật khẩu.")
                    texts = [page.get_text() for page in doc]
                    if sum(len(t.strip()) for t in texts) < 80:
                        raise ImportFailure(
                            "PDF không có đủ văn bản đọc được. Bản scan cần OCR trước khi nhập."
                        )
                    detected = (doc.metadata.get("title") or "").strip()
                    if not detected or detected.lower().endswith((".doc", ".docx")):
                        detected = next(
                            (
                                line.strip()
                                for line in texts[0].splitlines()
                                if len(line.strip()) > 12
                            ),
                            "Untitled paper",
                        )
            except ImportFailure:
                raise
            except Exception:
                raise ImportFailure("Không đọc được PDF. File có thể bị hỏng.") from None
        pid = "U" + digest[:12]
        pdf_path = ws.root / "data/papers" / (pid + ".pdf")
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(content)
        stage = ws.root / "artifacts/library_versions" / uuid.uuid4().hex
        stage.mkdir(parents=True)
        paper = PaperMeta(
            paper_id=pid,
            title=(title.strip() or detected)[:300],
            authors=[],
            source_url=source_url or "local-upload",
            local_path=str(pdf_path.relative_to(ws.root)),
            license="unspecified",
            sha256=digest,
        )
        extraction_paper = paper.model_copy(update={"local_path": str(pdf_path)})
        try:
            with PDF_LOCK:
                extraction = ingest_paper(
                    extraction_paper, stage / "extraction", extract_figures_flag=False
                )
            if not extraction.evidence:
                raise ImportFailure("Không trích xuất được văn bản từ PDF.")
            corpus = ws.corpus.model_copy(deep=True)
            corpus.manifest.papers.append(paper)
            corpus.extractions.append(extraction)
            corpus.all_evidence.extend(extraction.evidence)
            cfg = IndexConfig(**ws.config.get("index", {}))
            index = build_index(corpus, cfg, stage / "index")
            (stage / "corpus").mkdir()
            (stage / "corpus/corpus.json").write_text(corpus.model_dump_json(indent=2))
            # Commit pointer last: failed imports never replace the working library.
            pointer = ws.root / "artifacts/library-active.json"
            temp = pointer.with_suffix(".tmp")
            temp.write_text(json.dumps({"path": str(stage.relative_to(ws.root))}))
            os.replace(temp, pointer)
            ws.corpus, ws.index = corpus, index
            ws.papers = {p.paper_id: p for p in corpus.manifest.papers}
            ws.page_cache = None
            return {"paper_id": pid, "duplicate": False, "workspace": ws.summary()}
        except ImportFailure:
            raise
        except Exception:
            raise ImportFailure(
                "Nhập PDF chưa hoàn thành; thư viện trước đó vẫn được giữ nguyên."
            ) from None


def active_directory(root: Path):
    pointer = root / "artifacts/library-active.json"
    if not pointer.exists():
        return root / "artifacts/current"
    folder = (root / json.loads(pointer.read_text())["path"]).resolve()
    if not folder.is_relative_to((root / "artifacts/library_versions").resolve()):
        raise ValueError("Invalid library pointer")
    return folder
