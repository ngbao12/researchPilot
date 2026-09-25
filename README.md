# ResearchPilot

**Không chỉ đọc câu trả lời — mở được trang paper đứng sau mỗi nhận định.**

ResearchPilot là workspace chạy trên máy cá nhân để đọc paper, đặt câu hỏi và so sánh tài liệu. Bạn có thể thêm PDF từ máy hoặc đường dẫn Internet, chọn nguồn muốn hỏi, rồi kiểm tra các đoạn trích ngay bên cạnh câu trả lời.

Dự án có giao diện **tiếng Việt / English**, tích hợp **Groq, Gemini và OpenAI**, cùng CLI phục vụ truy xuất và đánh giá thử nghiệm. Chế độ offline không cần API key, nhưng chỉ trả trích đoạn từ nguồn, không tổng hợp như LLM.

## Chức năng

- **Thư viện PDF:** nhập file hoặc link PDF/arXiv, nhận diện file trùng, lưu thư viện qua các lần khởi động.
- **Hỏi và so sánh:** giới hạn câu hỏi theo các paper đã chọn; so sánh hai tài liệu và trả lời phần có căn cứ khi thông tin chưa đầy đủ.
- **Bằng chứng cạnh câu trả lời:** hiện đoạn nguồn, ý được hỗ trợ và giải thích của model; thu gọn những đoạn truy xuất chưa được sử dụng.
- **Truy xuất cho câu hỏi trừu tượng:** câu hỏi tổng quan/bài học có thêm bước chọn đoạn theo ngữ nghĩa bằng LLM, sau bước tạo tập ứng viên.
- **Đối chiếu PDF:** bấm trích dẫn để mở trang nguồn; xem thêm ngữ cảnh hoặc mở PDF gốc.
- **Cấu hình model trên giao diện:** nhập API key, chọn model và kiểm tra kết nối. Server hỗ trợ nhiều key Groq dự phòng.
- **Ghi chú nghiên cứu:** lịch sử trong phiên tab và xuất câu trả lời thành Markdown.
- **CLI đánh giá:** benchmark, ablation, xuất dữ liệu để con người chấm tính đúng và mức hỗ trợ của trích dẫn.

> Đây là bản thử nghiệm dành cho một người dùng trên localhost. Kiểm tra trích dẫn xác nhận đoạn văn có trong nguồn, **không chứng minh mọi diễn giải của model đều đúng**. Dự án chưa có kết quả đánh giá độc lập đủ để công bố độ chính xác của hệ thống.

## Bắt đầu

Yêu cầu **Python 3.11 trở lên**; môi trường được kiểm tra của dự án dùng Python 3.11. Chạy các lệnh dưới đây từ thư mục repository.

### 1. Cài đặt

```bash
git clone https://github.com/ngbao12/researchPilot.git
cd researchPilot

python3.11 -m venv .venv311
source .venv311/bin/activate
python -m pip install -r requirements.lock
python -m pip install '.[api]'
```

`requirements.lock` cố định môi trường offline và công cụ phát triển. SDK API là dependency bổ sung, chưa được cố định trong lock này. Nếu chỉ dùng offline, thay lệnh cuối bằng `python -m pip install --no-deps .`.

### 2. Tạo thư viện ban đầu

```bash
python scripts/build_corpus.py --config configs/default.yaml
```

Script tải các paper trong [manifest](data/papers_manifest.json), trích xuất nội dung và tạo chỉ mục tại `artifacts/current`. Bước này cần Internet nếu PDF chưa có trên máy. Nếu đã có đủ PDF, thêm `--skip-download`.

**Cần hoàn tất bước này trước khi mở web lần đầu.** Không cần dựng lại corpus mỗi lần chạy ứng dụng. Sau khi có thư viện, thêm paper mới trực tiếp trên giao diện.

### 3. Mở ứng dụng

```bash
python scripts/start_web.py
```

Truy cập **http://127.0.0.1:8765**. Script chạy server nền và không tạo thêm tiến trình nếu địa chỉ đó đã có workspace hoạt động.

Để chạy trong Terminal và dừng bằng `Ctrl+C`:

```bash
researchpilot-web --root . --port 8765
```

Log của server nền nằm ở `tmp/web-server.log`, PID ở `tmp/web-server.pid`. Có thể đổi cổng bằng `python scripts/start_web.py --port 8766`.

## Sử dụng giao diện

1. Chọn các paper trong **Tài liệu trên bàn**, hoặc bấm **+ Thêm paper**.
2. Mở **Kết nối model**, chọn nhà cung cấp, nhập key và model ID phù hợp với tài khoản. Bấm **Kiểm tra kết nối**, rồi **Áp dụng**.
3. Chọn **Hỏi tài liệu** hoặc **So sánh hai paper**; chế độ so sánh cần chọn đúng hai tài liệu.
4. Nhập câu hỏi và bấm **Tìm câu trả lời**. Có thể hỏi bằng tiếng Việt; ngôn ngữ câu trả lời theo lựa chọn **VI / EN**.
5. Đọc bằng chứng bên cạnh và bấm trích dẫn để đối chiếu trang PDF.

Ví dụ:

- “MobileNet giảm chi phí tính toán bằng cách nào?”
- “EfficientNet-B7 đạt độ chính xác ImageNet bao nhiêu?”
- “Điểm đáng học từ thiết kế của ResNet và Transformer là gì?” — cần thêm và chọn hai paper tương ứng.

Bản dịch giao diện không dịch lại câu trả lời đã có hoặc đoạn nguồn nguyên văn. Đoạn trích dài được thu gọn; phần **Xem thêm ngữ cảnh** giữ văn bản trích xuất để đối chiếu.

### Thêm paper

Hỗ trợ file PDF trên máy, link PDF công khai và link arXiv. Giới hạn nhập từ web là **30 MB / 200 trang**. PDF scan cần OCR trước; ứng dụng chưa có OCR tích hợp.

File trùng được nhận diện bằng SHA-256. Dữ liệu thư viện được lưu ở `data/papers`, `artifacts/library_versions` và con trỏ `artifacts/library-active.json`. Import lỗi không thay thế thư viện đang dùng. URL trỏ đến mạng nội bộ bị từ chối.

## API key và quyền riêng tư

| Cách dùng | Cấu hình |
| --- | --- |
| Groq, Gemini hoặc OpenAI riêng | Nhập key và model ID trong **Kết nối model** |
| Groq mặc định cho máy này | Đặt `GROQ_API_KEY` trong môi trường hoặc `.env.local` |
| Groq dự phòng | Đặt `GROQ_API_KEYS`, các key cách nhau bằng dấu phẩy |
| Không gửi dữ liệu tới API | Chọn **Offline** |

Ví dụ `.env.local` — thay các giá trị mẫu bằng cấu hình của bạn:

```dotenv
GROQ_API_KEY=your_primary_groq_key
GROQ_API_KEYS=your_backup_key_1,your_backup_key_2
GROQ_MODEL=openai/gpt-oss-120b
```

```bash
chmod 600 .env.local
```

Biến môi trường có ưu tiên hơn `.env.local`. File này được bỏ qua bởi Git; **không commit API key**. Khởi động lại server sau khi thay cấu hình server.

- Key nhập trong tab có ưu tiên hơn key mặc định. Nếu để trống key, ứng dụng dùng Groq mặc định **nếu đã cấu hình trên máy**; repository không cung cấp key dùng chung.
- Key tùy chỉnh chỉ tồn tại trong bộ nhớ tab và request tới server local. Tải lại hoặc đóng tab sẽ xóa key tùy chỉnh và lịch sử phiên. Lựa chọn ngôn ngữ được lưu riêng trong browser storage.
- Key mặc định nằm phía server, không được trả về giao diện. Key tùy chỉnh không dùng pool Groq dự phòng của server.
- Khi gặp giới hạn API, pool Groq có thể chờ hoặc thử key khác. Các key có thể dùng chung quota; thêm key không đồng nghĩa tăng hạn mức.
- Câu hỏi và các đoạn nguồn được gửi tới nhà cung cấp đang chọn để xử lý. Lượt lập kế hoạch, chọn bằng chứng hoặc sửa trích dẫn có thể phát sinh thêm token và độ trễ.
- **Kiểm tra kết nối** kiểm tra quyền truy cập model; không bảo đảm một lượt sinh câu trả lời dài sẽ thành công hoặc còn đủ quota.

Gemini dùng adapter tương thích OpenAI. Model khả dụng phụ thuộc tài khoản; có thể sửa model ID trong giao diện. Các bài test mock kiểm tra định tuyến và xử lý lỗi, không thay thế kiểm thử trực tiếp với key thật.

## Câu trả lời và bằng chứng được tạo như thế nào?

```text
PDF → trích xuất theo trang → chọn ứng viên truy xuất
                                  ↓
                 chọn đoạn theo ngữ nghĩa cho câu hỏi tổng quan
                                  ↓
                 model tạo nhận định + mã đoạn nguồn
                                  ↓
                 kiểm tra nguồn → câu trả lời + trích dẫn trang
```

Trong luồng web dùng API với `table-rag`, hệ thống truy xuất văn bản trang, giữ ngữ cảnh bảng và diễn giải câu hỏi tiếng Việt thành truy vấn tìm nguồn. Câu hỏi tổng quan/bài học bổ sung các trang mở đầu, cuối tài liệu và bước lựa chọn bằng LLM. Bước này vẫn phụ thuộc tập ứng viên; không phải tìm kiếm ngữ nghĩa toàn bộ corpus bằng embedding.

Model chọn mã đoạn có sẵn; server kiểm tra nguồn và tự gắn paper/trang. Một số lỗi định dạng trích dẫn được thử sửa một lần. Nếu không xác nhận được nguồn, câu trả lời có thể bị giữ lại. Nếu chỉ có căn cứ cho một phần câu hỏi, ứng dụng có thể trả lời phần đó và ghi rõ thông tin còn thiếu.

Phần **Giải thích của model** mô tả liên hệ giữa nguồn và nhận định, không phải kết quả kiểm chứng độc lập. Luôn đọc nguồn khi sử dụng các kết luận quan trọng. Điểm truy xuất không phải xác suất câu trả lời đúng.

Các chế độ khác và benchmark CLI dùng pipeline gốc: trích xuất → chunk có thông tin nguồn → chỉ mục FAISS → truy xuất → sinh câu trả lời → kiểm tra trích dẫn. Kết quả CLI không đại diện đầy đủ cho luồng web mới.

## CLI

Cấu hình mặc định tại [configs/default.yaml](configs/default.yaml) dùng truy xuất lexical và trả trích đoạn offline, không gọi API.

```bash
researchpilot ask --question "What is the key architectural innovation in MobileNets?" --paper-id P01
researchpilot ask --question "What accuracy does EfficientNet-B7 achieve?" --paper-id P02 --mode table-rag --json
researchpilot compare --paper-a P01 --paper-b P02 --question "How do width and resolution scaling differ?"
researchpilot inspect --query "depthwise separable convolution" --paper-id P01
```

Để dùng OpenAI trong CLI, đặt `OPENAI_API_KEY` trong môi trường hoặc `.env`, sao chép cấu hình mặc định và sửa `generate.llm_provider: openai`, `generate.llm_model`. Chạy bằng `researchpilot --config PATH ...`. Cấu hình CLI này riêng với kết nối model trên giao diện web.

Provider embedding sentence-transformers là tùy chọn qua `python -m pip install '.[semantic]'`. Đổi provider/model/kích thước embedding cần dựng chỉ mục mới; không dùng chỉ mục cũ với cấu hình khác.

## Đánh giá và phát triển

```bash
researchpilot benchmark --questions data/questions.jsonl --out results/my-run
researchpilot evaluate --run results/my-run --out reports/my-run.md

python scripts/run_baselines.py --questions data/questions.jsonl --out results/ablation-run --ablations
python scripts/audit_data.py --out reports/data-audit

ruff check src scripts tests
pytest -q
```

Benchmark không ghi đè predictions đã có; dùng thư mục output mới cho mỗi lần chạy. Khi dùng index khác, truyền `--index-dir` và giữ cấu hình embedding khớp với index. Test offline không cần API key; muốn kiểm tra API thật cần cấu hình riêng.

Các chỉ số trích dẫn cấu trúc, coverage và evidence recall đo những khía cạnh khác nhau; không được gọi chung là độ chính xác câu trả lời. Chấm tính đúng và mức hỗ trợ ngữ nghĩa cần con người đọc nguồn. Những câu hỏi cũ đã được dùng trong quá trình phát triển, chưa tạo thành tập held-out độc lập.

Đọc thêm:

- [Dữ liệu và nguồn paper](data/README.md)
- [Tình trạng yêu cầu nghiên cứu](reports/requirements_status.md)
- [Báo cáo thí nghiệm nền](reports/experiment_report.md)
- [Phân tích lỗi](reports/failure_analysis.md)
- [Kiểm thử import, Gemini và evidence](reports/ui-import-gemini-evidence-20260924.md)

Các báo cáo ghi nhận trạng thái tại thời điểm chạy, không phải cam kết cho mọi phiên bản hoặc mọi nhà cung cấp API.

## Xử lý lỗi thường gặp

| Hiện tượng | Cách kiểm tra |
| --- | --- |
| Không mở được web / `fetch failed` | Chạy `python scripts/start_web.py`; xem `tmp/web-server.log` nếu server không lên |
| Không tìm thấy corpus/index | Chạy bước tạo thư viện ban đầu từ thư mục repository |
| Key không hợp lệ / model không truy cập được | Kiểm tra key, nhà cung cấp và model ID trong **Kết nối model** |
| HTTP 429 / giới hạn API | Kiểm tra quota của tài khoản; chờ hoặc đổi nhà cung cấp. Không mặc định coi mọi 429 là hết tiền |
| Model trả phản hồi rỗng | Thử lại hoặc chọn model khác; nút kiểm tra kết nối không kiểm tra sinh nội dung |
| Chưa đủ bằng chứng | Kiểm tra đã chọn đúng paper, mở đoạn nguồn, hoặc hỏi rõ hơn. Không có cơ chế bảo đảm trả lời mọi câu hỏi |
| Giao diện vẫn giống bản cũ | Tải lại trang rồi gửi lại câu hỏi; lưu ghi chú cần thiết trước khi tải lại |

## Giới hạn hiện tại

- Server chỉ phục vụ `127.0.0.1`, chưa có xác thực hay thiết kế triển khai công khai cho nhiều người dùng.
- Trích xuất PDF có thể lẫn cột, ngắt chữ hoặc đọc sai bảng; chưa có OCR và chưa hoàn thiện suy luận trực tiếp trên hình.
- `caption-rag` dùng văn bản/caption, không phải phân tích hình bằng model thị giác. Luồng đánh giá `vlm-rag` chưa được triển khai hoàn chỉnh.
- Offline chỉ trích nguồn; không thực hiện tổng hợp và so sánh như LLM.
- Việc chọn bằng chứng và giải thích của LLM có thể sai. Bộ dữ liệu hiện tại chưa đủ cho kết luận nghiên cứu về chất lượng tổng quát.

Mã nguồn khai báo giấy phép **MIT** trong metadata dự án. Các paper và tài nguyên bên thứ ba giữ giấy phép riêng.
