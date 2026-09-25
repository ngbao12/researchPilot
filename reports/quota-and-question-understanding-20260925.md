# Key dự phòng và hiểu câu hỏi — 25/09/2026

- Giữ key mặc định trước đó, thêm bốn key dự phòng vào `.env.local` (600, gitignored). Không ghi giá trị key vào source, báo cáo hay phản hồi API.
- Pool dùng key tiếp theo khi HTTP 429; giới hạn một lần thử mỗi key trong mỗi lượt sinh. Có cooldown theo Retry-After và báo lỗi nếu hết pool. Không chuyển key cho lỗi xác thực/model/mạng; key người dùng nhập trong tab vẫn tách khỏi pool.
- Truy vấn tiếng Việt có ngữ cảnh tên paper đã chọn và phân loại tổng quan/nhận diện/cụ thể. Câu hỏi tổng hợp lấy thêm trang giới thiệu của từng paper. Model chọn đoạn bằng mã thay vì chép lại văn bản.
- Trả lời phần có nguồn hỗ trợ, hiển thị riêng phần chưa xác định. Không bỏ kiểm tra nguồn hoặc biến câu hỏi không có đáp án thành câu trả lời bịa.
- Tổng hợp bài học dùng mức reasoning medium của GPT-OSS theo [tài liệu Groq](https://console.groq.com/docs/reasoning), ưu tiên bài học định tính thay vì tự đưa thêm số liệu không được hỏi.

## Kiểm tra

170 pytest tests và Ruff qua. Tests mô phỏng 429 chứng minh chuyển key, giữ nguyên request, không retry lỗi khác, dừng khi mọi key bị giới hạn và phục hồi sau cooldown. Không cố tình dùng hết quota thật để thử failover.

Đã gọi Groq thật với key trong pool:
- “điểm đáng học giữa 2 model này là gì”: có câu trả lời với nguồn từ cả ResNet và Transformer. Bản cuối tập trung ba bài học thiết kế, lưu `artifacts/quality-current-lessons-final.json`.
- “đâu là paper nói về attention”: nhận diện đúng Attention Is All You Need.
- Hỏi chính xác kWh huấn luyện Transformer: vẫn từ chối vì không có số liệu trong paper.

Đã kiểm tra trên UI câu hỏi tổng hợp, không còn từ chối trong ca đã tái hiện. Kết quả trên bộ nhỏ dùng để phát triển không chứng minh mọi câu hỏi hay mọi diễn giải đều đúng; model vẫn có thể sai. Nhiều key dùng chung một hạn mức sẽ không tạo thêm quota.

Đã kiểm tra thêm câu hỏi hỗn hợp GPU và kWh: trả lời tám GPU, ghi riêng rằng nguồn không cung cấp số kWh; lưu `artifacts/quality-current-partial.json`. Một lượt API trước đó gặp BadRequestError, lượt chạy lại hoàn tất; chưa khẳng định loại bỏ mọi lỗi dịch vụ/model.

Ở lượt kiểm tra UI cuối, toàn bộ pool key bị giới hạn quota/cooldown; thử lại sau khoảng nghỉ vẫn nhận lỗi quota. Vì vậy chưa xác nhận được giao diện câu trả lời một phần bằng API thật trên bản cuối, dù backend đã trả lời một phần thành công trước đó và các test tách ghi chú thiếu thông tin đã qua. Không coi việc thêm key là bảo đảm tăng hạn mức. Server vẫn chạy bản cuối tại localhost:8765.
