import hashlib
import hmac
import os
import time

from fastapi import Request, Response
from fastapi.responses import RedirectResponse

SECRET_KEY = os.getenv('SECRET_KEY', 'anyrouter-checkin-secret-key-change-me')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin')
TOKEN_MAX_AGE = 86400 * 7  # 7 days


def _sign_token(timestamp: str) -> str:
	msg = f'{timestamp}:{ADMIN_PASSWORD}'.encode()
	return hmac.new(SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:32]


def create_token() -> str:
	ts = str(int(time.time()))
	sig = _sign_token(ts)
	return f'{ts}:{sig}'


def verify_token(token: str) -> bool:
	if not token:
		return False
	try:
		parts = token.split(':')
		if len(parts) != 2:
			return False
		ts, sig = parts
		if int(time.time()) - int(ts) > TOKEN_MAX_AGE:
			return False
		return hmac.compare_digest(sig, _sign_token(ts))
	except (ValueError, IndexError):
		return False


def verify_password(password: str) -> bool:
	return password == ADMIN_PASSWORD


def is_authenticated(request: Request) -> bool:
	token = request.cookies.get('auth_token')
	return verify_token(token)


def set_auth_cookie(response: Response) -> Response:
	token = create_token()
	response.set_cookie(
		key='auth_token',
		value=token,
		max_age=TOKEN_MAX_AGE,
		httponly=True,
		samesite='lax',
	)
	return response


LOGIN_EXEMPT_PATHS = {'/login', '/static'}


async def auth_middleware(request: Request, call_next):
	path = request.url.path
	if any(path.startswith(p) for p in LOGIN_EXEMPT_PATHS):
		return await call_next(request)

	if not is_authenticated(request):
		return RedirectResponse(url='/login', status_code=302)

	return await call_next(request)
