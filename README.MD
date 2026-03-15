# Multi-Container Setup dengan Docker Compose 

## Langkah-langkah Menjalankan Stack
```bash
# masuk ke folder porject
cd wordpress-docker

# Jalankan semua container
docker compose up -d

# Cek status container
docker ps

# Akses WordPress
# http://localhost:8000
```

## Dokumentasi (Screenshots)
### 1. Wordpress Installation Page
Pemilihan Bahasa: Memilih bahasa sistem WordPress.
![Tampilan installation page 1](screenshots/installation1.png)
Konfigurasi Akun: Membuat username admin dan password.
![Tampilan installation page 2](screenshots/installation2.png)

### 2. Wordpress Dashboard
Login ke Dashboard: Proses masuk ke halaman administrasi.
![Tampilan login dashboard](screenshots/login_dashboard.png)
Tampilan Dashboard: WordPress siap digunakan.
![Tampilan dashboard](screenshots/dashboard.png)

### 3. Docker Processes
Membuktikan 3 container (WordPress, MySQL, Redis) berstatus Up.
![Tampilan Docker ps](screenshots/docker_ps.png)

### 4. Redis CLI ping test
Uji respons Redis dengan hasil PONG.
![Reddis ping test](screenshots/redis_test.png)

## Jawaban Pertanyaan

### 1. Kenapa perlu volume untuk MySQL?
 
MySQL menyimpan data di dalam container yang bersifat sementara. Tanpa volume, seluruh data (posts, users, settings) akan **hilang permanen** setiap kali container dihentikan atau dihapus. Dengan volume, data disimpan di storage host sehingga tetap ada meskipun container restart atau diganti.
 
### 2. Apa fungsi `depends_on`?
 
`depends_on` mendefinisikan urutan startup container. Dengan konfigurasi:
```yaml
depends_on:
  - mysql
  - redis
```
Docker Compose memastikan container `mysql` dan `redis` **dijalankan lebih dulu** sebelum container `wordpress` dimulai. Ini penting karena WordPress butuh koneksi ke database saat proses inisialisasi.
 
### 3. Bagaimana cara WordPress container connect ke MySQL?
 
Di dalam Docker network (`wp_network`), setiap container bisa saling berkomunikasi menggunakan **nama service sebagai hostname**. Konfigurasi `WORDPRESS_DB_HOST: mysql:3306` berarti WordPress terhubung ke hostname `mysql` (nama service di docker-compose.yml) pada port 3306. Docker DNS internal secara otomatis me-resolve nama `mysql` ke IP container MySQL.
 
### 4. Apa keuntungan pakai Redis untuk WordPress?
 
- **Performa lebih cepat**: Query database yang sering dipanggil (misal: menu, widget, options) disimpan di RAM melalui Redis. Request berikutnya langsung diambil dari cache tanpa hit ke MySQL.
- **Mengurangi beban database**: Traffic tinggi tidak langsung membebani MySQL karena banyak request dilayani oleh cache.
- **Waktu respons lebih rendah**: Akses Redis (in-memory) jauh lebih cepat dibanding disk I/O MySQL.
- **Scalable**: Cocok untuk WordPress dengan traffic besar atau banyak plugin.

