import json
import os
import re
import requests
import streamlit as st
from playlist import format_durasi


def ambil_api_key():
    """Membaca API key dari Streamlit Secrets atau environment variable."""
    try:
        key = st.secrets.get("GEMINI_API_KEY", "")
        if key:
            return key
    except Exception:
        pass

    return os.getenv("GEMINI_API_KEY", "")


def buat_rekomendasi_ai(playlist, kegiatan, target_menit):
    """
    Mengirim hasil playlist ke Gemini untuk membuat nama,
    urutan lagu, dan alasan penyusunan.
    """
    api_key = ambil_api_key()

    if not api_key:
        return None, "API key Gemini belum diatur."

    ringkasan_lagu = []
    for nomor, lagu in enumerate(playlist, start=1):
        ringkasan_lagu.append({
            "id": lagu["id"],
            "judul": lagu["judul"],
            "artis": lagu["artis"],
            "genre": lagu["genre"],
            "durasi": format_durasi(lagu["durasi_detik"])
        })

    instruksi = f"""
Kamu adalah kurator musik. Buat rekomendasi untuk playlist berdasarkan data lagu berikut.

Jenis kegiatan: {kegiatan}
Durasi target: {target_menit} menit

Daftar lagu yang tersedia:
{json.dumps(ringkasan_lagu, ensure_ascii=False)}

Tugas:
1. Buat nama playlist yang singkat, menarik, dan sesuai kegiatan.
2. Susun urutan lagu agar alurnya enak didengarkan untuk kegiatan tersebut.
3. Jelaskan alasan penyusunan playlist dalam bahasa Indonesia.
4. Gunakan hanya ID lagu yang tersedia. Jangan membuat lagu atau ID baru.
5. Semua lagu harus tetap dimasukkan ke dalam urutan.

Balas hanya dengan JSON valid menggunakan format:
{{
  "nama_playlist": "Nama playlist",
  "urutan_id": ["id_lagu_1", "id_lagu_2"],
  "alasan": "Penjelasan singkat..."
}}
"""

    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-3.5-flash:generateContent"
    )

    try:
        response = requests.post(
            endpoint,
            params={"key": api_key},
            json={
                "contents": [
                    {"parts": [{"text": instruksi}]}
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "responseMimeType": "application/json"
                }
            },
            timeout=45
        )
        response.raise_for_status()
        hasil = response.json()

        teks = hasil["candidates"][0]["content"]["parts"][0]["text"]
        teks = teks.strip()

        # Menghapus penanda code block jika model tetap mengirimkannya.
        teks = re.sub(r"^```(?:json)?\s*", "", teks)
        teks = re.sub(r"\s*```$", "", teks)

        rekomendasi = json.loads(teks)
        return rekomendasi, None

    except requests.exceptions.RequestException as error:
        return None, f"Gagal menghubungi Gemini: {error}"
    except (KeyError, IndexError, ValueError, TypeError):
        return None, "Jawaban Gemini tidak dapat dibaca. Coba buat playlist lagi."


def terapkan_urutan_ai(playlist, rekomendasi):
    """Memastikan AI hanya mengurutkan lagu yang benar-benar tersedia."""
    if not rekomendasi:
        return playlist

    data_lagu = {lagu["id"]: lagu for lagu in playlist}
    urutan = rekomendasi.get("urutan_id", [])

    hasil = []
    sudah_dimasukkan = set()

    for id_lagu in urutan:
        id_lagu = str(id_lagu)
        if id_lagu in data_lagu and id_lagu not in sudah_dimasukkan:
            hasil.append(data_lagu[id_lagu])
            sudah_dimasukkan.add(id_lagu)

    # Lagu yang tidak disebutkan AI tetap dimasukkan.
    for lagu in playlist:
        if lagu["id"] not in sudah_dimasukkan:
            hasil.append(lagu)

    return hasil


def nama_playlist_default(kegiatan):
    nama = {
        "Belajar": "Focus Mode",
        "Lari": "Run The Rhythm",
        "Olahraga": "Power in Motion",
        "Santai": "Slow Moments",
        "Perjalanan": "On The Way",
        "Bekerja": "Work Flow"
    }
    return nama.get(kegiatan, "My Perfect Playlist")