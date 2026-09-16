import random

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="number-game-secret-key")

PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>숫자 맞추기 게임</title>
    <style>
        body {{
            font-family: sans-serif;
            max-width: 480px;
            margin: 60px auto;
            text-align: center;
        }}
        input[type=number] {{
            font-size: 1.2em;
            padding: 6px;
            width: 100px;
        }}
        button {{
            font-size: 1.2em;
            padding: 6px 16px;
        }}
        .message {{
            margin-top: 20px;
            font-size: 1.3em;
            font-weight: bold;
        }}
        .win {{
            color: green;
        }}
    </style>
</head>
<body>
    <h1>1~100 숫자 맞추기 게임</h1>
    <p>컴퓨터가 정한 1부터 100 사이의 숫자를 맞춰보세요!</p>
    <p>시도 횟수: {attempts}</p>
    <div class="message {message_class}">{message}</div>
    {form}
</body>
</html>
"""

GUESS_FORM = """
<form method="post" action="/guess">
    <input type="number" name="guess" min="1" max="100" required autofocus>
    <button type="submit">추측하기</button>
</form>
"""

RESTART_FORM = """
<form method="post" action="/restart">
    <button type="submit">다시 시작하기</button>
</form>
"""


def render_page(attempts: int, message: str, message_class: str, won: bool) -> str:
    form = RESTART_FORM if won else GUESS_FORM
    return PAGE_TEMPLATE.format(
        attempts=attempts,
        message=message,
        message_class=message_class,
        form=form,
    )


def start_new_game(request: Request) -> None:
    request.session["answer"] = random.randint(1, 100)
    request.session["attempts"] = 0
    request.session["won"] = False


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if "answer" not in request.session:
        start_new_game(request)

    attempts = request.session["attempts"]
    won = request.session["won"]

    if won:
        message = f"정답입니다! {attempts}번 만에 맞추셨습니다. 축하합니다!"
        message_class = "win"
    elif attempts == 0:
        message = "숫자를 입력해보세요."
        message_class = ""
    else:
        message = request.session.get("last_hint", "")
        message_class = ""

    return render_page(attempts, message, message_class, won)


@app.post("/guess", response_class=HTMLResponse)
def guess(request: Request, guess: int = Form(...)):
    if "answer" not in request.session:
        start_new_game(request)

    answer = request.session["answer"]
    request.session["attempts"] += 1
    attempts = request.session["attempts"]

    if guess < answer:
        message = "더 높은 숫자입니다."
        message_class = ""
        request.session["last_hint"] = message
    elif guess > answer:
        message = "더 낮은 숫자입니다."
        message_class = ""
        request.session["last_hint"] = message
    else:
        request.session["won"] = True
        message = f"정답입니다! {attempts}번 만에 맞추셨습니다. 축하합니다!"
        message_class = "win"

    return render_page(attempts, message, message_class, request.session["won"])


@app.post("/restart")
def restart(request: Request):
    start_new_game(request)
    return RedirectResponse(url="/", status_code=303)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
