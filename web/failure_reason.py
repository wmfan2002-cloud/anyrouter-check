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

CATEGORY_DISPLAY_MAP = {
	'auth_failed': {
		'label': '认证失败',
		'hint': '请检查 Cookie、API User 或登录凭据后重试',
		'actionable': True,
	},
	'waf_blocked': {
		'label': 'WAF 拦截',
		'hint': '请确认 WAF Cookie 是否完整，必要时改用浏览器登录',
		'actionable': True,
	},
	'network_error': {
		'label': '网络错误',
		'hint': '请检查域名可达性与网络连通性后重试',
		'actionable': True,
	},
	'config_error': {
		'label': '配置错误',
		'hint': '请检查 Provider 域名与路径配置是否正确',
		'actionable': True,
	},
	'upstream_error': {
		'label': '上游异常',
		'hint': '上游服务异常，建议稍后重试',
		'actionable': True,
	},
	'already_checked_in': {
		'label': '今日已签到',
		'hint': '今日签到已完成，无需执行修复动作',
		'actionable': False,
	},
	'unknown_error': {
		'label': '未知错误',
		'hint': '请查看原始错误信息并结合日志排查',
		'actionable': True,
	},
	'success': {
		'label': '成功',
		'hint': '执行成功',
		'actionable': False,
	},
}


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


def summarize_reason(status: str | None, message: str | None) -> dict:
	"""Return normalized category with localized display metadata."""
	category = categorize_checkin_result(status, message)
	meta = CATEGORY_DISPLAY_MAP.get(category, CATEGORY_DISPLAY_MAP['unknown_error'])
	return {
		'error_category': category,
		'error_category_label': meta['label'],
		'error_category_hint': meta['hint'],
		'error_category_actionable': meta['actionable'],
	}
