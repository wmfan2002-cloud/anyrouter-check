import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from web.database import (
	get_all_providers, get_provider, create_provider,
	update_provider, delete_provider,
)

router = APIRouter()


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
		bypass_method=data.get('bypass_method') or None,
		waf_cookie_names=data.get('waf_cookie_names', []),
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
			updates[field] = data[field] if data[field] else None
	if 'waf_cookie_names' in data:
		updates['waf_cookie_names'] = data['waf_cookie_names']

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
