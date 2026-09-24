# Kiểm thử paper mới — 24/09/2026

> Đây là kết quả trước khi sửa. Xem [bản cập nhật import, Gemini và evidence](ui-import-gemini-evidence-20260924.md) cho chức năng và kiểm thử mới.

## Kết luận

Pipeline tải/nhập/index được hai paper mới, nhưng **chưa trả lời đáng tin cậy trên paper mới**. Trong 10 câu có thông tin trả lời trong PDF, chỉ 1 câu trả lời được và đối chiếu đúng; 9 câu trả về `insufficient_evidence`. Hai câu cố ý hỏi thông tin không có trong paper đều bị từ chối. Không thấy câu trả lời sai được xuất ra trong mẫu nhỏ này, nhưng hệ thống bỏ lỡ quá nhiều câu có đáp án.

Đây là kiểm thử thủ công có chủ đích, không phải ước lượng accuracy tổng quát hay đánh giá độc lập của chuyên gia. Bốn câu Việt/Anh là các cặp tương đương nên không phải 12 quan sát độc lập. 122 unit tests đã qua ở lần phát triển trước không chứng minh độ đúng của câu trả lời RAG trên dữ liệu mới.

## Phạm vi và cách chạy

- Thêm [ResNet, arXiv:1512.03385v1](https://arxiv.org/abs/1512.03385v1) (N01, 12 trang) và [Attention Is All You Need, arXiv:1706.03762v7](https://arxiv.org/abs/1706.03762v7) (N02, 15 trang).
- Tải PDF chính thức; cố định phiên bản và SHA-256 trong manifest.
- Dựng corpus thử riêng gồm 4 paper cũ + 2 paper mới: 1.646 evidence items, 813 vectors. Không thay corpus/index đang chạy tại `artifacts/current`.
- Gọi cùng `Workspace.query` mà giao diện dùng, thay corpus/index bằng bản thử. Đây là kiểm thử pipeline/backend, không phải thao tác upload trên UI.
- Groq `openai/gpt-oss-120b`, lexical-hash-v1, top_k=5, table-rag, ngưỡng từ chối 0.15, giới hạn 2048 token. Key đọc từ cấu hình local, không ghi vào kết quả.
- 12 câu: 8 câu đơn-paper (4 cặp EN/VI), 2 câu không có đáp án, 1 câu tìm trong toàn bộ 6 paper, 1 câu so sánh 2 paper mới.
- Hai câu cuối lần đầu gặp RateLimitError; đã thử lại riêng một lần và lưu kết quả riêng. Báo cáo dùng lần chạy hoàn tất, vẫn giữ kết quả lỗi ban đầu.
- Đáp án tham chiếu được đối chiếu với văn bản PDF gốc, không lấy từ chính câu trả lời model. Trích dẫn của câu duy nhất trả lời được được kiểm tra cả trang và nội dung.

## Kết quả từng câu

| ID | Nội dung / ngôn ngữ | Đáp án trong PDF | Kết quả cuối |
|---|---|---|---|
| R1 | ResNet ensemble top-5 error, EN | 3.57%, tập test ImageNet; tr. 1–2, 6–7 | **Đúng**; trích N01 tr. 2 |
| R2 | Cùng câu R1, VI | 3.57% | Từ chối: uncited claim |
| R3 | ResNet-152, Table 3, 10-crop, EN | Top-1 21.43%; top-5 5.71%; tr. 6 | Từ chối dù có đáp án |
| R4 | Cùng câu R3, VI | 21.43% / 5.71% | Từ chối dù có đáp án |
| T1 | Transformer big: thời gian, số/loại GPU, EN | 3.5 ngày, 8 NVIDIA P100; tr. 7–8 | Từ chối: ID citation dùng dấu gạch nối Unicode |
| T2 | Cùng câu T1, VI | 3.5 ngày, 8 NVIDIA P100 | Từ chối trước gọi model: điểm cao nhất ~0.110 < 0.15 |
| T3 | Transformer base: heads, d_model, d_k, EN | 8 heads, 512, 64; tr. 3, 5, 9 | Từ chối: top-5 thiếu đoạn nêu giá trị |
| T4 | Cùng câu T3, VI | 8 / 512 / 64 | Từ chối: top-5 thiếu đoạn nêu giá trị |
| U1 | ResNet có báo accuracy GPT-4 không, EN | Không báo cáo | **Từ chối đúng** |
| U2 | Transformer big tiêu thụ chính xác bao nhiêu kWh, VI | Không báo cáo điện năng kWh đo được | **Từ chối đúng** |
| M1 | BLEU Transformer big, tìm toàn bộ 6 paper, EN | Abstract/Table 2: 28.4 EN-DE, 41.8 EN-FR; lưu ý đoạn văn tr. 8 ghi 41.0 EN-FR | Từ chối: sai ID citation sau khi thử lại |
| C1 | So sánh residual connection và normalization, EN | ResNet F(x)+x, BN; Transformer LayerNorm(x+Sublayer(x)); N01 tr. 3–4, N02 tr. 3 | Từ chối: ID citation không khớp sau khi thử lại |

Lưu ý M1: PDF v7 có bất nhất nội bộ giữa abstract/bảng (41.8) và đoạn văn (41.0). Một câu trả lời tốt cần chỉ rõ vị trí hoặc nêu bất nhất; không nên gán mọi câu trả lời 41.0 là bịa. Trường hợp này không có câu trả lời được hiển thị vì citation bị chặn.

## Nguyên nhân đã xác minh

1. **Truy xuất từ khóa yếu với câu tiếng Việt.** T2 thực tế tìm thấy đoạn chứa đáp án nhưng điểm thấp hơn ngưỡng, nên không gọi model. Chuyển ngôn ngữ giao diện không biến lexical retrieval thành tìm kiếm đa ngôn ngữ.
2. **Dữ liệu bảng bị tách khỏi ngữ cảnh hoặc mất khỏi index.** Corpus chứa `ev-N01-p6-t10` với nội dung `ResNet-152 / 21.43 / 5.71`; dòng ngắn này không có trong index. Cấu hình `min_chunk_size=100` loại đoạn ngắn không phải modality TABLE. Top-5 của R3 toàn caption/bảng khác, không có dòng cần trả lời. Bộ trích bảng cũng báo các bảng/grid bị loại vì sparse.
3. **Thiếu mở rộng ngữ cảnh cho đoạn lân cận.** Đoạn `ev-N02-p5-t5` chứa h=8, d_k=64 tồn tại trong index nhưng không vào top-5 của T3/T4; các đoạn chung chung về attention/caption được xếp trên.
4. **Model không giữ đúng ID citation.** T1 đổi dấu `-` thành `‑`; M1 còn làm mất thành phần ID. Bộ kiểm tra chặn đúng theo tiêu chuẩn ID hiện tại. Không được sửa bằng cách bỏ kiểm tra provenance hay tự ghép citation gần giống.
5. **Lỗi vận hành tách biệt.** Hai RateLimitError ban đầu là giới hạn dịch vụ, không tính là câu trả lời sai; đã được thử lại có kiểm soát.

## Khả năng “tự add paper” hiện tại

Chưa có tự tìm paper trên Internet, upload PDF, hoặc thêm URL trực tiếp từ giao diện. Script `build_corpus.py` có thể tải PDF theo manifest đã cung cấp, rồi ingest và index. Giao diện đọc corpus khi server khởi động; không tự cập nhật khi có file PDF mới. Việc thêm hai paper trong lần kiểm thử này do script thực hiện trên bộ thử riêng.

## Hướng sửa ưu tiên

1. Giữ các dòng bảng ngắn, nối header/caption/dòng dữ liệu theo trang và vùng bảng trước khi chunk.
2. Truy xuất đa ngôn ngữ hoặc dịch truy vấn có kiểm soát; bổ sung reranking và ngữ cảnh lân cận.
3. Yêu cầu model trả citation theo cấu trúc/ID cho phép, giữ validation paper/page/evidence chính xác; chỉ chuẩn hóa Unicode có quy tắc, không fuzzy-match ID bị mất ký tự.
4. Chạy lại bộ này sau sửa và thêm một bộ paper/câu hỏi chưa dùng để sửa, tránh tối ưu riêng bộ thử.

## Tệp kiểm chứng

- [Manifest và fingerprint](../artifacts/new-paper-check/manifest.json)
- [12 câu và đáp án kỳ vọng](../artifacts/new-paper-check/questions.json)
- [Kết quả lần đầu, đầy đủ evidence](../artifacts/new-paper-check/answers.jsonl)
- [Hai kết quả thử lại](../artifacts/new-paper-check/retry-answers.jsonl)
- [Script kiểm thử](../artifacts/new-paper-check/run_check.py)
- [Log nhập và index](../artifacts/new-paper-check/build.log)
- [PDF ResNet](../artifacts/new-paper-check/papers/N01.pdf)
- [PDF Transformer](../artifacts/new-paper-check/papers/N02.pdf)
