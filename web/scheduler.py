import asyncio
import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from utils.config import ProviderConfig, AccountConfig
from web.database import (
	get_enabled_accounts, get_all_providers, get_account,
	update_account, add_checkin_log, get_setting, set_setting,
)

logger = logging.getLogger('checkin')
_tz = ZoneInfo(os.environ.get('TZ', 'Asia/Shanghai'))
scheduler = AsyncIOScheduler(timezone=_tz)
_checkin_lock = asyncio.Lock()


def start_scheduler():
	async def _setup():
		cron_expr = await get_setting('cron_expression', '0 */6 * * *')
		_schedule_job(cron_expr)

	loop = asyncio.get_event_loop()
	loop.create_task(_setup())
	if not scheduler.running:
		scheduler.start()


async def update_schedule(cron_expr: str):
	"""Update the cron expression and reschedule the job."""
	await set_setting('cron_expression', cron_expr)
	_schedule_job(cron_expr)


def _schedule_job(cron_expr: str):
	# Remove existing job if any
	if scheduler.get_job('checkin_job'):
		scheduler.remove_job('checkin_job')

	parts = cron_expr.strip().split()
	if len(parts) == 5:
		trigger = CronTrigger(
			minute=parts[0], hour=parts[1], day=parts[2],
			month=parts[3], day_of_week=parts[4]
		)
		scheduler.add_job(
			_scheduled_checkin, trigger, id='checkin_job',
			name='Scheduled Check-in', replace_existing=True,
			misfire_grace_time=300,
		)
		logger.info(f'Scheduled checkin job with cron: {cron_expr}')


async def _scheduled_checkin():
	logger.info('Scheduled check-in triggered')
	await run_checkin_task(triggered_by='schedule')


def get_next_run_time():
	job = scheduler.get_job('checkin_job')
	if job and job.next_run_time:
		return job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')
	return None


async def _build_provider_config(provider_name: str) -> ProviderConfig | None:
	providers = await get_all_providers()
	for p in providers:
		if p['name'] == provider_name:
			waf_names = None
			if p['waf_cookie_names']:
				try:
					waf_names = json.loads(p['waf_cookie_names'])
				except (json.JSONDecodeError, TypeError):
					waf_names = None
			return ProviderConfig(
				name=p['name'],
				domain=p['domain'],
				login_path=p['login_path'] or '/login',
				sign_in_path=p['sign_in_path'],
				user_info_path=p['user_info_path'] or '/api/user/self',
				api_user_key=p['api_user_key'] or 'new-api-user',
				bypass_method=p['bypass_method'],
				waf_cookie_names=waf_names,
			)
	return None


def _db_account_to_config(acc: dict, index: int) -> AccountConfig:
	cookies = acc['cookies']
	try:
		cookies = json.loads(cookies)
	except (json.JSONDecodeError, TypeError):
		pass
	return AccountConfig(
		cookies=cookies,
		api_user=acc['api_user'],
		provider=acc['provider'],
		name=acc['name'],
	)


async def run_checkin_single(account_row: dict, triggered_by='manual') -> dict:
	auth_method = account_row.get('auth_method', 'cookie')

	if auth_method == 'browser_login':
		return await _run_browser_login_checkin(account_row, triggered_by)
	else:
		return await _run_cookie_checkin(account_row, triggered_by)


async def _run_browser_login_checkin(account_row: dict, triggered_by: str) -> dict:
	"""使用浏览器登录方式签到"""
	from web.browser_checkin import browser_login_checkin

	provider_config = await _build_provider_config(account_row['provider'])
	if not provider_config:
		msg = f'Provider "{account_row["provider"]}" not found'
		await add_checkin_log(
			account_id=account_row['id'],
			account_name=account_row['name'],
			provider=account_row['provider'],
			status='failed',
			message=msg,
			triggered_by=triggered_by,
		)
		return {'success': False, 'message': msg}

	try:
		result = await browser_login_checkin(
			account_name=account_row['name'],
			domain=provider_config.domain,
			login_path=provider_config.login_path,
			username=account_row.get('username', ''),
			password=account_row.get('password', ''),
			user_info_path=provider_config.user_info_path,
		)

		status = 'success' if result['success'] else 'failed'
		update_data = {
			'last_checkin': datetime.now().isoformat(),
			'last_status': status,
		}
		if result.get('quota') is not None:
			update_data['last_balance'] = result['quota']
		if result.get('used_quota') is not None:
			update_data['last_used'] = result['used_quota']
		await update_account(account_row['id'], **update_data)

		await add_checkin_log(
			account_id=account_row['id'],
			account_name=account_row['name'],
			provider=account_row['provider'],
			status=status,
			balance=result.get('quota'),
			used_quota=result.get('used_quota'),
			message=result.get('message', ''),
			triggered_by=triggered_by,
		)

		return {'success': result['success'], 'message': result.get('message', '')}

	except Exception as e:
		msg = str(e)[:200]
		await add_checkin_log(
			account_id=account_row['id'],
			account_name=account_row['name'],
			provider=account_row['provider'],
			status='failed',
			message=msg,
			triggered_by=triggered_by,
		)
		await update_account(account_row['id'],
							 last_checkin=datetime.now().isoformat(),
							 last_status='failed')
		return {'success': False, 'message': msg}


async def _run_cookie_checkin(account_row: dict, triggered_by: str) -> dict:
	"""使用 Cookie 方式签到（原有逻辑）"""
	from checkin import check_in_account
	from utils.config import AppConfig

	provider_config = await _build_provider_config(account_row['provider'])
	if not provider_config:
		msg = f'Provider "{account_row["provider"]}" not found'
		await add_checkin_log(
			account_id=account_row['id'],
			account_name=account_row['name'],
			provider=account_row['provider'],
			status='failed',
			message=msg,
			triggered_by=triggered_by,
		)
		return {'success': False, 'message': msg}

	# Build a temporary AppConfig with the resolved provider
	app_config = AppConfig(providers={account_row['provider']: provider_config})
	account_config = _db_account_to_config(account_row, 0)

	try:
		success, user_info = await check_in_account(account_config, 0, app_config)

		balance = user_info.get('quota') if user_info and user_info.get('success') else None
		used = user_info.get('used_quota') if user_info and user_info.get('success') else None
		status = 'success' if success else 'failed'
		msg = ''
		if user_info and user_info.get('success'):
			msg = f'Balance: ${balance}, Used: ${used}'
		elif user_info:
			msg = user_info.get('error', '')
		if not success and not msg:
			msg = 'Check-in failed (WAF bypass or request error)'

		# Update account status
		update_data = {
			'last_checkin': datetime.now().isoformat(),
			'last_status': status,
		}
		if balance is not None:
			update_data['last_balance'] = balance
		if used is not None:
			update_data['last_used'] = used
		await update_account(account_row['id'], **update_data)

		# Add log
		await add_checkin_log(
			account_id=account_row['id'],
			account_name=account_row['name'],
			provider=account_row['provider'],
			status=status,
			balance=balance,
			used_quota=used,
			message=msg,
			triggered_by=triggered_by,
		)

		return {'success': success, 'message': msg}

	except Exception as e:
		msg = str(e)[:200]
		await add_checkin_log(
			account_id=account_row['id'],
			account_name=account_row['name'],
			provider=account_row['provider'],
			status='failed',
			message=msg,
			triggered_by=triggered_by,
		)
		await update_account(account_row['id'],
							 last_checkin=datetime.now().isoformat(),
							 last_status='failed')
		return {'success': False, 'message': msg}


async def run_checkin_task(triggered_by='schedule') -> dict:
	async with _checkin_lock:
		accounts = await get_enabled_accounts()
		if not accounts:
			logger.info('No enabled accounts found')
			return {'success_count': 0, 'total_count': 0}

		success_count = 0
		total_count = len(accounts)

		for acc in accounts:
			try:
				result = await run_checkin_single(acc, triggered_by=triggered_by)
				if result['success']:
					success_count += 1
			except Exception as e:
				logger.error(f'Error checking in account {acc["name"]}: {e}')

		# Send notification if there are failures
		if success_count < total_count:
			try:
				from utils.notify import notify
				content = f'签到完成: {success_count}/{total_count} 成功'
				notify.push_message('AnyRouter Check-in', content, msg_type='text')
			except Exception as e:
				logger.error(f'Notification failed: {e}')

		logger.info(f'Check-in completed: {success_count}/{total_count} success')
		return {'success_count': success_count, 'total_count': total_count}
