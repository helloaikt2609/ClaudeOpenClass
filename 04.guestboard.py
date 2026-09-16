import hashlib
import html
import json
import os
import threading
import uuid
from datetime import datetime

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

app = FastAPI()

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "guestboard.json")
_lock = threading.Lock()

MAX_NAME_LEN = 30
MAX_CONTENT_LEN = 500


def load_posts() -> list:
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_posts(posts: list) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


PAGE_HEAD = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>방명록</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', 'Malgun Gothic', sans-serif;
            background: #f0f7f1;
            margin: 0;
            padding: 0 16px 60px;
            color: #1b3a24;
        }
        .banner {
            max-width: 680px;
            margin: 0 auto;
            padding: 40px 20px 30px;
            text-align: center;
        }
        .banner h1 {
            font-size: 2.2em;
            margin: 0 0 6px;
            color: #1e6b3a;
        }
        .banner p {
            margin: 0;
            color: #4c7a5a;
        }
        .container {
            max-width: 680px;
            margin: 0 auto;
        }
        .write-box {
            background: #ffffff;
            border: 1px solid #d3ead9;
            border-radius: 14px;
            padding: 24px;
            box-shadow: 0 4px 14px rgba(30, 107, 58, 0.08);
            margin-bottom: 30px;
        }
        .write-box h2 {
            margin-top: 0;
            font-size: 1.15em;
            color: #1e6b3a;
        }
        .row {
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
        }
        .row input {
            flex: 1;
        }
        input, textarea {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #cfe3d5;
            border-radius: 8px;
            font-size: 0.95em;
            font-family: inherit;
        }
        input:focus, textarea:focus {
            outline: none;
            border-color: #2e9e57;
        }
        textarea {
            resize: vertical;
            min-height: 90px;
            margin-bottom: 12px;
        }
        button {
            background: #2e9e57;
            color: white;
            border: none;
            border-radius: 8px;
            padding: 10px 20px;
            font-size: 0.95em;
            cursor: pointer;
            transition: background 0.15s;
        }
        button:hover {
            background: #227e44;
        }
        .submit-row {
            text-align: right;
        }
        .count {
            color: #4c7a5a;
            font-size: 0.9em;
            margin-bottom: 12px;
        }
        .post {
            background: #ffffff;
            border: 1px solid #d3ead9;
            border-radius: 12px;
            padding: 18px 20px;
            margin-bottom: 14px;
            box-shadow: 0 2px 8px rgba(30, 107, 58, 0.06);
        }
        .post-header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 8px;
        }
        .post-name {
            font-weight: 600;
            color: #1e6b3a;
            font-size: 1.05em;
        }
        .post-date {
            color: #8aa693;
            font-size: 0.8em;
        }
        .post-content {
            white-space: pre-wrap;
            line-height: 1.5;
            margin-bottom: 12px;
            word-break: break-word;
        }
        .delete-form {
            display: flex;
            gap: 6px;
            justify-content: flex-end;
        }
        .delete-form input {
            width: 120px;
            padding: 6px 10px;
            font-size: 0.85em;
        }
        .delete-form button {
            background: #c94b4b;
            padding: 6px 14px;
            font-size: 0.85em;
        }
        .delete-form button:hover {
            background: #a83a3a;
        }
        .empty {
            text-align: center;
            color: #6d8f79;
            padding: 40px 0;
        }
    </style>
</head>
<body>
    <div class="banner">
        <h1>🌿 방명록</h1>
        <p>따뜻한 한마디를 남겨주세요.</p>
    </div>
    <div class="container">
        <div class="write-box">
            <h2>글쓰기</h2>
            <form method="post" action="/write">
                <div class="row">
                    <input type="text" name="name" placeholder="이름" maxlength="30" required>
                    <input type="password" name="password" placeholder="비밀번호 (삭제 시 필요)" maxlength="30" required>
                </div>
                <textarea name="content" placeholder="방명록 내용을 남겨주세요." maxlength="500" required></textarea>
                <div class="submit-row">
                    <button type="submit">등록</button>
                </div>
            </form>
        </div>
"""

PAGE_FOOT = """
    </div>
</body>
</html>
"""


def render_post(post: dict) -> str:
    name = html.escape(post["name"])
    content = html.escape(post["content"])
    created_at = html.escape(post["created_at"])
    post_id = html.escape(post["id"])
    return f"""
        <div class="post">
            <div class="post-header">
                <span class="post-name">{name}</span>
                <span class="post-date">{created_at}</span>
            </div>
            <div class="post-content">{content}</div>
            <form class="delete-form" method="post" action="/delete/{post_id}">
                <input type="password" name="password" placeholder="비밀번호" required>
                <button type="submit">삭제</button>
            </form>
        </div>
"""


def render_page() -> str:
    posts = load_posts()
    posts_sorted = sorted(posts, key=lambda p: p["created_at"], reverse=True)

    if posts_sorted:
        count_html = f'<div class="count">총 {len(posts_sorted)}개의 글</div>'
        posts_html = "".join(render_post(p) for p in posts_sorted)
    else:
        count_html = ""
        posts_html = '<div class="empty">아직 작성된 방명록이 없습니다. 첫 글을 남겨보세요!</div>'

    return PAGE_HEAD + count_html + posts_html + PAGE_FOOT


@app.get("/", response_class=HTMLResponse)
def index():
    return render_page()


@app.post("/write")
def write(
    request: Request,
    name: str = Form(...),
    password: str = Form(...),
    content: str = Form(...),
):
    name = name.strip()[:MAX_NAME_LEN]
    content = content.strip()[:MAX_CONTENT_LEN]

    if not name or not password or not content:
        return RedirectResponse(url="/", status_code=303)

    with _lock:
        posts = load_posts()
        posts.append({
            "id": uuid.uuid4().hex,
            "name": name,
            "content": content,
            "password_hash": hash_password(password),
            "ip": get_client_ip(request),
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        save_posts(posts)

    return RedirectResponse(url="/", status_code=303)


@app.post("/delete/{post_id}")
def delete(post_id: str, password: str = Form(...)):
    with _lock:
        posts = load_posts()
        target = next((p for p in posts if p["id"] == post_id), None)

        if target and target["password_hash"] == hash_password(password):
            posts = [p for p in posts if p["id"] != post_id]
            save_posts(posts)

    return RedirectResponse(url="/", status_code=303)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
