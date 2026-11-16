"""Kiểm cân bằng Bước 6: mỗi dòng quét mã phải được tính, bị loại vì lý do bình thường, hoặc vào ngoại lệ.
Chạy ở thư mục gốc dự án: python bang_chung/kiem_can_bang.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import config, db, tu_dong  # noqa: E402

k = db.ket_noi()
du = {r[0] for r in k.execute(tu_dong.DU_DIEU_KIEN)}
ngoai_le = list(k.execute(tu_dong.NGOAI_LE))
nhom = {}
for ma_sv, phut_tre, co_dang_ky in k.execute(
        """SELECT d.ma_sv, d.phut_tre, k.ma_sv IS NOT NULL FROM diem_danh d
           LEFT JOIN dang_ky k ON k.ma_sv = d.ma_sv AND k.ma_phien = UPPER(d.ma_phien)"""):
    if not co_dang_ky or not (phut_tre or "").strip():
        loai = "ngoai_le"
    elif int(phut_tre) > config.PHUT_TRE_TOI_DA:
        loai = "den_muon"
    elif ma_sv in du:
        loai = "duoc_tinh"
    else:
        loai = "chua_du_2_phien"
    nhom[loai] = nhom.get(loai, 0) + 1
vao = k.execute("SELECT COUNT(*) FROM diem_danh").fetchone()[0]
print(f"Vào: {vao} dòng quét · Ra: {sum(nhom.values())} = {dict(sorted(nhom.items()))}")
print(f"Ngoại lệ theo phân loại: {nhom.get('ngoai_le', 0)} · theo truy vấn NGOAI_LE: {len(ngoai_le)}")
dat = sum(nhom.values()) == vao and nhom.get("ngoai_le", 0) == len(ngoai_le)
print("ĐẠT: không dòng nào biến mất không lý do" if dat else "KHÔNG ĐẠT")
