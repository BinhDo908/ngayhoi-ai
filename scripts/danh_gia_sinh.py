"""Chấm pha SINH của RAG khi có Ollama (bổ sung cho danh_gia_rag.py, vốn chỉ chấm pha tìm).

- 10 câu hỏi vàng: câu trả lời phải KHÔNG từ chối và phải trích đúng [Điều n].
- 5 câu ngoài phạm vi, chấm hai lớp:
    lớp 1 = ngưỡng trong mã (NGUONG_OLLAMA) · lớp 2 = lối ra KHONG_DE_CAP trong câu lệnh (tắt lớp 1 để thử riêng).
Chạy: LLM_MODE=ollama NGUONG_OLLAMA=0.513 python scripts/danh_gia_sinh.py
"""
import json
import re
import time

import _goc  # noqa: F401
from app import config, rag

if __name__ == "__main__":
    vang = json.loads((config.DATA / "cau_hoi_vang.json").read_text(encoding="utf-8"))
    ngoai = json.loads((config.DATA / "cau_hoi_ngoai.json").read_text(encoding="utf-8"))
    print(f"Mô hình sinh: {config.MO_HINH_SINH} · nhúng: {config.MO_HINH_NHUNG} · ngưỡng lớp 1: {rag.nguong()}")
    dung = 0
    for c in vang:
        t = time.time(); kq = rag.hoi(c["hoi"]); giay = time.time() - t
        so = c["dieu"].split()[-1]
        tu_choi = rag.TU_CHOI.split(".")[0] in kq["tra_loi"]     # câu từ chối có gắn [Điều n] vẫn là từ chối
        ok = not tu_choi and re.search(rf"\[Điều {so}(\.\d+)?\]", kq["tra_loi"]) is not None
        dung += ok
        print(f"{'✓' if ok else '✕'} {c['hoi']} (cần [Điều {so}], {giay:.1f}s)\n    → {kq['tra_loi'][:220]}")
    print(f"Trả lời đúng, trích đúng Điều: {dung}/{len(vang)}\n")

    chan1 = chan2 = 0
    ng_goc = config.NGUONG_OLLAMA
    for q in ngoai:
        kq1 = rag.hoi(q)
        config.NGUONG_OLLAMA = 0.0                     # tắt lớp 1 để thử riêng lớp 2
        kq2 = rag.hoi(q)
        config.NGUONG_OLLAMA = ng_goc
        c1 = kq1.get("lop_tu_choi") == 1
        c2 = kq2.get("lop_tu_choi") == 2
        chan1 += c1; chan2 += c2
        print(f"{q} (điểm {kq1['nguon'][0]['diem']})\n    lớp 1: {'chặn' if c1 else 'LỌT'}"
              f" · lớp 2 (tắt lớp 1): {'chặn' if c2 else 'LỌT'} → {kq2['tra_loi'][:160]}")
    print(f"Ngoài phạm vi bị chặn: lớp 1 {chan1}/{len(ngoai)} · lớp 2 {chan2}/{len(ngoai)}")
