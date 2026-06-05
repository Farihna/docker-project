import redis
import json
import time

# ──────────────────────────────────────────────
# Koneksi ke Redis (service name Docker: "redis")
# ──────────────────────────────────────────────
r = redis.Redis(
    host="redis",
    port=6379,
    db=0,
    decode_responses=True,   # semua nilai dikembalikan sebagai str, bukan bytes
)

CACHE_TTL = 300  # 5 menit


def fetch_weather_from_api(city: str) -> dict:
    """
    Simulasi pemanggilan API cuaca eksternal.
    time.sleep(2) menggantikan latensi jaringan / proses berat.
    """
    print(f"  [API]  Mengambil data cuaca untuk '{city}' dari sumber eksternal...")
    time.sleep(2)  # ← simulasi latency API

    # Data dummy — dalam produksi ini diganti response.json() dari API nyata
    return {
        "city": city,
        "temperature_c": 28,
        "humidity_pct": 75,
        "condition": "Berawan sebagian",
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


def get_weather(city: str) -> dict:
    """
    Implementasi Cache-Aside Pattern:
      1. Cek cache → jika HIT, kembalikan data dari Redis.
      2. Jika MISS, ambil dari 'API', simpan ke Redis dengan TTL, lalu kembalikan.

    Cache key format: weather:{city}
    """
    cache_key = f"weather:{city.lower()}"

    # ── Langkah 1: GET dari Redis ──────────────────────────────
    cached_value = r.get(cache_key)  # Redis GET command

    if cached_value is not None:
        # ── CACHE HIT ──────────────────────────────────────────
        remaining_ttl = r.ttl(cache_key)  # Redis TTL command — sisa waktu (detik)
        print(f"  [CACHE HIT]  Key '{cache_key}' ditemukan. TTL tersisa: {remaining_ttl} detik.")
        return json.loads(cached_value)   # deserialize JSON → dict

    # ── Langkah 2: CACHE MISS — panggil 'API' ─────────────────
    print(f"  [CACHE MISS] Key '{cache_key}' tidak ditemukan. Memanggil API...")
    weather_data = fetch_weather_from_api(city)

    # ── Langkah 3: Simpan hasil ke Redis ──────────────────────
    # Redis SET command dengan parameter EX (expire dalam detik)
    r.set(cache_key, json.dumps(weather_data), ex=CACHE_TTL)
    print(f"  [CACHE SET]  Data disimpan ke Redis. Key: '{cache_key}', TTL: {CACHE_TTL} detik.")

    return weather_data


# ──────────────────────────────────────────────
# Entrypoint — demo singkat
# ──────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  Demo Cache-Aside Pattern — get_weather('Jakarta')")
    print("=" * 55)

    print("\n[Panggilan ke-1]")
    start = time.time()
    data = get_weather("Jakarta")
    elapsed = time.time() - start
    print(f"  Hasil   : {data}")
    print(f"  Durasi  : {elapsed:.3f} detik\n")

    print("[Panggilan ke-2]")
    start = time.time()
    data = get_weather("Jakarta")
    elapsed = time.time() - start
    print(f"  Hasil   : {data}")
    print(f"  Durasi  : {elapsed:.3f} detik\n")

    print("=" * 55)
    print("  Selesai. Coba lagi setelah 5 menit untuk melihat")
    print("  cache MISS karena TTL sudah habis.")
    print("=" * 55)