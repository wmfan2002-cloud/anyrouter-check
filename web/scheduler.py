import asyncio
import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from utils.config import AccountConfig, ProviderConfig
from web.database import (
	add_checkin_log,
	cleanup_expired_waf_cookies,
	delete_waf_cookies,
	get_all_providers,
	get_cached_waf_cookies,
	get_enabled_accounts,
	get_setting,
	save_waf_cookies,
	set_setting,
	update_account,
)

logger = logging.getLogger('checkin')
_tz = ZoneInfo(os.environ.get('TZ', 'Asia/Shanghai'))
scheduler = AsyncIOScheduler(timezone=_tz)
_checkin_lock = asyncio.Lock()


def _is_already_checked_in_message(message: str | None) -> bool:
	if not message:
		return False

	text = str(message).strip().lower()
	keywords = [
		'already checked in',
		'already check in',
		'already signed in',
		'already_checked_in',
		'已经签到',
		'已签到',
		'重复签到',
	]
	return any(keyword in text for keyword in keywords)


def _normalize_status(success: bool, message: str | None) -> tuple[str, bool]:
	if _is_already_checked_in_message(message):
		return 'already_checked_in', True
	return ('success', True) if success else ('failed', False)


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
	# 清理过期的 WAF cookie 缓存
	try:
		deleted = await cleanup_expired_waf_cookies()
		if deleted:
			logger.info(f'Cleaned up {deleted} expired WAF cookie cache entries')
	except Exception as e:
		logger.warning(f'WAF cookie cleanup failed: {e}')
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
			domain = (p['domain'] or '').rstrip('/')
			waf_names = None
			if p['waf_cookie_names']:
				try:
					waf_names = json.loads(p['waf_cookie_names'])
				except (json.JSONDecodeError, TypeError):
					waf_names = None
			return ProviderConfig(
				name=p['name'],
				domain=domain,
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


def _resolve_domain(provider_config, account_row: dict) -> str | None:
	"""Resolve domain: use account domain if provider has no domain (template provider)."""
	if provider_config.domain:
		return provider_config.domain
	account_domain = (account_row.get('domain') or '').rstrip('/')
	if account_domain:
		provider_config.domain = account_domain
		return account_domain
	return None


def _waf_cache_key(provider_config, account_row: dict) -> str:
	"""Determine cache key for WAF cookies.

	Regular providers use provider name; template providers (empty domain)
	use provider_name:account_domain to avoid cross-account conflicts.
	"""
	account_domain = (account_row.get('domain') or '').rstrip('/')
	if provider_config.domain and not account_domain:
		return provider_config.name
	return f'{provider_config.name}:{account_domain or provider_config.domain}'


async def _get_waf_cookies_cached(
	account_name: str, provider_config, account_row: dict
) -> dict | None:
	"""Get WAF cookies with cache-first strategy.

	Returns: dict of cookies on success, None if browser fetch failed.
	Empty dict {} if WAF bypass is not needed.
	"""
	if not provider_config.needs_waf_cookies():
		return {}

	cache_key = _waf_cache_key(provider_config, account_row)

	# 尝试缓存
	try:
		cached = await get_cached_waf_cookies(cache_key)
		if cached:
			logger.info(f'{account_name}: Using cached WAF cookies (key={cache_key})')
			return cached
	except Exception as e:
		logger.warning(f'{account_name}: Failed to check WAF cookie cache: {e}')

	# 缓存未命中，启动浏览器
	logger.info(f'{account_name}: No cached WAF cookies, launching browser...')
	from checkin import get_waf_cookies_with_playwright

	login_url = f'{provider_config.domain}{provider_config.login_path}'
	waf_cookies = await get_waf_cookies_with_playwright(
		account_name, login_url, provider_config.waf_cookie_names
	)

	if waf_cookies:
		# 保存到缓存
		try:
			await save_waf_cookies(cache_key, waf_cookies)
			logger.info(f'{account_name}: WAF cookies cached for 24 hours (key={cache_key})')
		except Exception as e:
			logger.warning(f'{account_name}: Failed to cache WAF cookies: {e}')

	return waf_cookies


async def _invalidate_and_refresh_waf_cookies(
	account_name: str, provider_config, account_row: dict
) -> dict | None:
	"""Invalidate cached WAF cookies and get fresh ones via browser."""
	cache_key = _waf_cache_key(provider_config, account_row)

	# 清除缓存
	try:
		await delete_waf_cookies(cache_key)
		logger.info(f'{account_name}: Invalidated WAF cookie cache (key={cache_key})')
	except Exception as e:
		logger.warning(f'{account_name}: Failed to invalidate WAF cookie cache: {e}')

	# 启动浏览器获取新 cookies
	from checkin import get_waf_cookies_with_playwright

	login_url = f'{provider_config.domain}{provider_config.login_path}'
	waf_cookies = await get_waf_cookies_with_playwright(
		account_name, login_url, provider_config.waf_cookie_names
	)

	if waf_cookies:
		try:
			await save_waf_cookies(cache_key, waf_cookies)
			logger.info(f'{account_name}: Fresh WAF cookies cached (key={cache_key})')
		except Exception as e:
			logger.warning(f'{account_name}: Failed to cache fresh WAF cookies: {e}')

	return waf_cookies


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
		return {'success': False, 'status': 'failed', 'message': msg}

	if not _resolve_domain(provider_config, account_row):
		msg = f'Provider "{account_row["provider"]}" 无域名，且账号未指定域名'
		await add_checkin_log(
			account_id=account_row['id'],
			account_name=account_row['name'],
			provider=account_row['provider'],
			status='failed',
			message=msg,
			triggered_by=triggered_by,
		)
		return {'success': False, 'status': 'failed', 'message': msg}

	try:
		result = await browser_login_checkin(
			account_name=account_row['name'],
			domain=provider_config.domain,
			login_path=provider_config.login_path,
			username=account_row.get('username', ''),
			password=account_row.get('password', ''),
			user_info_path=provider_config.user_info_path,
			sign_in_path=provider_config.sign_in_path,
		)

		message = result.get('message', '')
		status, success_flag = _normalize_status(result.get('success', False), message)
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
			message=message,
			triggered_by=triggered_by,
		)

		return {'success': success_flag, 'status': status, 'message': message}

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
		return {'success': False, 'status': 'failed', 'message': msg}


async def _run_cookie_checkin(account_row: dict, triggered_by: str) -> dict:
	"""使用 Cookie 方式签到（带 WAF cookie 缓存和挑战检测）"""
	from checkin import check_in_account, is_waf_challenge_response, parse_cookies
	from dataclasses import replace as dc_replace
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
		return {'success': False, 'status': 'failed', 'message': msg}

	if not _resolve_domain(provider_config, account_row):
		msg = f'Provider "{account_row["provider"]}" 无域名，且账号未指定域名'
		await add_checkin_log(
			account_id=account_row['id'],
			account_name=account_row['name'],
			provider=account_row['provider'],
			status='failed',
			message=msg,
			triggered_by=triggered_by,
		)
		return {'success': False, 'status': 'failed', 'message': msg}

	# --- WAF cookie 缓存优先 ---
	# 保存原始 provider_config 用于后续 WAF 挑战重试
	original_provider = provider_config
	original_needs_waf = provider_config.needs_waf_cookies()
	checkin_account_row = account_row

	if original_needs_waf:
		waf_cookies = await _get_waf_cookies_cached(
			account_row['name'], provider_config, account_row
		)
		if waf_cookies is None:
			# 浏览器获取失败，尝试不用 WAF 作为回退
			logger.warning(f'{account_row["name"]}: WAF cookie fetch failed, trying without WAF')
			provider_config = dc_replace(provider_config, bypass_method=None, waf_cookie_names=None)
		elif waf_cookies:
			# 将缓存的 WAF cookies 合并到账号 cookies 中，跳过浏览器
			raw_cookies = account_row['cookies']
			try:
				raw_cookies = json.loads(raw_cookies)
			except (json.JSONDecodeError, TypeError):
				pass
			user_cookies = parse_cookies(raw_cookies)
			merged = {**waf_cookies, **user_cookies}
			checkin_account_row = {**account_row, 'cookies': json.dumps(merged)}
			provider_config = dc_replace(provider_config, bypass_method=None, waf_cookie_names=None)
		# waf_cookies == {} 表示不需要 WAF，直接继续

	app_config = AppConfig(providers={account_row['provider']: provider_config})
	account_config = _db_account_to_config(checkin_account_row, 0)

	try:
		success, user_info = await check_in_account(account_config, 0, app_config)

		waf_hint = ''

		# --- WAF 挑战检测 + 缓存刷新重试 ---
		if not success and original_needs_waf and user_info:
			checkin_message = user_info.get('checkin_message', '')
			is_waf = (
				user_info.get('_waf_challenge')
				or is_waf_challenge_response(checkin_message)
			)

			if is_waf:
				logger.info(f'{account_row["name"]}: WAF challenge detected, refreshing cookies...')
				fresh_waf = await _invalidate_and_refresh_waf_cookies(
					account_row['name'], original_provider, account_row
				)
				if fresh_waf:
					# 用新 cookies 重试
					raw_cookies = account_row['cookies']
					try:
						raw_cookies = json.loads(raw_cookies)
					except (json.JSONDecodeError, TypeError):
						pass
					user_cookies = parse_cookies(raw_cookies)
					merged_fresh = {**fresh_waf, **user_cookies}
					retry_row = {**account_row, 'cookies': json.dumps(merged_fresh)}
					retry_provider = dc_replace(original_provider, bypass_method=None, waf_cookie_names=None)
					retry_app_config = AppConfig(providers={account_row['provider']: retry_provider})
					retry_account_config = _db_account_to_config(retry_row, 0)

					success, user_info = await check_in_account(retry_account_config, 0, retry_app_config)
					if success:
						waf_hint = 'WAF cookies refreshed successfully'
						logger.info(f'{account_row["name"]}: Check-in succeeded after WAF refresh')

		# --- 最终兜底：去掉 WAF 重试 ---
		if not success and not waf_hint and original_needs_waf:
			logger.info(f'WAF bypass failed for {account_row["name"]}, retrying without WAF...')
			provider_no_waf = dc_replace(original_provider, bypass_method=None, waf_cookie_names=None)
			app_config_retry = AppConfig(providers={account_row['provider']: provider_no_waf})
			# 使用原始 cookies（不含 WAF cookies）
			account_config_orig = _db_account_to_config(account_row, 0)
			success, user_info = await check_in_account(account_config_orig, 0, app_config_retry)
			if success:
				waf_hint = '签到成功（无需 WAF 绕过），建议将该 Provider 的 WAF 绕过设置为「无」'
				logger.info(f'{account_row["name"]}: {waf_hint}')

		# --- 清理内部标记 ---
		if user_info:
			user_info.pop('_waf_challenge', None)

		balance = user_info.get('quota') if user_info and user_info.get('success') else None
		used = user_info.get('used_quota') if user_info and user_info.get('success') else None
		msg = ''
		checkin_status = user_info.get('checkin_status') if user_info else None
		checkin_message = user_info.get('checkin_message', '') if user_info else ''

		if checkin_status == 'already_checked_in':
			status = 'already_checked_in'
			success = True
		elif checkin_status == 'failed':
			status = 'failed'
			success = False
		else:
			status, success = _normalize_status(success, checkin_message)

		if checkin_message:
			msg = checkin_message
		elif user_info and user_info.get('success'):
			msg = f'Balance: ${balance}, Used: ${used}'
		elif user_info:
			msg = user_info.get('error', '')

		if status == 'already_checked_in' and not msg:
			msg = 'Already checked in today'
		if not success and not msg:
			msg = 'Check-in failed (WAF bypass or request error)'

		if waf_hint:
			msg = f'{msg} | {waf_hint}' if msg else waf_hint

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

		return {'success': success, 'status': status, 'message': msg}

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
		return {'success': False, 'status': 'failed', 'message': msg}


async def run_checkin_task(triggered_by='schedule') -> dict:
	async with _checkin_lock:
		accounts = await get_enabled_accounts()
		if not accounts:
			logger.info('No enabled accounts found')
			return {'success_count': 0, 'total_count': 0}

		success_count = 0
		failed_count = 0
		total_count = len(accounts)

		for acc in accounts:
			try:
				result = await run_checkin_single(acc, triggered_by=triggered_by)
				status = result.get('status')
				if not status:
					status = 'success' if result.get('success') else 'failed'

				if status in {'success', 'already_checked_in'}:
					success_count += 1
				elif status == 'failed':
					failed_count += 1
			except Exception as e:
				failed_count += 1
				logger.error(f'Error checking in account {acc["name"]}: {e}')

		# Send notification only when there are real failures
		if failed_count > 0:
			try:
				from utils.notify import notify
				content = f'签到完成: {success_count}/{total_count} 成功'
				notify.push_message('AnyRouter Check-in', content, msg_type='text')
			except Exception as e:
				logger.error(f'Notification failed: {e}')

		logger.info(
			f'Check-in completed: success={success_count}, failed={failed_count}, total={total_count}'
		)
		return {
			'success_count': success_count,
			'total_count': total_count,
		}
