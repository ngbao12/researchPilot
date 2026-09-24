# Thêm paper, Gemini và bằng chứng — 24/09/2026

## Chức năng đã triển khai

- Nhập PDF từ link trực tiếp/arXiv hoặc file trên máy, ngay trong giao diện VI/EN. Giới hạn 30 MB/200 trang; không hỗ trợ OCR cho bản scan.
- Thư viện cập nhật sau nhập; chống trùng SHA-256; lưu phiên bản và chuyển con trỏ sau khi index thành công. Khởi động lại vẫn giữ paper mới.
- Gemini có lựa chọn provider, ô API key/model, link Google AI Studio và kiểm tra quyền truy cập model. Key tùy chỉnh nằm trong bộ nhớ tab. Không nhập key thì dùng Groq mặc định; key sai không tự đổi provider.
- Evidence ưu tiên nguồn đã trích dẫn, hiện đoạn trích đối chiếu được, từ khóa khớp, lý do xuất hiện, ngữ cảnh mở rộng và nút mở đúng trang PDF. Số trích dẫn khớp số thẻ nguồn.

## Cải thiện trả lời

Web API ở chế độ Text + tables dùng tìm kiếm BM25 trên trang PDF, giữ các dòng bảng ngắn. Câu hỏi tiếng Việt được dịch để tìm trong paper tiếng Anh. Ngữ cảnh chia đều giữa các trang để tránh nguồn đầu chiếm toàn bộ ngân sách.

Model trả các nhận định và đoạn trích theo cấu trúc. Server gắn ID/trang thật, kiểm tra đoạn trích có trong nguồn, yêu cầu cả hai paper khi so sánh. Nếu model chép sai đoạn trích, chỉ thử sửa một lần và vẫn kiểm tra lại. Từ khóa khớp là giải thích truy xuất, không phải xác suất trả lời đúng. Kiểm tra trích đoạn không tự chứng minh nhận định được suy ra đúng.

Đây là cải thiện cho web API Text + tables; benchmark CLI và chế độ offline/Text + captions vẫn dùng pipeline gốc. Chưa huấn luyện hoặc fine-tune model.

## Kiểm thử kỹ thuật và giao diện

- 154 pytest tests qua; Ruff qua. Gồm định tuyến Gemini, endpoint/tham số JSON, key không khớp provider, kiểm chứng đoạn trích, giới hạn một lượt sửa và tính token.
- Nhập ResNet qua link arXiv và Transformer qua file PDF thực tế từ giao diện. Thư viện có 6 paper/81 trang và giữ nguyên sau khởi động lại.
- Nhập lại Transformer không tạo bản trùng; link địa chỉ nội bộ bị từ chối với thông báo rõ ràng.
- Chọn Gemini, model mặc định, link lấy key, áp dụng cấu hình rồi xóa key tùy chỉnh đã kiểm tra qua UI. Kiểm tra bố cục desktop 1440 px và mobile 390 px.
- Gemini chỉ kiểm thử bằng mock và thao tác cấu hình: chưa có key Gemini để gọi sinh câu trả lời thật. Groq được kiểm thử bằng API thật.

## Kết quả câu hỏi thật

Trên 10 câu có đáp án trong PDF, bản cũ trả lời đúng 1/10; sau sửa trả lời đúng nội dung 8/10, còn 2 câu từ chối vì đoạn trích không khớp. Hai câu không có đáp án đều từ chối đúng. Không quan sát thấy câu sai về nội dung được xuất ra trong mẫu này. Đây là bộ phát triển dùng lại để sửa, không phải held-out set hoặc đánh giá độc lập; bốn cặp Việt/Anh không phải các quan sát độc lập.

| Câu | Kết quả đối chiếu |
|---|---|
| R1, R2 | ResNet ensemble: 3.57% top-5, ImageNet test; đúng |
| R3, R4 | ResNet-152, Table 3: 21.43% top-1 / 5.71% top-5; đúng |
| T1, T2 | Transformer big: 3.5 ngày, 8 NVIDIA P100; đúng nội dung |
| T3, T4 | Transformer base: 8 heads, d_model=512, d_k=64; đúng nội dung |
| U1, U2 | GPT-4 trong ResNet / điện năng kWh Transformer: từ chối đúng |
| M1 | BLEU trên toàn thư viện: vẫn từ chối do đoạn trích không khớp |
| C1 | So sánh residual/normalization: vẫn từ chối do đoạn trích không khớp |

T2 và T4 trong lượt API đã trả nội dung bằng tiếng Anh dù yêu cầu tiếng Việt. Đã bổ sung chỉ dẫn ngôn ngữ rõ hơn trong prompt cuối; không xem thay đổi prompt là bằng chứng đã loại bỏ hoàn toàn lỗi này.

### Cách tổng hợp kết quả và giới hạn

- R2, R3, R4, T1 lấy từ `final-answers.jsonl`, là các ca thành công trước khi thêm lượt sửa trích dẫn. Nhánh thành công này không thay đổi bởi lượt sửa.
- R1, T2, T3, T4, U1, U2, M1, C1 chạy lại/hoàn tất với sửa trích dẫn có giới hạn, lưu tại `verified-answers.jsonl`. Vì vậy 8/10 là kết quả đối chiếu qua quá trình sửa, **không phải một lần chạy 12 câu độc lập trên bản cuối**.
- Giữ lại `improved-answers.jsonl`, `improved-v2-answers.jsonl` và `final-answers.jsonl` để không che giấu các lần thất bại trước. Các lượt đang phát triển có ngữ cảnh quá dài, giới hạn API hoặc đoạn trích sai.
- Có sửa prompt và cách chia ngữ cảnh dựa trên chính bộ câu hỏi này. Cần thêm paper/câu hỏi chưa dùng để sửa trước khi đánh giá khả năng tổng quát.
- Model vẫn có thể trả sai diễn giải dù trích đúng nguyên văn; cần mở PDF và kiểm tra. Không có điểm tin cậy giả lập trên giao diện.

Tệp gốc nằm trong `artifacts/new-paper-check/`: [kết quả trước lượt sửa](../artifacts/new-paper-check/final-answers.jsonl), [kết quả sửa trích dẫn](../artifacts/new-paper-check/verified-answers.jsonl), [script chạy](../artifacts/new-paper-check/run_final.py).

### Kiểm tra trực tiếp bản cuối qua UI

Sau chỉ dẫn ngôn ngữ bổ sung, đã hỏi Groq trên paper Transformer vừa upload:
“Transformer base dùng bao nhiêu attention heads, d_model và d_k bằng bao nhiêu?”
Ứng dụng trả bằng tiếng Việt: 8 heads, d_model=512, d_k=64; trích trang 9 và 5.
Thời gian hiển thị 4.6 giây. Hai nguồn đã dùng được xếp đầu, có tô từ khóa và lý do;
bấm trích dẫn số 1 mở đúng trang 9/15. Đây là một kiểm tra UI thật trên bản cuối,
không thay thế một lượt đánh giá toàn bộ độc lập.

Sổ bằng chứng được kiểm tra giữ vị trí khi cuộn desktop; giao diện mobile không
tràn ngang. Trích dẫn offline cũng mở PDF đúng trang và ảnh xem trước tải thành công.
