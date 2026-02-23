import re
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from web.database import (
	create_provider,
	delete_provider,
	get_all_providers,
	get_provider,
	update_provider,
)

router = APIRouter()
_COOKIE_NAME_PATTERN = re.compile(r'^[A-Za-z0-9_-]+$')


def _is_valid_domain(domain: str) -> bool:
	if not domain:
		return False

	parsed = urlparse(domain.strip())
	return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def _normalize_waf_cookie_names(raw) -> list[str]:
	if raw is None:
		return []

	if isinstance(raw, str):
		raw = [item.strip() for item in raw.split(',') if item.strip()]
	elif isinstance(raw, list):
		raw = [item.strip() for item in raw if isinstance(item, str) and item.strip()]
	else:
		raise ValueError('WAF Cookie 名称格式错误，请使用逗号分隔字符串或数组')

	invalid = [item for item in raw if not _COOKIE_NAME_PATTERN.fullmatch(item)]
	if invalid:
		raise ValueError('WAF Cookie 名称只能包含字母、数字、下划线或短横线')
	return raw


@router.get('/providers')
async def providers_page(request: Request):
	from web.app import templates
	providers = await get_all_providers()
	return templates.TemplateResponse('providers.html', {
		'request': request,
		'providers': providers,
		'active_page': 'providers',
	})


@router.post('/api/providers')
async def api_create_provider(request: Request):
	data = await request.json()
	name = data.get('name', '').strip()
	domain = data.get('domain', '').strip()

	if not name or not domain:
		return JSONResponse({'success': False, 'message': '请填写名称和域名'})
	if not _is_valid_domain(domain):
		return JSONResponse({'success': False, 'message': '域名格式不正确，请使用 http(s):// 开头的完整地址'})

	try:
		waf_cookie_names = _normalize_waf_cookie_names(data.get('waf_cookie_names', []))
	except ValueError as e:
		return JSONResponse({'success': False, 'message': str(e)})

	existing = await get_provider(name)
	if existing:
		return JSONResponse({'success': False, 'message': f'Provider "{name}" 已存在'})

	await create_provider(
		name=name,
		domain=domain,
		login_path=data.get('login_path', '/login'),
		sign_in_path=data.get('sign_in_path', '/api/user/sign_in'),
		user_info_path=data.get('user_info_path', '/api/user/self'),
		api_user_key=data.get('api_user_key', 'new-api-user'),
		bypass_method=(data.get('bypass_method') or '').strip() or None,
		waf_cookie_names=waf_cookie_names,
	)
	return JSONResponse({'success': True})


@router.put('/api/providers/{name}')
async def api_update_provider(name: str, request: Request):
	data = await request.json()
	existing = await get_provider(name)
	if not existing:
		return JSONResponse({'success': False, 'message': 'Provider 不存在'})
	if existing['is_builtin']:
		return JSONResponse({'success': False, 'message': '内置 Provider 不可编辑'})

	updates = {}
	for field in ['domain', 'login_path', 'sign_in_path', 'user_info_path', 'api_user_key', 'bypass_method']:
		if field in data:
			value = data[field]
			if isinstance(value, str):
				value = value.strip()
			updates[field] = value if value else None

	if 'domain' in updates:
		if not updates['domain']:
			return JSONResponse({'success': False, 'message': '域名不能为空'})
		if not _is_valid_domain(updates['domain']):
			return JSONResponse({'success': False, 'message': '域名格式不正确，请使用 http(s):// 开头的完整地址'})

	if 'waf_cookie_names' in data:
		try:
			updates['waf_cookie_names'] = _normalize_waf_cookie_names(data['waf_cookie_names'])
		except ValueError as e:
			return JSONResponse({'success': False, 'message': str(e)})

	if updates:
		await update_provider(name, **updates)
	return JSONResponse({'success': True})


@router.delete('/api/providers/{name}')
async def api_delete_provider(name: str):
	existing = await get_provider(name)
	if not existing:
		return JSONResponse({'success': False, 'message': 'Provider 不存在'})
	if existing['is_builtin']:
		return JSONResponse({'success': False, 'message': '内置 Provider 不可删除'})
	await delete_provider(name)
	return JSONResponse({'success': True})
