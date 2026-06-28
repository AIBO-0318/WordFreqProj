"""
_env.py — 아주 작은 .env 로더 (python-dotenv 같은 외부 패키지 불필요)

crawler/.env 파일에 적힌 KEY=VALUE 들을 os.environ 으로 올린다.
.env 는 .gitignore 에 등록되어 깃허브에 올라가지 않으므로,
이메일·비밀번호·API 키 같은 비밀값은 여기에만 적어 둔다.

사용:
    from _env import load_env
    load_env()
    EMAIL = os.environ.get("WATCHA_EMAIL", "")
"""
import os


def load_env(path: str | None = None) -> None:
    """같은 폴더의 .env 파일을 읽어 환경변수로 설정한다(이미 설정된 값은 보존)."""
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
