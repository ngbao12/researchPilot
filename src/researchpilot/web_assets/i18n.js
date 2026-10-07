'use strict';
// UI copy only. Research questions, source excerpts and model answers are never translated here.
let language = 'vi';
try { language = localStorage.getItem('researchpilot.language') === 'en' ? 'en' : 'vi'; } catch (_) {}
const english = {
  'Xem toàn bộ đoạn trích':'Show full excerpt',
  'Thu gọn đoạn trích':'Collapse excerpt',
  'Bước chọn theo ngữ nghĩa chưa thành công; đang dùng kết quả truy xuất dự phòng.':'Semantic selection was unavailable; showing fallback retrieval results.',
  'Đoạn truy xuất chưa dùng':'Unused retrieval candidates',
  'Hỗ trợ ý:':'Supports this point:',
  'Giải thích của model:':'Model explanation:', 
  'Các key Groq đang bị giới hạn. Hãy chờ rồi thử lại hoặc dùng Gemini. Các key có thể dùng chung hạn mức.':'The Groq keys are rate limited. Wait and retry, or use Gemini. Keys may share a quota.',

  'Nhà cung cấp API đang giới hạn yêu cầu. Hãy chờ rồi thử lại; lỗi này không nhất thiết là hết tiền.':'The API provider is rate limiting requests. Wait and retry; this does not necessarily mean you are out of credit.',

  'Yêu cầu mất quá nhiều thời gian. Hãy thử lại sau.':'The request timed out. Please try again later.',
  'Không kết nối được ResearchPilot trên máy. Hãy khởi động lại server rồi thử lại; đây chưa phải lỗi API key.':'Cannot reach the local ResearchPilot server. Start the server and try again; this does not indicate an invalid API key.',
  'Server trả về dữ liệu không hợp lệ. Hãy tải lại trang và thử lại.':'The server returned an invalid response. Reload the page and try again.',

  'TRẢ LỜI MỘT PHẦN':'PARTIAL ANSWER', 'Phần chưa xác định từ nguồn:':'Not established by the sources:',
  'Các nguồn tìm được chưa đủ để trả lời đầy đủ câu hỏi.':'The retrieved sources do not fully support an answer.',
  'Model chưa trích đúng nguyên văn từ nguồn. Câu trả lời được giữ lại để tránh dẫn chứng sai.':'The model did not quote the source accurately. The answer was withheld to avoid an invalid citation.',
  'Model viện dẫn nguồn không có trong các đoạn tìm được.':'The model cited a source outside the retrieved excerpts.',
  'Chưa có đủ bằng chứng từ cả hai paper để so sánh.':'There is not enough supporting evidence from both papers to compare them.',
  'Chưa tìm thấy trang phù hợp với câu hỏi.':'No matching source pages were found.',
  'Phản hồi của model chưa đúng định dạng. Hãy thử lại.':'The model response has an invalid format. Please try again.',

  'Trang':'Page', 'Mở nguồn':'Open source', 'Đã dùng trong câu trả lời':'Cited in the answer',
  'Nguồn liên quan':'Related source', 'Vì sao liên quan?':'Why this source?',
  'Đoạn trích này đã được đối chiếu với trang gốc và dùng để hỗ trợ câu trả lời.':'This excerpt was matched against the source page and used to support the answer.',
  'Câu trả lời có trích dẫn đến nguồn này.':'The answer cites this source.',
  'Được tìm thấy khi truy xuất; chưa được dùng để khẳng định câu trả lời.':'Retrieved as a possible match; not used to support a claim in the answer.',
  'Từ khóa khớp':'Matching terms', 'Xem thêm ngữ cảnh':'Read source context', 'Mở trang PDF ↗':'Open PDF page ↗',

  '+ Thêm paper': '+ Add paper', 'Thêm một góc nhìn mới.': 'A new perspective.',
  'Đóng nhập paper': 'Close import', 'Cách nhập': 'Import method',
  'Dán link PDF/arXiv hoặc chọn file trên máy. PDF tối đa 30 MB, 200 trang.': 'Paste a PDF/arXiv link or choose a local file. Up to 30 MB and 200 pages.',
  'CHỌN FILE PDF': 'CHOOSE PDF FILE', 'TÊN PAPER (KHÔNG BẮT BUỘC)': 'PAPER TITLE (OPTIONAL)',
  'Tự nhận diện từ PDF': 'Detect from PDF',
  'PDF được lưu trên máy. Không gửi tài liệu tới model trong bước nhập. PDF scan cần OCR trước.': 'PDFs stay on your computer. Importing does not send documents to a model. Scanned PDFs need OCR first.',
  'Thư viện cập nhật tự động': 'Library updates automatically', 'Thêm vào thư viện': 'Add to library',
  'Thêm PDF hoặc link arXiv/PDF. Tài liệu mới có thể hỏi ngay sau khi nhập xong.': 'Add a PDF or an arXiv/PDF link. New papers are ready to query as soon as import completes.',
  'Đang tải và xử lý PDF…': 'Downloading and indexing PDF…',
  'Paper đã có trong thư viện.': 'This paper is already in your library.',
  'Đã thêm paper. Bạn có thể đặt câu hỏi ngay.': 'Paper added. You can ask a question now.',
  'Chọn file PDF trước khi nhập.': 'Choose a PDF file first.',
  'Chọn file PDF hợp lệ, tối đa 30 MB.': 'Choose a valid PDF up to 30 MB.',
  'Nhập link PDF hoặc arXiv hợp lệ.': 'Enter a valid PDF or arXiv link.',
  'Đang nhập một paper khác. Hãy đợi hoàn tất.': 'Another paper is being imported. Please wait.',
  'PDF phải có 1–200 trang và không khóa mật khẩu.': 'The PDF must contain 1–200 pages and must not be password protected.',
  'PDF không có đủ văn bản đọc được. Bản scan cần OCR trước khi nhập.': 'This PDF has insufficient readable text. Scans need OCR before import.',
  'Không đọc được PDF. File có thể bị hỏng.': 'Cannot read the PDF. The file may be damaged.',
  'Link chưa trỏ tới PDF. Hãy dùng link PDF trực tiếp hoặc trang arXiv /abs/.': 'This link is not a PDF. Use a direct PDF link or an arXiv /abs/ page.',
  'Không tải được PDF. Kiểm tra link hoặc tải file lên trực tiếp.': 'Could not download the PDF. Check the link or upload the file directly.',
  'Chỉ chấp nhận link Internet công khai, không dùng địa chỉ nội bộ.': 'Only public Internet links are accepted; internal addresses are blocked.',
  'Link phải là http/https công khai tới PDF hoặc arXiv.': 'Use a public HTTP/HTTPS PDF or arXiv link.',
  'Không nhập được paper. Thư viện cũ vẫn được giữ nguyên.': 'Import failed. Your previous library has been preserved.',

  'Nhập model ID':'Enter model ID', 'Ngôn ngữ':'Language', 'ResearchPilot trang chủ':'ResearchPilot home',
  'Không gian cá nhân':'Personal workspace', 'KHÔNG GIAN LÀM VIỆC':'WORKSPACE',
  'Điều hướng chính':'Main navigation', 'Bàn nghiên cứu':'Research desk', 'Thư viện':'Library',
  'Phiên làm việc':'Session history', 'BỘ SƯU TẬP':'COLLECTIONS', 'Chạy trên máy của bạn':'Running on your computer',
  'PDF và tìm kiếm luôn ở local':'PDFs and retrieval stay local', 'Nhà nghiên cứu':'Researcher',
  'Kết nối model':'Connect model', 'Từ câu hỏi':'From questions', 'đến':'to', 'bằng chứng.':'evidence.',
  'Đọc, đối chiếu và tìm điều đáng chú ý.':'Read, compare, and find what matters.',
  'Mỗi câu trả lời đều có một nơi để kiểm chứng.':'Every answer leads back to its source.',
  'Tài liệu trên bàn':'Papers on your desk', 'Đang mở bộ sưu tập…':'Opening your collection…',
  'Xem thư viện':'Browse library', 'Loại nghiên cứu':'Research task', 'Hỏi tài liệu':'Ask your papers',
  'So sánh hai paper':'Compare two papers', 'Câu hỏi nghiên cứu':'Research question',
  'Bạn muốn tìm hiểu điều gì trong những tài liệu này?':'What would you like to explore in these papers?',
  'Loại bằng chứng':'Evidence type', 'Văn bản + bảng':'Text + tables', 'Văn bản + caption':'Text + captions',
  'Tìm câu trả lời':'Find an answer', 'Trích bằng chứng trên máy · Không cần API key':'Local evidence retrieval · No API key needed',
  'THỬ MỘT CÂU HỎI':'TRY A QUESTION', 'MobileNet giảm tính toán thế nào?':'How does MobileNet reduce computation?',
  'Độ chính xác của EfficientNet-B7':'EfficientNet-B7 accuracy', 'GHI CHÚ NGHIÊN CỨU':'RESEARCH NOTE',
  'CHƯA ĐỦ BẰNG CHỨNG':'INSUFFICIENT EVIDENCE', 'Xuất ghi chú':'Export note', 'Lưu ý về bằng chứng':'Evidence notes',
  'Thư viện':'Library', 'của bạn.':'of your own.', 'Những nghiên cứu trong bộ sưu tập Efficient vision models.':'Research in your Efficient vision models collection.',
  'Tìm theo tên, tác giả hoặc năm…':'Search by title, author, or year…', 'Tìm tài liệu':'Search papers',
  'Bộ sưu tập được nhập từ pipeline local. Thêm PDF bằng lệnh build corpus, sau đó khởi động lại giao diện.':'This collection comes from your local pipeline. Add PDFs with the build corpus command, then restart the workspace.',
  'Mạch':'Your research', 'nghiên cứu.':'in progress.', 'Các câu hỏi trong phiên này. Đóng hoặc tải lại tab sẽ xóa lịch sử.':'Questions from this session. Closing or reloading the tab clears this history.',
  'SỔ BẰNG CHỨNG':'EVIDENCE NOTEBOOK', 'Nguồn gốc':'The source', 'của một câu trả lời.':'behind an answer.',
  'Đặt câu hỏi để xem những đoạn trích, số trang và tài liệu liên quan ngay tại đây.':'Ask a question to see relevant excerpts, page numbers, and papers here.',
  'CÁCH LÀM VIỆC':'HOW IT WORKS', 'Chọn tài liệu cần đọc':'Choose your papers', 'Đặt câu hỏi cụ thể':'Ask a specific question',
  'Mở nguồn để kiểm chứng':'Open the source to verify', 'Chỉ tìm trong bộ sưu tập của bạn':'Searches only your collection',
  'Đóng cài đặt':'Close settings', 'Kết nối cách bạn đọc.':'Read on your terms.',
  'Dùng bằng chứng offline, hoặc kết nối model để tổng hợp câu trả lời.':'Use offline evidence, or connect a model to synthesize answers.',
  'Nhà cung cấp':'Provider', 'Trích nguyên văn · Không cần key':'Direct quotes · No key needed',
  'Key mặc định trên máy':'Local default key', 'Tổng hợp bằng model của bạn':'Synthesize with your model',
  'Lấy API key ↗':'Get an API key ↗', 'Hiện':'Show', 'Ẩn':'Hide',
  'Để trống để dùng Groq mặc định':'Leave blank to use default Groq',
  'Model tương thích Chat Completions. Nhập đúng ID được cấp quyền trên tài khoản của bạn.':'Use a Chat Completions model ID available to your account.',
  'Kiểm tra kết nối':'Test connection', 'Kiểm tra quyền truy cập model, không tạo câu trả lời.':'Checks model access without generating an answer.',
  'Key nhập ở đây chỉ giữ trong tab. Key Groq mặc định nằm trong cấu hình local trên máy, không gửi về trình duyệt. Câu hỏi và đoạn trích được gửi tới nhà cung cấp đã chọn; phí API tính trên tài khoản tương ứng.':'Keys entered here stay in this tab. The default Groq key is stored in local server configuration and is never sent to the browser. Questions and excerpts are sent to the selected provider; API usage is billed to that account.',
  'Số đoạn bằng chứng':'Evidence excerpts', 'Mỗi câu hỏi':'Per question', '3 đoạn':'3 excerpts', '5 đoạn':'5 excerpts', '10 đoạn':'10 excerpts', '15 đoạn':'15 excerpts',
  'Xóa key tùy chỉnh':'Clear custom key', 'Áp dụng':'Apply', 'TÀI LIỆU NGUỒN':'SOURCE PAPER', 'Đóng tài liệu':'Close paper',
  '← Trang trước':'← Previous', 'Trang sau →':'Next →', 'Mở PDF ↗':'Open PDF ↗', 'Trang tài liệu nguồn':'Source document page',
  'Chọn đúng hai tài liệu trên bàn để so sánh.':'Select exactly two papers on your desk to compare.',
  'Trang bìa':'Cover of', 'Chọn':'Select', 'Mở':'Open', 'Đọc paper ↗':'Read paper ↗',
  'Không có tài liệu khớp với tìm kiếm.':'No papers match your search.',
  'Chưa có đủ bằng chứng để trả lời chắc chắn. Hãy thử câu hỏi cụ thể hơn hoặc chọn thêm tài liệu. Bạn vẫn có thể kiểm tra các đoạn tìm được ở sổ bằng chứng.':'There is not enough evidence for a reliable answer. Try a more specific question or select more papers. You can still review the retrieved excerpts in the evidence notebook.',
  'Xem trang gốc ↗':'View source page ↗', 'Chưa đủ bằng chứng':'Insufficient evidence',
  'Chưa có câu hỏi nào. Bắt đầu tại bàn nghiên cứu.':'No questions yet. Start at the research desk.',
  'Hãy nhập câu hỏi.':'Enter a question.', 'Chọn ít nhất một tài liệu.':'Select at least one paper.', 'Chọn đúng hai tài liệu để so sánh.':'Select exactly two papers to compare.',
  'Nhập API key trong Kết nối model trước khi hỏi.':'Enter an API key in Connect model before asking.', 'Đang đọc…':'Reading…',
  'Để trống key: dùng Groq mặc định trên máy. Key mới sẽ được ưu tiên.':'Leave the key blank to use the local Groq default. A custom key takes priority.',
  'Chưa có key mặc định. Nhập key để kết nối.':'No default key configured. Enter a key to connect.',
  'Nhập API key và model trước khi áp dụng.':'Enter an API key and model before applying.',
  'Đã áp dụng cấu hình cho tab này.':'Settings applied to this tab.', 'Nhập API key và model để kiểm tra.':'Enter an API key and model to test.',
  'Đang kiểm tra quyền truy cập…':'Checking model access…',
  'Đã xóa key tùy chỉnh và khôi phục cấu hình mặc định.':'Custom key cleared. Default settings restored.',
  'Không tải được trang. Thử mở PDF gốc.':'Could not load the page. Try opening the original PDF.',
  'Đã xuất ghi chú Markdown.':'Markdown note exported.', 'Chưa tải được bộ sưu tập':'Could not load the collection',
  'Bằng chứng':'Evidence', 'trang':'page',
  'Key có quyền truy cập model. Chưa thực hiện sinh câu trả lời.':'The key has access to this model. No answer has been generated.',
  'API key không hợp lệ hoặc đã hết hiệu lực. Kiểm tra lại trong Kết nối model.':'The API key is invalid or expired. Check it in Connect model.',
  'Tài khoản API đã chạm giới hạn hoặc hết hạn mức. Kiểm tra billing rồi thử lại.':'The API account has reached its rate or usage limit. Check billing and try again.',
  'Chưa kết nối được nhà cung cấp API. Kiểm tra mạng và thử lại.':'Could not reach the API provider. Check your connection and try again.',
  'Model không tồn tại hoặc key chưa có quyền truy cập model này.':'The model does not exist or this key does not have access.',
  'Model không hỗ trợ cấu hình sinh hiện tại. Thử model tương thích Chat Completions như gpt-4o-mini.':'This model does not support the current generation settings. Choose a compatible Chat Completions model.',
  'Thiếu SDK OpenAI. Cài thêm gói API theo hướng dẫn README.':'The API SDK is missing. Install the API package as described in the README.',
  'Yêu cầu chưa hoàn thành. Thử lại hoặc kiểm tra pipeline trong Terminal.':'The request could not be completed. Try again or check the pipeline in Terminal.',
  'Chưa hoàn thành yêu cầu. Vui lòng thử lại.':'The request could not be completed. Please try again.',
  'Nhập API key trong phần Kết nối model.':'Enter an API key in Connect model.', 'API key không khớp nhà cung cấp đã chọn.':'The API key does not match the selected provider.',
  'Dữ liệu không hợp lệ. Kiểm tra câu hỏi, model và số bằng chứng.':'Invalid request. Check the question, model, and evidence count.',
  'Đang xử lý yêu cầu khác. Vui lòng thử lại sau.':'Other requests are being processed. Please try again shortly.',
  'Ngôn ngữ không được hỗ trợ.':'Unsupported language.', 'Cấu hình không được hỗ trợ.':'Unsupported configuration.',
  'Chế độ truy xuất không được hỗ trợ.':'Unsupported retrieval mode.', 'Danh sách tài liệu không hợp lệ.':'Invalid paper selection.',
};
function t(value) {
  if (language !== 'en' || typeof value !== 'string') return value;
  const key = value.trim();
  if (Object.hasOwn(english, key)) return value.replace(key, english[key]);
  return value
    .replace(/^Các key Groq đang bị giới hạn\. Thử lại sau khoảng (\d+) giây, hoặc dùng Gemini\. Các key có thể dùng chung hạn mức\.$/, 'The Groq keys are rate limited. Retry in about $1 seconds, or use Gemini. Keys may share a quota.')
    .replace(/^(\d+) tài liệu$/, '$1 papers')
    .replace(/^(\d+) trang · (\d+) đoạn trích$/, '$1 pages · $2 excerpts')
    .replace(/^(\d+) papers · Chọn nguồn cho câu hỏi của bạn$/, '$1 papers · Choose sources for your question')
    .replace(/^(\d+) papers · (\d+) trang$/, '$1 papers · $2 pages')
    .replace(/^Câu hỏi và đoạn trích sẽ được gửi tới /, 'Questions and excerpts will be sent to ')
    .replace(/^Trích đoạn offline/, 'Offline excerpts')
    .replace(/ giây · (\d+) bằng chứng$/, ' seconds · $1 excerpts')
    .replace(/^(\d+) trích dẫn · Mở ghi chú ↗$/, '$1 citations · Open note ↗')
    .replace(/ · tr\. (\d+)$/, ' · p. $1')
    .replace(/ · TRANG (\d+)$/, ' · PAGE $1')
    .replace(/ \/ TÀI LIỆU NGUỒN$/, ' / SOURCE PAPER')
    .replace(/ và cộng sự$/, ' et al.');
}
// Capture authored HTML copy once, before dynamic rendering starts.
const staticCopy = [];
const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
while (walker.nextNode()) {
  const node = walker.currentNode;
  if (node.parentElement?.closest('script,style')) continue;
  if (Object.hasOwn(english, node.textContent.trim())) staticCopy.push([node, node.textContent]);
}
const staticAttributes = [];
for (const element of document.querySelectorAll('[aria-label],[placeholder],[alt]')) {
  for (const attr of ['aria-label', 'placeholder', 'alt']) {
    const value = element.getAttribute(attr);
    if (value && Object.hasOwn(english, value.trim())) staticAttributes.push([element, attr, value]);
  }
}
function setLanguage(next) {
  language = next === 'en' ? 'en' : 'vi';
  document.documentElement.lang = language;
  document.getElementById('language').value = language;
  for (const [node, original] of staticCopy) if (node.isConnected) node.textContent = t(original);
  for (const [element, attr, original] of staticAttributes) element.setAttribute(attr, t(original));
  try { localStorage.setItem('researchpilot.language', language); } catch (_) {}
}
