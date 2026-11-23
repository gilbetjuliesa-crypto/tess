import json
from datetime import datetime
from io import BytesIO

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from itunes_api import ambil_lagu_itunes
from playlist import pilih_lagu, format_durasi
from gemini_ai import (
    buat_rekomendasi_ai,
    terapkan_urutan_ai,
    nama_playlist_default,
)
from youtube_api import cari_video_youtube

# ---------------------------------------------------------
# DAFTAR 8 FITUR APLIKASI
# 1. Pengaturan playlist (durasi, kegiatan, genre, artis)
# 2. Pilih negara (toko iTunes + kata kunci bawaan negara)
# 3. Pencarian lagu iTunes + pemilihan lagu sesuai durasi (greedy)
# 4. Rekomendasi Gemini (nama, urutan, alasan)
# 5. Edit playlist: keluarkan lagu, semua bagian ikut berubah
# 6. Pemutar: preview 30 detik (gratis) atau lagu penuh (YouTube)
# 7. Visualisasi (bar chart dan line chart)
# 8. Ekspor CSV, Excel, dan JSON
# ---------------------------------------------------------

# Dictionary: nama negara -> (kode negara iTunes, kata kunci bawaan)
NEGARA = {
    "Indonesia": ("ID", "pop indonesia"),
    "Amerika Serikat": ("US", "popular music"),
    "Inggris": ("GB", "uk pop"),
    "Jepang": ("JP", "j-pop"),
    "Korea Selatan": ("KR", "k-pop"),
    "India": ("IN", "bollywood"),
    "Brasil": ("BR", "musica brasileira"),
    "Prancis": ("FR", "chanson francaise"),
    "Jerman": ("DE", "deutsche hits"),
    "Australia": ("AU", "australian pop"),
}


# ---------------------------------------------------------
# SESSION STATE (Pertemuan 6)
# Script dijalankan ulang dari atas setiap ada interaksi,
# jadi hasil playlist harus disimpan di st.session_state.
# ---------------------------------------------------------
if "playlist" not in st.session_state:
    st.session_state["playlist"] = None
if "nama_playlist" not in st.session_state:
    st.session_state["nama_playlist"] = ""
if "alasan_ai" not in st.session_state:
    st.session_state["alasan_ai"] = ""
if "kegiatan" not in st.session_state:
    st.session_state["kegiatan"] = ""
if "negara" not in st.session_state:
    st.session_state["negara"] = ""
if "target_menit" not in st.session_state:
    st.session_state["target_menit"] = 0
if "ai_aktif" not in st.session_state:
    st.session_state["ai_aktif"] = False
if "pesan_ai" not in st.session_state:
    st.session_state["pesan_ai"] = ""
if "versi" not in st.session_state:
    st.session_state["versi"] = 0  # naik 1 setiap playlist baru dibuat


# ---------------------------------------------------------
# FUNGSI EKSPOR (sebelumnya di exports.py)
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# FUNGSI PROSES
# ---------------------------------------------------------
def siapkan_playlist(kata_kunci, kode_negara, genre, target_menit):
    """Ambil lagu dari iTunes lalu pilih lagu sesuai durasi.
    Mengembalikan (playlist, pesan). Jika gagal, playlist = None
    dan pesan berisi alasan kegagalan."""
    with st.spinner("Sedang mencari lagu dari iTunes..."):
        semua_lagu, pesan_error = ambil_lagu_itunes(kata_kunci, kode_negara)

    if pesan_error:
        return None, pesan_error
    if not semua_lagu:
        return None, "Lagu tidak ditemukan. Coba kata kunci atau artis lain."

    # Filter genre (kalau tidak ada yang cocok, pakai semua hasil)
    lagu_filter = semua_lagu
    if genre != "Semua genre":
        hasil_filter = [
            lagu for lagu in semua_lagu
            if genre.lower() in lagu["genre"].lower()
        ]
        if hasil_filter:
            lagu_filter = hasil_filter
        else:
            st.info(
                "Genre yang dipilih tidak ditemukan pada hasil pencarian. "
                "Aplikasi menampilkan hasil lagu dari pencarian utama."
            )

    with st.spinner("Menyusun lagu sesuai durasi kegiatan..."):
        playlist = pilih_lagu(lagu_filter, target_menit)

    if not playlist:
        return None, "Belum ada lagu yang dapat dimasukkan ke playlist."
    return playlist, ""


# ---------------------------------------------------------
# FUNGSI TAMPILAN
# Semua fungsi di bawah menerima data yang SAMA (lagu_aktif),
# jadi kalau playlist diedit, semua bagian ikut berubah.
# ---------------------------------------------------------
def edit_playlist(playlist):
    """Fitur 5: pengguna mengeluarkan lagu. Mengembalikan lagu_aktif."""
    st.subheader("✂️ Edit Playlist")
    st.caption(
        "Keluarkan lagu yang tidak diinginkan. Ringkasan, daftar, pemutar, "
        "grafik, dan file download ikut menyesuaikan."
    )

    pilihan_lagu = []
    for nomor, lagu in enumerate(playlist, start=1):
        pilihan_lagu.append(f"{nomor}. {lagu['judul']} - {lagu['artis']}")

    # key memakai nomor versi supaya pilihan lama tidak terbawa
    # ketika playlist baru dibuat.
    dikeluarkan = st.multiselect(
        "Lagu yang dikeluarkan",
        pilihan_lagu,
        key=f"keluar_{st.session_state['versi']}",
    )

    lagu_aktif = []
    for i in range(len(playlist)):
        if pilihan_lagu[i] not in dikeluarkan:
            lagu_aktif.append(playlist[i])
    return lagu_aktif


def tampilkan_ringkasan(lagu_aktif, target_menit):
    total_detik = sum(lagu["durasi_detik"] for lagu in lagu_aktif)
    total_menit = total_detik / 60
    selisih = abs(target_menit - total_menit)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Durasi Target", f"{target_menit} menit")
    col2.metric("Durasi Playlist", f"{total_menit:.1f} menit")
    col3.metric("Jumlah Lagu", len(lagu_aktif))
    col4.metric("Selisih Waktu", f"{selisih:.1f} menit")


def tampilkan_daftar(lagu_aktif):
    st.subheader("📋 Daftar Lagu")
    for nomor, lagu in enumerate(lagu_aktif, start=1):
        kolom_gambar, kolom_info, kolom_durasi = st.columns([1, 6, 1])

        with kolom_gambar:
            if lagu["gambar"]:
                st.image(lagu["gambar"], width=62)
            else:
                st.write("🎵")

        with kolom_info:
            st.markdown(f"**{nomor}. {lagu['judul']}**")
            st.caption(f"{lagu['artis']} • {lagu['album']} • {lagu['genre']}")
            if lagu["tautan"]:
                st.markdown(f"[Buka lagu di iTunes]({lagu['tautan']})")

        with kolom_durasi:
            st.markdown(f"**{format_durasi(lagu['durasi_detik'])}**")

        st.markdown("---")


def tampilkan_pemutar(lagu_aktif):
    """Fitur 6: satu pemutar untuk semua lagu di playlist."""
    st.subheader("▶ Pemutar Lagu")

    daftar_pilihan = []
    for nomor, lagu in enumerate(lagu_aktif, start=1):
        daftar_pilihan.append(f"{nomor}. {lagu['judul']} - {lagu['artis']}")

    pilihan = st.selectbox("Pilih lagu", daftar_pilihan)
    mode = st.radio(
        "Mode putar",
        ["Preview 30 detik (gratis)", "Lagu penuh (YouTube)"],
    )

    lagu = lagu_aktif[daftar_pilihan.index(pilihan)]
    st.write(f"**{lagu['judul']}** - {lagu['artis']}")

    if mode == "Preview 30 detik (gratis)":
        if lagu["preview"]:
            st.audio(lagu["preview"])
        else:
            st.info("Preview tidak tersedia untuk lagu ini.")
    else:
        video_id, pesan_yt = cari_video_youtube(lagu["judul"], lagu["artis"])
        if video_id:
            st.video(f"https://www.youtube.com/watch?v={video_id}")
        else:
            st.warning(pesan_yt)
            if lagu["preview"]:
                st.caption("Memutar preview 30 detik sebagai cadangan.")
                st.audio(lagu["preview"])


def tampilkan_grafik(lagu_aktif, target_menit):
    """Fitur 7: visualisasi dengan Matplotlib (Pertemuan 11)."""
    st.header("📊 Visualisasi Playlist")

    nama_lagu = []
    durasi_lagu = []
    akumulasi = []
    total_sementara = 0

    for lagu in lagu_aktif:
        nama_lagu.append(f"{lagu['judul'][:28]} - {lagu['artis'][:18]}")
        durasi_lagu.append(lagu["durasi_detik"] / 60)
        total_sementara += lagu["durasi_detik"]
        akumulasi.append(total_sementara / 60)

    urutan = list(range(1, len(lagu_aktif) + 1))

    # Grafik 1: bar horizontal (cocok untuk label panjang)
    st.subheader("Durasi setiap lagu")
    fig1, ax1 = plt.subplots(figsize=(10, max(4, len(lagu_aktif) * 0.32)))
    ax1.barh(nama_lagu, durasi_lagu)
    ax1.invert_yaxis()  # lagu pertama berada di paling atas
    ax1.set_title("Durasi Setiap Lagu")
    ax1.set_xlabel("Durasi (menit)")
    ax1.set_ylabel("Lagu")
    ax1.grid(axis="x", linestyle="--", alpha=0.5)
    plt.tight_layout()
    st.pyplot(fig1)
    plt.close(fig1)  # tutup figure supaya tidak menumpuk di memori

    # Grafik 2: line chart akumulasi durasi + garis target
    st.subheader("Akumulasi durasi")
    fig2, ax2 = plt.subplots(figsize=(10, 4.5))
    ax2.plot(
        urutan, akumulasi,
        marker="o", label="Akumulasi durasi playlist"
    )
    ax2.plot(
        [0, len(lagu_aktif)], [target_menit, target_menit],
        linestyle="--", label=f"Target {target_menit} menit"
    )
    ax2.set_title("Perkembangan Durasi Playlist")
    ax2.set_xlabel("Jumlah lagu")
    ax2.set_ylabel("Total durasi (menit)")
    ax2.legend()
    ax2.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    st.pyplot(fig2)
    plt.close(fig2)


def tampilkan_download(lagu_aktif, nama, kegiatan, target_menit, alasan):
    """Fitur 8: ekspor CSV, Excel, JSON (Pertemuan 9 dan 10)."""
    st.header("📥 Download Playlist")

    df_export = buat_dataframe(lagu_aktif)
    csv_data = df_export.to_csv(index=False).encode("utf-8-sig")
    excel_data = buat_file_excel(
        lagu_aktif, nama, kegiatan, target_menit, alasan
    )
    json_data = buat_data_json(
        lagu_aktif, nama, kegiatan, target_menit, alasan
    )

    col_csv, col_excel, col_json = st.columns(3)

    with col_csv:
        st.download_button(
            "Download CSV",
            data=csv_data,
            file_name="music_playlist.csv",
            mime="text/csv",
        )

    with col_excel:
        st.download_button(
            "Download Excel",
            data=excel_data,
            file_name="music_playlist.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with col_json:
        st.download_button(
            "Download JSON",
            data=json_data.encode("utf-8"),
            file_name="music_playlist.json",
            mime="application/json",
        )


# ---------------------------------------------------------
# TAMPILAN UTAMA: PENGATURAN (Fitur 1 dan 2)
# ---------------------------------------------------------
st.title("🎧 Music Playlist")
st.write("Playlist yang pas dengan durasi kegiatanmu.")
st.caption("Temukan susunan lagu yang sesuai dengan waktu dan aktivitasmu.")

st.subheader("Pengaturan Playlist")

col_a, col_b = st.columns(2)
with col_a:
    target_menit = st.number_input(
        "Durasi kegiatan (menit)",
        min_value=10,
        max_value=360,
        value=90,
        step=5,
    )
    genre = st.selectbox(
        "Genre musik",
        [
            "Semua genre", "Pop", "Rock", "Hip-Hop/Rap", "R&B/Soul",
            "Dance", "Electronic", "Indie", "Jazz", "Classical",
            "Alternative", "K-Pop", "Soundtrack",
        ],
    )
    negara = st.selectbox("Negara", list(NEGARA.keys()))
with col_b:
    kegiatan = st.selectbox(
        "Jenis kegiatan",
        ["Belajar", "Lari", "Olahraga", "Santai", "Perjalanan", "Bekerja"],
    )
    artis = st.text_input("Artis (opsional)", placeholder="Contoh: Taylor Swift")

buat_playlist = st.button("✨ Buat Playlist", type="primary")
st.caption("Sumber lagu: iTunes Search API (katalog toko iTunes negara terpilih)")


# ---------------------------------------------------------
# PROSES: dijalankan saat tombol ditekan (Fitur 3 dan 4)
# ---------------------------------------------------------
if buat_playlist:
    kode_negara, kata_negara = NEGARA[negara]

    # Tentukan kata kunci pencarian
    if artis.strip() != "":
        kata_kunci = artis.strip()
    elif genre != "Semua genre":
        kata_kunci = genre
    else:
        kata_kunci = kata_negara

    hasil_playlist, pesan = siapkan_playlist(
        kata_kunci, kode_negara, genre, target_menit
    )

    if hasil_playlist is None:
        st.warning(pesan)
        st.session_state["playlist"] = None
    else:
        with st.spinner("Gemini sedang menyusun nama dan urutan lagu..."):
            rekomendasi, pesan_ai = buat_rekomendasi_ai(
                hasil_playlist, kegiatan, target_menit
            )

        if rekomendasi:
            hasil_playlist = terapkan_urutan_ai(hasil_playlist, rekomendasi)
            nama = rekomendasi.get(
                "nama_playlist", nama_playlist_default(kegiatan)
            )
            alasan = rekomendasi.get(
                "alasan", "Playlist disusun sesuai jenis kegiatan."
            )
            st.session_state["ai_aktif"] = True
        else:
            nama = nama_playlist_default(kegiatan)
            alasan = (
                "Urutan lagu dibuat berdasarkan hasil pemilihan durasi. "
                "Tambahkan GEMINI_API_KEY untuk mendapatkan nama dan "
                "penjelasan playlist dari Gemini AI."
            )
            st.session_state["ai_aktif"] = False

        # Simpan semua hasil ke session_state
        st.session_state["playlist"] = hasil_playlist
        st.session_state["nama_playlist"] = nama
        st.session_state["alasan_ai"] = alasan
        st.session_state["kegiatan"] = kegiatan
        st.session_state["negara"] = negara
        st.session_state["target_menit"] = target_menit
        st.session_state["pesan_ai"] = pesan_ai
        st.session_state["versi"] += 1


# ---------------------------------------------------------
# HASIL PLAYLIST
# ---------------------------------------------------------
if st.session_state["playlist"]:
    playlist = st.session_state["playlist"]
    nama = st.session_state["nama_playlist"]
    alasan = st.session_state["alasan_ai"]
    kegiatan_hasil = st.session_state["kegiatan"]
    negara_hasil = st.session_state["negara"]
    target_hasil = st.session_state["target_menit"]

    st.markdown("---")
    st.header(f"🎶 {nama}")
    st.caption(
        f"Playlist untuk kegiatan {kegiatan_hasil.lower()} "
        f"• Negara: {negara_hasil}"
    )

    if st.session_state["ai_aktif"]:
        st.success("Gemini AI berhasil membuat rekomendasi playlist.")
    else:
        st.info(
            "Playlist berhasil dibuat. Gemini AI belum aktif, "
            "jadi nama dan penjelasan menggunakan rekomendasi dasar."
        )
        if st.session_state["pesan_ai"]:
            st.caption(st.session_state["pesan_ai"])

    st.subheader("💡 Alasan Penyusunan")
    st.write(alasan)

    # Fitur 5: hasil edit (lagu_aktif) dipakai oleh SEMUA bagian di bawah
    lagu_aktif = edit_playlist(playlist)

    if len(lagu_aktif) == 0:
        st.warning("Semua lagu dikeluarkan. Batalkan sebagian pilihan di atas.")
    else:
        tampilkan_ringkasan(lagu_aktif, target_hasil)
        tampilkan_daftar(lagu_aktif)
        tampilkan_pemutar(lagu_aktif)
        tampilkan_grafik(lagu_aktif, target_hasil)
        tampilkan_download(
            lagu_aktif, nama, kegiatan_hasil, target_hasil, alasan
        )

else:
    st.markdown("---")
    st.header("Mulai buat playlist")
    st.write(
        "Atur durasi, kegiatan, dan negara di atas, "
        "lalu tekan **Buat Playlist**."
    )

    info1, info2, info3 = st.columns(3)
    with info1:
        st.subheader("⏱️ Sesuai Waktu")
        st.caption("Pilih durasi kegiatan dari 10 sampai 360 menit.")
    with info2:
        st.subheader("🌏 Sesuai Selera")
        st.caption("Cari lagu berdasarkan negara, genre, atau artis favorit.")
    with info3:
        st.subheader("✨ Dibantu AI")
        st.caption("Gemini membantu memberi nama dan mengurutkan playlist.")

    st.caption(
        "Catatan: ketersediaan lagu dan preview mengikuti data yang "
        "disediakan oleh iTunes Search API."
    )

st.markdown("---")
st.caption("Music Playlist • Project Praktikum Struktur Data")
