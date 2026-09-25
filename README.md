# ResearchPilot

A local web workspace and CLI for extracting scientific PDFs, retrieving source evidence and producing page-cited answers. The default works offline after dependency installation: deterministic lexical retrieval plus **literal evidence quotations**, not a pretrained LLM. Mock providers are separate test doubles.

**Status:** tested engineering MVP with four local papers and 12 draft questions. This is not a completed 10–20-paper research study. Correctness and semantic citation support are **not measured** until independent human judgments are supplied. See [requirements status](reports/requirements_status.md) and [measured report](reports/experiment_report.md).

## Setup (Python 3.11)

```bash
python3.11 -m venv .venv311
source .venv311/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps .
pytest -q
```

`requirements.lock` pins the complete tested offline/dev environment. Optional API and semantic embedding dependencies are outside this lock and must be recorded separately for a research run. No API key is needed for the default pipeline. Existing Python 3.9 `.venv` directories should not be used. A regular wheel installation is used because macOS can mark editable `.pth` files hidden, causing Python to skip them. Reinstall with `python -m pip install --no-deps .` after editing source.

## Giao diện web

Sau khi cài đặt và có corpus/index tại `artifacts/current`, chạy từ thư mục dự án:

```bash
.venv311/bin/researchpilot-web
# Mở http://127.0.0.1:8765
# Có thể chọn cổng: .venv311/bin/researchpilot-web --port 8766
```

Giao diện có thư viện PDF, chọn tài liệu, hỏi/so sánh hai paper, trích dẫn mở đúng trang,
sổ bằng chứng, lịch sử trong tab và xuất ghi chú Markdown. Chế độ offline hoạt động
không cần key; thử các câu hỏi mẫu bằng tiếng Anh để khớp với nội dung paper.

Chọn **VI / EN** ở thanh trên cùng để đổi ngôn ngữ. Giao diện ghi nhớ lựa chọn
ngôn ngữ; câu trả lời mới từ model dùng ngôn ngữ tương ứng. Câu hỏi, câu trả lời
đã có và trích dẫn nguyên văn không bị dịch lại khi chuyển giao diện.

Để tổng hợp bằng Groq, Gemini hoặc OpenAI:

```bash
.venv311/bin/python -m pip install 'openai>=1.30.0,<3'
```

Trong **Kết nối model**, chọn **Groq**, **Gemini** hoặc **OpenAI**, nhập key tùy chỉnh và
model ID, rồi **Áp dụng**. Key tùy chỉnh có ưu tiên cao hơn key mặc định.
Nếu để trống key, ứng dụng dùng Groq mặc định trên máy. Chọn **Offline** để
không gọi API. Lỗi của key tùy chỉnh được báo rõ, không âm thầm đổi nhà cung cấp.
Nút **Xóa key tùy chỉnh** khôi phục cấu hình mặc định, không xóa key server.

Cấu hình mặc định được đọc từ biến môi trường `GROQ_API_KEY` / `GROQ_MODEL`
hoặc `.env.local` tại thư mục dự án (biến môi trường có ưu tiên cao hơn).
`.env.local` bị loại khỏi Git; đặt quyền file `600`. Không chia sẻ file này.
Model mặc định là `openai/gpt-oss-120b` trên Groq. Model GPT-OSS dùng reasoning
thấp và ngân sách 2048 token cho giao diện. Tích hợp dựa trên
[Groq OpenAI compatibility](https://console.groq.com/docs/openai) và
[Groq reasoning parameters](https://console.groq.com/docs/reasoning).

**Kiểm tra kết nối** xác nhận key truy cập model, không sinh câu trả lời.
Key mặc định chỉ nằm phía server, không được đưa vào HTML, JavaScript hay API
trả về trình duyệt. Key tùy chỉnh chỉ giữ trong bộ nhớ tab và từng request,
không lưu vào file hay browser storage. Tải lại/đóng tab xóa key tùy chỉnh và
lịch sử; key Groq mặc định vẫn hoạt động. Chỉ lựa chọn ngôn ngữ được lưu trong
browser storage. Câu hỏi và các đoạn bằng chứng được gửi tới nhà cung cấp đang
chọn, tính phí trên tài khoản API tương ứng.

Server chỉ bind `127.0.0.1`, dành cho một người dùng trên máy cá nhân. Không có
đăng nhập hay hỗ trợ triển khai nhiều người dùng qua Internet. Giao diện không thay thế benchmark hay quy trình đánh giá nghiên cứu.

### Thêm paper và kiểm tra bằng chứng

Bấm **+ Thêm paper**, dán link PDF trực tiếp/link arXiv hoặc chọn file PDF trên máy.
Giới hạn 30 MB, 200 trang; PDF scan cần OCR trước. Paper được xử lý và chọn tự động
để hỏi ngay. File trùng được nhận diện bằng SHA-256. Thư viện tồn tại sau khi khởi
động lại server; nhập lỗi không thay thế thư viện đang dùng. Dữ liệu nằm tại
`data/papers`, `artifacts/library_versions` và con trỏ `artifacts/library-active.json`.
Link nhập phải trỏ tới tài nguyên Internet công khai; địa chỉ nội bộ bị từ chối.

Ở chế độ web **Text + tables** với API, ứng dụng tìm trên văn bản nguyên trang,
giữ các hàng bảng ngắn, dịch câu hỏi tiếng Việt sang tiếng Anh để truy xuất và
phân bổ ngữ cảnh cho nhiều trang. Model trả về các nhận định có trích đoạn;
server kiểm tra trích đoạn có trong nguồn rồi tự gắn paper/trang. Nếu model
chép sai đoạn trích, ứng dụng thử sửa một lần và kiểm tra lại; thất bại vẫn từ chối.
Lượt sửa có thể phát sinh thêm token và độ trễ. Những kiểm tra
này xác nhận xuất xứ, không chứng minh mọi diễn giải của model đều đúng.
Các chế độ offline, Text + captions và benchmark CLI vẫn dùng pipeline gốc.

Sổ bằng chứng ưu tiên nguồn thực sự được trích dẫn, tô từ khóa khớp, hiện đoạn
trích và lý do nguồn xuất hiện. Nguồn chỉ được truy xuất được phân biệt với nguồn
đã dùng trong câu trả lời. Bấm số trích dẫn để mở đúng trang PDF, hoặc mở rộng
ngữ cảnh để đối chiếu. Điểm truy xuất không được trình bày như xác suất đúng.

Xem [báo cáo kiểm thử import, Gemini và evidence](reports/ui-import-gemini-evidence-20260924.md).

### Gemini

Chọn **Gemini**, nhập key từ Google AI Studio, kiểm tra model rồi áp dụng.
Model ID có thể sửa theo quyền tài khoản. Tích hợp dùng
[Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai).
Key Gemini chỉ nằm trong bộ nhớ tab; để trống vẫn dùng Groq mặc định theo cấu hình
chung. Đã kiểm thử định tuyến và tham số bằng mock; chưa kiểm thử sinh câu trả
lời thật với Gemini vì chưa có key Gemini.

## Run

Run commands from the repository root. The manifest contains source URLs and SHA-256 fingerprints. Downloaded PDFs and generated indexes are ignored by Git.

```bash
# Download if absent, then ingest and index with the SAME configuration.
python scripts/build_corpus.py --config configs/default.yaml
# If the four PDFs are already available, use --skip-download.

researchpilot ask --question "What is the key architectural innovation in MobileNets?" --paper-id P01
researchpilot ask --question "What accuracy does EfficientNet-B7 achieve?" --paper-id P02 --mode table-rag --json
researchpilot compare --paper-a P01 --paper-b P02 --question "How do width and resolution scaling differ?"
researchpilot inspect --query "depthwise separable convolution" --paper-id P01

researchpilot benchmark --questions data/questions.jsonl --out results/my-run
researchpilot evaluate --run results/my-run --out reports/my-run.md
# Evaluation can be repeated safely. A benchmark refuses to overwrite predictions.
```

The default artifacts live in `artifacts/current/{corpus,index}`. Individual stages are also available:

```bash
researchpilot ingest --manifest data/papers_manifest.json --out artifacts/current/corpus
researchpilot index --corpus artifacts/current/corpus --out artifacts/current/index
```

Use a new output directory when rebuilding to preserve earlier experiments, and pass its `--index-dir` to query/benchmark commands. `index --config PATH` is honored; global `--config` precedes the subcommand. Query-time embedding configuration must match the saved index. Both `--json` and `--json-output` emit parseable JSON without terminal line wrapping.

## Architecture and guarantees

```text
PDF -> text / structured tables / captions / extracted image assets
    -> page-preserving chunks with stable per-evidence IDs
    -> provenance-aware deduplication -> normalized FAISS index
    -> filtered top-k -> generator -> citation/coverage guard -> answer or abstention
                                        |
                           raw response + prompt + source evidence
                                        |
                     benchmark snapshots -> evaluation -> human review
```

- Evidence stores paper ID, page, URL, modality, excerpt, section heuristic and bounding boxes where available. Images retain local asset paths; image assets are not necessarily complete rendered figures.
- Filtering searches the full small index before selecting top-k. Equal text on different pages or papers remains separately citable.
- Citations must match **ID, paper and page**. Missing/invalid citations or uncited sentences cause an abstention; the raw response remains available for auditing.
- Low retrieval scores or no evidence cause abstention. Similarity thresholds are heuristics, not proof of sufficient evidence.
- Document content is serialized as untrusted JSON; generation has no execution tools. Injection regression tests cover deterministic providers and output guards. They do not establish immunity for every remote LLM.
- Retrieval order, seeds, model/version, prompts, decoding settings, source/index/question hashes, hardware, token usage and end-to-end retrieval/generation latency are saved. API tokens are measured; offline counts are estimates.

Example **excerpt from an actual offline answer**, shortened here:

> Extracted evidence: “We proposed a new model architecture called Mo- bileNets based on depthwise separable convolutions. …” [P01, p.8, ev-P01-p8-t3-c0].

The offline generator quotes source text; it does not perform cross-paper reasoning or certify that the quote answers the entire question.

## Evaluation and ablations

Modes:

| Mode | Input |
|---|---|
| `closed-book` | No retrieval. Offline generators abstain because they have no learned knowledge. |
| `text-rag` | Body text and captions; no structured table input. |
| `table-rag` | Body text, captions and structured tables. |
| `caption-rag` | Alias baseline with text and captions; no image inference. |
| `vlm-rag` | Rejected explicitly: end-to-end image evaluation is not implemented. |

```bash
python scripts/run_baselines.py --questions data/questions.jsonl --out results/ablation-run --ablations
# Produces k3, k5, k10 and no-captions runs.
python scripts/evaluate.py --run results/ablation-run/k3 --report reports/k3.md
python scripts/audit_data.py --out reports/data-audit
```

Text/table runs at each k use identical questions and generator settings. Explicit caption blocks are separated from body text for caption ablations; imperfect PDF layout parsing can still leave caption fragments inside mixed blocks. No reranker is implemented.

`evaluation_metrics.json` reports numerator/denominator, per-question/category/modality/split results, latency p50/p95, tokens and abstention precision/recall. Undefined ratios are `null`, not 100%. API cost is `null` unless independently measured; token counts do not imply a dollar cost.

**Structural citation precision** checks original raw citations, including rejected ones. **Citation coverage** counts delivered sentences with citations, not semantic entailment. Evidence recall uses exact evidence IDs (or their chunks), falling back to paper/page only when a gold ID was not supplied. Page-level recall is coarse. It is not an answer-accuracy metric.

For human scoring:

1. Give `review_template.jsonl` to reviewers; keep `blind_key.json` separate. `review_id` order obscures mode labels but answer style can still reveal the generator.
2. Review gold facts, source excerpts and each cited claim. Fill correctness (0/1), semantic_citation_support (0/1 or null), annotator and rationale.
3. Convert filled reviews to judgments with `scripts/import_reviews.py` and evaluate with `--judgments`.

```bash
python scripts/import_reviews.py --reviews results/my-run/review_template.jsonl --key results/my-run/blind_key.json --out results/my-run/judgments.jsonl
researchpilot evaluate --run results/my-run --judgments results/my-run/judgments.jsonl
```

There is currently **no untouched held-out set**. All legacy questions were available during development. `--split dev|held-out` supports future prospectively annotated questions; relabeling these existing questions would not make them unseen.

## Optional API generation

Install `python -m pip install '.[api]'`, put `OPENAI_API_KEY` in `.env`, copy the default config to a new YAML and set `generate.llm_provider: openai` and `generate.llm_model` to your chosen supported model. Run with `researchpilot --config PATH ...`. There is no automatic model fallback. Existing API/VLM provider adapters remain optional; real API inference and actual image reasoning were not exercised in the offline validation.

A sentence-transformers embedding provider is also available through `.[semantic]`. Changing the embedding provider/model/dimension requires a new index. Record and pin the downloaded model revision and optional dependency versions before drawing research conclusions.

## Data and limitations

See [data documentation](data/README.md) for corrected source metadata and [failure analysis](reports/failure_analysis.md). PDF extraction can miss or split tables, merge columns, omit vector figures and misidentify captions. OCR is not implemented. The benchmark's original authorship/verification is undocumented; source corrections made by AI are not human annotations.

The larger study still needs 10–20 permissively licensed papers, 30–50 human-authored/verified questions, a genuinely held-out subset, completed extraction reviews, blind correctness/support judgments and experiments with a real generator. The shipped offline runs demonstrate software behavior and lexical retrieval only.

## Development

```bash
ruff check src scripts tests
ruff format --check src scripts tests
pytest -q
```

CI runs the same offline checks on Python 3.11. Tests use synthetic PDFs and never require API credentials. Source code is declared MIT in project metadata; third-party papers retain their own licenses.

### Key Groq dự phòng và câu hỏi tổng hợp

Server hỗ trợ `GROQ_API_KEYS` trong `.env.local`: danh sách key phân cách bằng dấu phẩy.
`GROQ_API_KEY` vẫn là key chính. Chỉ khi gọi API bị HTTP 429, server thử key dự phòng,
mỗi key tối đa một lần trong một lượt sinh; key bị giới hạn được tạm nghỉ theo
`Retry-After` (mặc định 60 giây). Các key không được gửi xuống giao diện hoặc ghi log.
Nếu mọi key bị giới hạn, ứng dụng báo lỗi quota; nếu các key chung một hạn mức,
chuyển key không làm tăng hạn mức đó. Lỗi xác thực/model/mạng không tự đổi key.
Key do người dùng nhập trực tiếp trong tab vẫn có ưu tiên và không dùng pool server.

Câu hỏi tiếng Việt được diễn giải thành truy vấn tìm nguồn, có tên các paper đã chọn.
Câu hỏi bài học/tổng quan lấy thêm trang giới thiệu của mỗi paper. Model chọn mã
đoạn gốc thay vì chép lại trích dẫn, giảm lỗi trích dẫn sai định dạng. Câu trả lời có
thể trả phần đã xác định kèm mục “Phần chưa xác định từ nguồn”. Không có cam kết
mọi câu hỏi đều trả lời được: thông tin không có trong tài liệu không được bịa ra.

### Khi trình duyệt báo “fetch failed”

Lỗi này có thể do server localhost đã dừng, chưa phải do API key. Khởi động độc lập
với terminal/tác vụ bằng:

```bash
.venv311/bin/python scripts/start_web.py
```

Lệnh không tạo thêm server nếu ứng dụng đã chạy. Log ở `tmp/web-server.log`;
PID ở `tmp/web-server.pid`. Không cần gửi key vào lệnh. Ứng dụng phân biệt lỗi
mất kết nối local, key không hợp lệ và giới hạn API; không mặc định coi HTTP 429 là hết tiền.
