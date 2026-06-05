import time
from weather_api import get_weather

# Panggilan pertama — cache MISS, lambat (~2 detik)
start = time.time()
result1 = get_weather("Jakarta")
time1 = time.time() - start
print(f"First call: {time1:.2f}s")

# Panggilan kedua — cache HIT, cepat (< 0.1 detik)
start = time.time()
result2 = get_weather("Jakarta")
time2 = time.time() - start
print(f"Second call (cached): {time2:.2f}s")

# Panggilan ketiga setelah 5 menit — lambat lagi
# Setelah TTL 300 detik habis, Redis otomatis menghapus key "weather:jakarta".
# Pemanggilan berikutnya akan cache MISS lagi → memanggil API ulang → ~2 detik.
# (Tidak perlu menunggu 5 menit untuk pengujian ini)