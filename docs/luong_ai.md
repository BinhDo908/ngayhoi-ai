# Luồng xử lý theo ý định người dùng và mô hình dùng ở từng bước

Mô hình chạy cục bộ qua **Ollama 0.33.1** (`OLLAMA_URL=http://localhost:11434`, không gửi dữ liệu ra ngoài):

| Mô hình | Vai trò | Dùng ở |
|---|---|---|
| `bge-m3` (1.024 chiều) | Nhúng văn bản: biến quy chế và câu hỏi thành vectơ | RAG — pha chuẩn bị và pha tìm |
| `qwen2.5:3b` (temperature 0) | Sinh câu trả lời; chọn công cụ qua `tool_calls` | RAG — pha sinh; agent — bộ lập kế hoạch |
| *(không mô hình)* TF-IDF + luật | Chế độ offline khi Ollama tắt / trên CI | RAG, agent |

`LLM_MODE=auto` (mặc định): có Ollama và đã tải `qwen2.5:3b` → chế độ `ollama`; không có → `offline`. Ô góc trên giao diện ghi chế độ đang chạy.

## Bản đồ ý định → luồng

| Ý định người dùng | Tab / API | Mô hình | Kiểm soát nằm trong mã |
|---|---|---|---|
| Xem phiên, đăng ký, hủy | Đăng ký phiên · `/api/phien`, `/api/dang-ky` | **Không** — quy tắc nghiệp vụ dùng SQL | `INSERT … SELECT … WHERE` (sức chứa, tối đa 3 phiên), `UNIQUE`, hủy trước 24 giờ, mã SV từ đăng nhập |
| Hỏi quy chế | Hỏi đáp quy chế · `/api/hoi` | `bge-m3` → `qwen2.5:3b` | Ngưỡng lớp 1, lối ra cố định lớp 2, chuẩn hóa trích dẫn |
| Nhờ tìm / đăng ký phiên bằng lời | Trợ lý đăng ký · `/api/agent` | `qwen2.5:3b` (tool_calls) | Chặn đăng ký hộ, danh sách công cụ, kiểm tham số, hành động chờ, xác nhận |
| Thống kê | Quản trị · `/api/thong-ke` | **Không** — chỉ số là SQL có định nghĩa | Hợp đồng chỉ số `docs/chi_so.md`, tập nhỏ có đáp án |
| Cộng điểm rèn luyện | Quản trị · `/api/cong-diem` | **Không** — Điều 5, 6 là quy tắc | Sổ `da_cong` + `INSERT OR IGNORE`, hàng đợi ngoại lệ |
| Tạo poster | Quản trị · `/api/poster` | **Không** mô hình chữ — nền sinh bằng thuật toán có seed | Chữ đặt bằng mã từ `noi_dung.json`, 3 phép kiểm |

Nguyên tắc (Buổi 9): bước **quy tắc** dùng mã; chỉ bước cần **hiểu ngôn ngữ** (hỏi đáp, trò chuyện) mới dùng mô hình.

## Luồng 1 · Hỏi đáp quy chế (RAG)

```
Pha chuẩn bị (scripts/nhung.py, chạy lại khi sửa quy chế)
  data/quy_che.md ──cắt theo "## Điều"──► 10 đoạn ──bge-m3──► out/chi_muc.json (nguồn, nội dung, vectơ)

Pha hỏi (app/rag.py · hoi)
  câu hỏi ──bge-m3──► vectơ ──cosine──► top-3 Điều
     │
     ├─ điểm cao nhất < 0,513 ─────────────► LỚP 1: TU_CHOI (trong mã, không gọi qwen)
     │
     └─ ≥ 0,513 ──► qwen2.5:3b, temperature 0
                     system: 4 quy tắc · 2 ví dụ hội thoại · user: <quy_che>top-3</quy_che> + câu hỏi
                        │
                        ├─ trả "KHONG_DE_CAP" ──► LỚP 2: mã đổi thành TU_CHOI
                        └─ câu trả lời ──► mã chuẩn hóa [Điều 3.1] → [Điều 3] ──► trả lời + nguồn + điểm
```

**Số đo trên máy (bang_chung/):**

| Đo | Kết quả |
|---|---|
| Recall@3, bge-m3 (`danh_gia_rag.py`) | 10/10 |
| Điểm 10 câu trong phạm vi | 0,516 – 0,703 |
| Điểm 5 câu ngoài phạm vi | 0,422 – **0,510** |
| Ngưỡng chọn | **0,513** (giữa khoảng trống; mặc định cũ 0,45 để lọt 3/5 câu ngoài phạm vi qua lớp 1) |
| Pha sinh, 10 câu hỏi vàng (`danh_gia_sinh.py`) | **10/10** trả lời đúng, trích đúng Điều |
| Câu ngoài phạm vi bị chặn | lớp 1: 5/5 · lớp 2 (tắt lớp 1 để thử riêng): 5/5 |

**Chọn câu lệnh bằng số đo** (`bang_chung/thu_cau_lenh.py`, cùng 10 câu vàng + 5 câu ngoài, lớp 1 tắt):

| Phương án | qwen2.5:3b | llama3.2 |
|---|---|---|
| A · câu lệnh gốc (4 quy tắc trước `<quy_che>`, chuỗi từ chối dài) | 2/10 · 5/5 | — |
| B · chuyển quy tắc xuống sau câu hỏi (cách sửa Buổi 6) | 2/10 · 5/5 | — |
| C · lối ra là mã `KHONG_DE_CAP` | 1/10 · 5/5 | — |
| D · quy tắc trong system + mã lối ra | 3/10 · 5/5 | — |
| E · thêm một ví dụ trong lệnh | 5/10 · 5/5 | — |
| F · đúng câu lệnh `quyche/hoi.py` Buổi 6 | 5/10 · 5/5 | 1/10 · 5/5 |
| G · trích nguyên văn rồi trả lời | 1/10 · 5/5 | — |
| H · chỉ đưa top-1 + trích | 3/10 · 4/5 | — |
| J · bỏ hẳn chuỗi từ chối khỏi lệnh | 7/10 · 5/5 | — |
| **M · system 4 quy tắc + 2 ví dụ hội thoại (đang dùng)** | **9/10 · 5/5** (10/10 sau chuẩn hóa trích dẫn) | **9/10 · 5/5** |

Nguyên nhân: với mô hình 3b và temperature 0, chuỗi từ chối dài nằm ngay trong lệnh là chuỗi "dễ chép" nhất — mô hình in câu từ chối rồi mới trả lời đúng phía sau (`KHONG_DE_CAP … đến muộn quá 10 phút không được tính…`). Ví dụ hội thoại cho mô hình thấy *khi nào* trả lời và *khi nào* từ chối, thay vì chỉ thấy câu từ chối. Kết luận này khác Buổi 6 (ở đó chuyển quy tắc xuống sau là đủ) vì câu từ chối ở đây dài hơn và lệnh gửi qua `/api/chat` với temperature 0.

## Luồng 2 · Trợ lý đăng ký (agent)

```
tin nhắn + mã SV từ đăng nhập
  │
  ├─ có mã SV 8 số khác người dùng ──► từ chối NGAY trong mã (không gọi mô hình)
  │
  └─ qwen2.5:3b (system + TOOLS, tối đa 5 vòng)
        tool_calls ──► thuc_thi (app/agent.py)
                         ├─ tên ngoài {tim_phien, xem_cho, dang_ky} ──► KHONG_CO_CONG_CU
                         ├─ tham số ngoài định nghĩa (mô hình tự bịa) ──► THAM_SO_KHONG_HOP_LE
                         ├─ tim_phien / xem_cho ──► đọc CSDL, trả kết quả về mô hình (là DỮ LIỆU)
                         └─ dang_ky(ma_phien) ──► phiên phải tồn tại và còn chỗ
                               ──► tạo hanh_dong_cho, CHƯA ghi; câu xác nhận do MÃ điền
  người dùng bấm Xác nhận ──► xac_nhan: đúng người đề nghị, mỗi hành động một lần ──► dang_ky.dang_ky ──► 201
  mọi lần gọi công cụ ──► out/nhat_ky_agent.jsonl
```

| Đo (`danh_gia_agent.py`) | offline (luật) | ollama (qwen2.5:3b) — mã gốc | ollama — sau khi sửa |
|---|---|---|---|
| Nhiệm vụ đúng | 10/10 | 9/10 | **10/10** |
| Ghi trái phép | 0 | 0 | **0** |
| Ca tiêm chỉ thị | bị lừa, đề nghị P03 → Từ chối → 0 ghi | không đề nghị ghi → 0 ghi | không đề nghị ghi → 0 ghi |

Ba sửa đổi trong `app/agent.py`, đều do số đo chỉ ra:
1. Mô hình gọi `dang_ky({"ma_phien": "22020002", "ma_phien_dau_thuc_hien": "P01"})` — nhét mã SV vào `ma_phien` và bịa tham số. Mã gốc vẫn tạo thẻ "Đăng ký 22020100 vào 22020002?". Nay `thuc_thi` từ chối tham số ngoài định nghĩa và `dang_ky` kiểm phiên tồn tại, còn chỗ trước khi tạo hành động chờ.
2. Thêm vào system: chỉ có P01–P12; nhờ đăng ký cho mã SV khác thì không gọi công cụ. Đo lại: mô hình **vẫn** gọi `dang_ky(P01, ma_phien_dang_ky=22020002)` (bị mã chặn) → lời nhắc không đủ.
3. Đăng ký hộ là quy tắc cứng nên chặn bằng mã trước khi gọi mô hình (bộ lập kế hoạch offline của giảng viên vốn đã làm vậy).

## Áp dụng từ các buổi đã thực hành

| Buổi | Bài học | Áp dụng ở đây |
|---|---|---|
| 1 | Gọi LLM cục bộ, temperature 0, câu lệnh có cấu trúc | `app/llm.py`, `qwen2.5:3b` qua Ollama |
| 6 (`quyche/`) | Ngưỡng phải đo; khoảng trống bge-m3 hẹp (0,500–0,558); thứ tự quy tắc ảnh hưởng mô hình 3b | Đo lại cho quy chế này: khoảng trống 0,510–0,516 → 0,513; thử lại cách sửa thứ tự (không đủ) → ví dụ hội thoại |
| 7 (`agent/`) | qwen2.5:3b bịa tham số (`so_thue`, `user_id`), bị tiêm chỉ thị trong lời nói; cổng trong mã mới là bảo đảm | Từ chối tham số lạ; chặn đăng ký hộ bằng mã; ghi trái phép = 0 |
| 8, 9 | Chỉ số và cộng điểm là quy tắc → SQL, không dùng AI | Thống kê, cộng điểm không gọi mô hình |
