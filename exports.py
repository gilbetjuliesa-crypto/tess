import json
from io import BytesIO
from datetime import datetime

import pandas as pd

from playlist import format_durasi


def buat_dataframe(playlist):
    kolom = [
        "No", "Judul Lagu", "Artis", "Album", "Genre",
        "Durasi", "Durasi (detik)", "Link Lagu", "Preview"
    ]

    baris = []
    for nomor, lagu in enumerate(playlist, start=1):
        baris.append({
            "No": nomor,
            "Judul Lagu": lagu["judul"],
            "Artis": lagu["artis"],
            "Album": lagu["album"],
            "Genre": lagu["genre"],
            "Durasi": format_durasi(lagu["durasi_detik"]),
            "Durasi (detik)": lagu["durasi_detik"],
            "Link Lagu": lagu["tautan"],
            "Preview": lagu["preview"]
        })

    return pd.DataFrame(baris, columns=kolom)


def buat_file_excel(playlist, nama, kegiatan, target_menit, alasan):
    buffer = BytesIO()
    df = buat_dataframe(playlist)

    ringkasan = pd.DataFrame([{
        "Nama Playlist": nama,
        "Jenis Kegiatan": kegiatan,
        "Durasi Target (menit)": target_menit,
        "Durasi Aktual (menit)": round(
            sum(lagu["durasi_detik"] for lagu in playlist) / 60, 2
        ),
        "Jumlah Lagu": len(playlist),
        "Alasan AI": alasan
    }])

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        ringkasan.to_excel(writer, sheet_name="Ringkasan", index=False)
        df.to_excel(writer, sheet_name="Daftar Lagu", index=False)

    buffer.seek(0)
    return buffer.getvalue()


def buat_data_json(playlist, nama, kegiatan, target_menit, alasan):
    total_detik = sum(lagu["durasi_detik"] for lagu in playlist)

    data = {
        "nama_playlist": nama,
        "tagline": "Playlist yang pas dengan durasi kegiatanmu.",
        "jenis_kegiatan": kegiatan,
        "durasi_target_menit": target_menit,
        "durasi_aktual_detik": total_detik,
        "jumlah_lagu": len(playlist),
        "alasan_ai": alasan,
        "dibuat_pada": datetime.now().isoformat(timespec="seconds"),
        "lagu": playlist
    }

    return json.dumps(data, ensure_ascii=False, indent=4)
