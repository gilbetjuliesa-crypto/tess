import pandas as pd


# ---------------------------------------------------------
# STRUKTUR DATA DAN ALGORITMA PEMILIHAN LAGU
# ---------------------------------------------------------
def pilih_lagu(daftar_lagu, target_menit):
    """
    Algoritma greedy:
    lagu diurutkan dari durasi terpanjang, lalu dipilih selama
    durasinya tidak melewati sisa waktu target.
    """
    target_detik = int(target_menit * 60)

    if not daftar_lagu:
        return []

    # List of dictionary diubah menjadi DataFrame agar mudah diurutkan.
    data = pd.DataFrame(daftar_lagu)
    data = data.sort_values(
        by="durasi_detik",
        ascending=False
    )

    lagu_tersedia = data.to_dict(orient="records")
    playlist = []
    total_detik = 0

    for lagu in lagu_tersedia:
        sisa_waktu = target_detik - total_detik

        if lagu["durasi_detik"] <= sisa_waktu:
            playlist.append(lagu)
            total_detik += lagu["durasi_detik"]

        if total_detik == target_detik:
            break

    # Jika masih ada selisih kecil, periksa satu lagu yang paling
    # mendekati sisa waktu. Lagu ditambahkan hanya jika hasilnya
    # lebih dekat ke target daripada playlist sebelumnya.
    if total_detik < target_detik:
        lagu_terpilih = {lagu["id"] for lagu in playlist}
        sisa_lagu = [
            lagu for lagu in lagu_tersedia
            if lagu["id"] not in lagu_terpilih
        ]

        if sisa_lagu:
            kandidat = min(
                sisa_lagu,
                key=lambda item: abs(
                    target_detik - (total_detik + item["durasi_detik"])
                )
            )
            total_baru = total_detik + kandidat["durasi_detik"]

            if abs(target_detik - total_baru) < abs(target_detik - total_detik):
                playlist.append(kandidat)

    return playlist

def format_durasi(detik):
    menit = int(detik) // 60
    sisa_detik = int(detik) % 60
    return f"{menit}:{sisa_detik:02d}"