import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from web.database import (
	get_all_accounts, get_account, create_account,
	update_account, delete_account, toggle_account,
	get_all_providers,
)

router = APIRouter()


@router.get('/accounts')
async def accounts_page(request: Request):
	from web.app import templates
	accounts = await get_all_accounts()
	providers = await get_all_providers()
	return templates.TemplateResponse('accounts.html', {
		'request': request,
		'accounts': accounts,
		'providers': providers,
		'active_page': 'accounts',
	})


@router.post('/api/accounts')
async def api_create_account(request: Request):
	data = await request.json()
	name = data.get('name', '').strip()
	provider = data.get('provider', 'anyrouter').strip()
	auth_method = data.get('auth_method', 'cookie').strip()

	if not name:
		return JSONResponse({'success': False, 'message': '请填写账号名称'})

	if auth_method == 'browser_login':
		username = data.get('username', '').strip()
		password = data.get('password', '').strip()
		if not username or not password:
			return JSONResponse({'success': False, 'message': '请填写用户名和密码'})
		account_id = await create_account(
			name=name, provider=provider, auth_method='browser_login',
			username=username, password=password,
		)
	else:
		cookies_raw = data.get('cookies', '').strip()
		api_user = data.get('api_user', '').strip()
		if not cookies_raw or not api_user:
			return JSONResponse({'success': False, 'message': '请填写 Cookies 和 API User ID'})
		# Auto-wrap plain session value into JSON format
		if not cookies_raw.startswith('{'):
			cookies_raw = json.dumps({'session': cookies_raw})
		else:
			try:
				json.loads(cookies_raw)
			except json.JSONDecodeError:
				return JSONResponse({'success': False, 'message': 'Cookies JSON 格式不正确'})
		account_id = await create_account(
			name=name, provider=provider, auth_method='cookie',
			cookies=cookies_raw, api_user=api_user,
		)

	return JSONResponse({'success': True, 'id': account_id})


@router.put('/api/accounts/{account_id}')
async def api_update_account(account_id: int, request: Request):
	data = await request.json()
	acc = await get_account(account_id)
	if not acc:
		return JSONResponse({'success': False, 'message': '账号不存在'})

	updates = {}
	if 'name' in data and data['name'].strip():
		updates['name'] = data['name'].strip()
	if 'provider' in data:
		updates['provider'] = data['provider'].strip()
	if 'auth_method' in data:
		updates['auth_method'] = data['auth_method'].strip()

	auth_method = data.get('auth_method', acc.get('auth_method', 'cookie'))
	if auth_method == 'browser_login':
		if 'username' in data:
			updates['username'] = data['username'].strip()
		if 'password' in data:
			updates['password'] = data['password'].strip()
	else:
		if 'cookies' in data and data['cookies'].strip():
			c = data['cookies'].strip()
			if not c.startswith('{'):
				c = json.dumps({'session': c})
			updates['cookies'] = c
		if 'api_user' in data and data['api_user'].strip():
			updates['api_user'] = data['api_user'].strip()

	if updates:
		await update_account(account_id, **updates)
	return JSONResponse({'success': True})


@router.delete('/api/accounts/{account_id}')
async def api_delete_account(account_id: int):
	acc = await get_account(account_id)
	if not acc:
		return JSONResponse({'success': False, 'message': '账号不存在'})
	await delete_account(account_id)
	return JSONResponse({'success': True})


@router.post('/api/accounts/{account_id}/toggle')
async def api_toggle_account(account_id: int):
	acc = await get_account(account_id)
	if not acc:
		return JSONResponse({'success': False, 'message': '账号不存在'})
	await toggle_account(account_id)
	return JSONResponse({'success': True})
