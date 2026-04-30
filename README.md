# MyPaste<a name="top"></a>
## 1. Thông tin sinh viên
- Họ và tên: Vòng Sau Hậu
- MSSV: 24120307
- Lớp: 24CTT3

---


## 2. Công nghệ sử dụng
- **Frontend:** Streamlit
- **Backend:** FastAPI
- **Database/Auth:** Firebase Firestore + Firebase Auth
- **Config:** `.streamlit/secrets.toml` (dùng chung frontend/backend)

---

## 3. Giới thiệu dự án
Đây là dự án web app dạng pastebin đơn giản:
- Đăng nhập Email/Password hoặc Google OAuth
- Tạo, sửa, xoá paste
- Public paste listing + search theo ID
- Trang health để theo dõi tình trạng hệ thống

> [!TIP]
> Dự án phù hợp để:
> - Chia sẻ nhanh snippet code/text
> - Lưu và quản lý paste cá nhân

### Video demo:
<table align="center">
  <tr>
    <td>
      <video src="..." controls width="400"></video>
    </td>
  </tr>
</table>

---

## 4. Cấu trúc thư mục / các file chính

### 4.1 Frontend
```
frontend/
├── app.py # Giao diện Streamlit: navigation, login, create/edit/view paste, health page.
└── api_client.py # Gọi backend API và xử lý OAuth exchange
```
### 4.2 Backend
```
backend/app/
├── core/
│   ├── firebase_config.py # Khởi tạo Firebase Admin/Pyrebase
├── dependencies/
│   ├── auth.py # xác thực Firebase ID token
├── routers/
│   ├── auth.py # API auth: /sync-user, /sync-user-google, /me
│   ├── pastes.py # API Paste: /p/{paste_id}, /paste, /my-pastes, ...
├── schemas/
│   ├── auth.py 
│   ├── pastes.py
├── services/
│   ├── firestore_service.py # Tương tác Firestore, xử lí dữ liệu, thống kê hệ thống.
└── main.py # Khởi tạo FastAPI app
```

## 5. Cài đặt

```bash
git clone https://github.com/HauBaka/MyPaste.git
cd MyPaste
python -m venv .venv
```

Windows:
```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

Tạo file cấu hình dùng chung:

`./.streamlit/secrets.toml`

```toml
[app]
frontend_url = "http://localhost:8501"
google_client_id = "YOUR_GOOGLE_CLIENT_ID"
google_client_secret = "YOUR_GOOGLE_CLIENT_SECRET"
google_redirect_uri = "http://localhost:8501"
google_scopes = "openid email profile"
cors_origins = "http://localhost:8501"

[firebase_client]
apiKey = "YOUR_FIREBASE_WEB_API_KEY"
authDomain = "YOUR_PROJECT.firebaseapp.com"
projectId = "YOUR_PROJECT_ID"
storageBucket = "YOUR_PROJECT.appspot.com"
messagingSenderId = "YOUR_SENDER_ID"
appId = "YOUR_APP_ID"

[firebase_admin]
type = "service_account"
project_id = "YOUR_PROJECT_ID"
private_key_id = "YOUR_PRIVATE_KEY_ID"
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "firebase-adminsdk-xxx@YOUR_PROJECT_ID.iam.gserviceaccount.com"
client_id = "YOUR_CLIENT_ID"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "YOUR_CLIENT_X509_CERT_URL"
universe_domain = "googleapis.com"
```

---

## 6. Cách chạy

### 6.1. Backend
```bash
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend URL: `http://127.0.0.1:8000`

### 6.2. Frontend
```bash
streamlit run frontend/app.py
```

Frontend URL: `http://localhost:8501`

---

## 7. Mô tả API
### 7.1 Endpoints
| Endpoints            | Method   | Body                          | Output |
| :------------------- | :------: | :---------------------------: | :----- |
| `/health`            | `GET`    | `NONE`                        | Tình trạng hệ thống |
| `/sync-user`         | `POST`   | `{"id_token": string}`        | Đồng bộ user Firebase |
| `/sync-user-google`  | `POST`   | `{"email": string, "google_id": string}` | Đồng bộ user Google |
| `/me`                | `GET`    | `NONE`                        | User hiện tại |
| `/paste`             | `POST`   | `PasteCreateRequest`          | Tạo paste |
| `/paste/{paste_id}`  | `GET`    | `NONE`                        | Lấy chi tiết paste |
| `/paste/{paste_id}`  | `PUT`    | `PasteUpdateRequest`          | Cập nhật paste |
| `/paste/{paste_id}`  | `DELETE` | `NONE`                        | Xoá paste |
| `/my-pastes`         | `GET`    | `NONE`                        | Danh sách paste của user |
| `/pastes`            | `GET`    | `skip, limit, search`         | Danh sách public paste |
| `/p/{paste_id}`      | `GET`    | `NONE`                        | Redirect sang frontend |

> [!IMPORTANT]
> `content` của paste tối đa **2048 ký tự**.

---
[:arrow_up:](#top)

