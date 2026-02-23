import os
from typing import Annotated

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from web.auth import auth_middleware, is_authenticated, set_auth_cookie, verify_password
from web.database import init_db
from web.failure_reason import categorize_checkin_result
from web.routes.accounts import router as accounts_router
from web.routes.checkin import router as checkin_router
from web.routes.logs import router as logs_router
from web.routes.providers import router as providers_router

app = FastAPI(title='AnyRouter Check-in', docs_url=None, redoc_url=None)

BASE_DIR = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, 'templates'))
app.mount('/static', StaticFiles(directory=os.path.join(BASE_DIR, 'static')), name='static')

app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)

app.include_router(accounts_router)
app.include_router(providers_router)
app.include_router(checkin_router)
app.include_router(logs_router)


@app.on_event('startup')
async def startup():
	await init_db()
	from web.scheduler import start_scheduler
	start_scheduler()


@app.get('/login', response_class=HTMLResponse)
async def login_page(request: Request):
	if is_authenticated(request):
		return RedirectResponse(url='/', status_code=302)
	return templates.TemplateResponse('login.html', {'request': request, 'error': None})


@app.post('/login', response_class=HTMLResponse)
async def login_submit(request: Request, password: Annotated[str, Form(...)]):
	if verify_password(password):
		response = RedirectResponse(url='/', status_code=302)
		return set_auth_cookie(response)
	return templates.TemplateResponse('login.html', {'request': request, 'error': '密码错误'})


@app.get('/logout')
async def logout():
	response = RedirectResponse(url='/login', status_code=302)
	response.delete_cookie('auth_token')
	return response


@app.get('/', response_class=HTMLResponse)
async def dashboard(request: Request):
	from web.database import get_all_accounts, get_checkin_logs, get_setting
	accounts = await get_all_accounts()
	recent_logs = await get_checkin_logs(limit=10)
	for log in recent_logs:
		log['error_category'] = categorize_checkin_result(log.get('status'), log.get('message'))

	cron_expr = await get_setting('cron_expression', '0 */6 * * *')

	from web.scheduler import get_next_run_time
	next_run = get_next_run_time()

	return templates.TemplateResponse('dashboard.html', {
		'request': request,
		'accounts': accounts,
		'recent_logs': recent_logs,
		'cron_expression': cron_expr,
		'next_run': next_run,
		'active_page': 'dashboard',
	})


@app.get('/api/settings/schedule')
async def get_schedule():
	from web.database import get_setting
	from web.scheduler import get_next_run_time
	cron_expr = await get_setting('cron_expression', '0 */6 * * *')
	return {'success': True, 'cron_expression': cron_expr, 'next_run': get_next_run_time()}


@app.post('/api/settings/schedule')
async def update_schedule(request: Request):
	from web.scheduler import update_schedule as do_update
	data = await request.json()
	cron_expr = data.get('cron_expression', '').strip()
	if not cron_expr:
		return {'success': False, 'message': 'Cron 表达式不能为空'}
	parts = cron_expr.split()
	if len(parts) != 5:
		return {'success': False, 'message': 'Cron 表达式格式错误，需要5个字段'}
	await do_update(cron_expr)
	from web.scheduler import get_next_run_time
	return {'success': True, 'next_run': get_next_run_time()}
