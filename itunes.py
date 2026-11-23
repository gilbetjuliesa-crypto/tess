import requests


def ambil_lagu_itunes(kata_kunci, kode_negara="US"):
    """Mengambil lagu dari iTunes Search API (Pertemuan 12).

    kode_negara = kode 2 huruf toko iTunes, misalnya ID, US, JP.
    Mengembalikan (daftar_lagu, pesan_error).
    daftar_lagu berupa list of dictionary, satu dictionary per lagu.
    """
    url_api = "https://itunes.apple.com/search"
    params = {
        "term": kata_kunci,
        "media": "music",
        "entity": "song",
        "country": kode_negara,
        "limit": 200,
    }

    try:
        response = requests.get(url_api, params=params, timeout=15)

        if response.status_code != 200:
            return [], f"iTunes mengembalikan status {response.status_code}."

        data = response.json()
    except Exception as error:
        return [], f"Gagal mengambil data dari iTunes: {error}"

    daftar_lagu = []
    id_sudah_ada = set()

    for item in data.get("results", []):
        # Lewati data yang tidak lengkap
        if "trackId" not in item or "trackTimeMillis" not in item:
            continue

        id_lagu = str(item["trackId"])

        # Lewati lagu yang sudah masuk (hindari duplikat)
        if id_lagu in id_sudah_ada:
            continue
        id_sudah_ada.add(id_lagu)

        daftar_lagu.append({
            "id": id_lagu,
            "judul": item.get("trackName", "Tanpa judul"),
            "artis": item.get("artistName", "Tidak diketahui"),
            "album": item.get("collectionName", "-"),
            "genre": item.get("primaryGenreName", "-"),
            "durasi_detik": int(item["trackTimeMillis"] / 1000),
            "tautan": item.get("trackViewUrl", ""),
            "preview": item.get("previewUrl", ""),
            "gambar": item.get("artworkUrl100", ""),
        })

    return daftar_lagu, ""