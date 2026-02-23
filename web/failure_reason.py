"""Failure reason categorization for check-in logs."""

ALREADY_CHECKED_IN_KEYWORDS = (
	'already checked in',
	'already_check_in',
	'already_checked_in',
	'已经签到',
	'已签到',
	'重复签到',
)

AUTH_FAILED_KEYWORDS = (
	'auth failed',
	'authentication',
	'unauthorized',
	'invalid api user',
	'invalid token',
	'invalid credentials',
	'cookie expired',
	'凭据',
	'认证失败',
	'cookie 过期',
	'api user',
)

WAF_BLOCKED_KEYWORDS = (
	'waf',
	'cloudflare',
	'cf_chl',
	'missing waf cookies',
	'challenge',
	'反爬',
	'风控',
)

NETWORK_ERROR_KEYWORDS = (
	'timeout',
	'timed out',
	'connection refused',
	'connection reset',
	'network is unreachable',
	'temporary failure in name resolution',
	'failed to establish a new connection',
	'无法连接',
	'连接超时',
	'网络错误',
	'dns',
)

CONFIG_ERROR_KEYWORDS = (
	'provider not found',
	'invalid url',
	'域名格式',
	'配置错误',
	'json',
)

UPSTREAM_ERROR_KEYWORDS = (
	'http 5',
	'upstream',
	'bad gateway',
	'service unavailable',
	'internal server error',
)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
	return any(keyword in text for keyword in keywords)


def categorize_checkin_result(status: str | None, message: str | None) -> str:
	"""Categorize check-in result into normalized reason labels."""
	status_value = (status or '').strip().lower()
	text = (message or '').strip().lower()

	if status_value == 'success':
		return 'success'
	if status_value == 'already_checked_in' or _contains_any(text, ALREADY_CHECKED_IN_KEYWORDS):
		return 'already_checked_in'
	if _contains_any(text, AUTH_FAILED_KEYWORDS):
		return 'auth_failed'
	if _contains_any(text, WAF_BLOCKED_KEYWORDS):
		return 'waf_blocked'
	if _contains_any(text, NETWORK_ERROR_KEYWORDS):
		return 'network_error'
	if _contains_any(text, CONFIG_ERROR_KEYWORDS):
		return 'config_error'
	if _contains_any(text, UPSTREAM_ERROR_KEYWORDS):
		return 'upstream_error'
	return 'unknown_error'
