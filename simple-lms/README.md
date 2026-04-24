# SIMPLE LMS API DOCUMENTATION

## 1. API ENDPOINTS & DOCUMENTATION
Menampilkan seluruh daftar fungsionalitas yang tersedia pada sistem LMS.
![api endpoint](screenshots/api_enpoints.png)

## 2. JWT AUTHENTICATION
Sistem keamanan menggunakan JSON Web Token untuk proteksi data.

### Token Generation
Proses login untuk mendapatkan access dan refresh token.
![login](screenshots/jwt1.png)

### Security Protection
Respon (401 Unauthorized) saat mencoba akses endpoint terproteksi tanpa token.
![akses tanpa token](screenshots/jwt2.png)

Akses berhasil setelah menyertakan token yang valid.
![akses menggunakan token](screenshots/jwt3.png)

## 3. RBAC (ROLE-BASED ACCESS CONTROL)
Pembatasan hak akses berdasarkan peran pengguna:
- **Admin**: Akses penuh melalui `@admin_required`.
- **Instructor**: Izin membuat dan mengelola kursus melalui `@instructor_required`.
- **Student**: Akses konten dan komentar melalui `@student_required`.

### Testing RBAC
Contoh penolakan akses (403 Forbidden) saat user biasa mencoba mengakses fitur instruktur.
![RBAC testing](screenshots/jwt4.png)

## 4. SCHEMA VALIDATION
Validasi integritas data menggunakan Pydantic untuk mencegah data cacat masuk ke database.

- **Tipe data tidak sesuai (422 Error)**:
![Validation Fail 1](screenshots/val_fail.png)

- **Field wajib tidak diisi**:
![Validation Fail 2](screenshots/val_fail2.png)

- **Input Valid (Success)**:
![Validation Success](screenshots/val_success.png)

## 5. POSTMAN COLLECTION & AUTOMATION
Koleksi request API yang terorganisir, mencakup seluruh endpoint yang telah diimplementasikan. Koleksi ini dilengkapi dengan pengaturan environment untuk fleksibilitas pengujian di berbagai server.

**Struktur folder:**
![postman collection](screenshots/postman_collection.png)
**Daftar request pada Postman:**
![postman collection](screenshots/postman_collection2.png)
![postman collection](screenshots/postman_collection3.png)
![postman collection](screenshots/postman_collection4.png)