import os

import requests
import streamlit as st


def ambil_youtube_key():
    try:
        key = st.secrets.get("YOUTUBE_API_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("YOUTUBE_API_KEY", "")


@st.cache_data(ttl=86400, show_spinner=False)
def cari_video_youtube(judul, artis):
    """Mencari satu video YouTube yang cocok dengan lagu."""
    key = ambil_youtube_key()
    if not key:
        return None, "API key YouTube belum diatur."

    try:
        response = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "q": f"{judul} {artis} official audio",
                "type": "video",
                "videoCategoryId": "10",      # kategori Music
                "videoEmbeddable": "true",
                "maxResults": 1,
                "key": key,
            },
            timeout=15,
        )
        response.raise_for_status()
        items = response.json().get("items", [])

        if not items:
            return None, "Video lagu tidak ditemukan."
        return items[0]["id"]["videoId"], None

    except requests.exceptions.RequestException as error:
        return None, f"Gagal menghubungi YouTube: {error}"
    except (KeyError, ValueError, TypeError):
        return None, "Data dari YouTube tidak dapat dibaca."