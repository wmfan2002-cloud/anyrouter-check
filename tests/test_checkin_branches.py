import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

# Add project root to import path.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from checkin import execute_check_in
from utils.config import ProviderConfig
from web import scheduler


class _MockResponse:
	def __init__(self, status_code: int, json_data=None, text: str = ''):
		self.status_code = status_code
		self._json_data = json_data
		self.text = text

	def json(self):
		if isinstance(self._json_data, Exception):
			raise self._json_data
		return self._json_data


class _MockClient:
	def __init__(self, response: _MockResponse):
		self._response = response

	def post(self, *args, **kwargs):
		return self._response


def test_execute_check_in_success_branch():
	resp = _MockResponse(200, {'ret': 1, 'msg': '签到成功'})
	client = _MockClient(resp)
	provider = ProviderConfig(name='p', domain='https://example.com')

	result = execute_check_in(client, 'acc', provider, {})

	assert result['success'] is True
	assert result['status'] == 'success'


def test_execute_check_in_already_checked_in_branch():
	resp = _MockResponse(200, {'ret': 0, 'msg': '今天已经签到'})
	client = _MockClient(resp)
	provider = ProviderConfig(name='p', domain='https://example.com')

	result = execute_check_in(client, 'acc', provider, {})

	assert result['success'] is True
	assert result['status'] == 'already_checked_in'
	assert '签到' in result['message']


def test_execute_check_in_failure_branch():
	resp = _MockResponse(500, text='internal error')
	client = _MockClient(resp)
	provider = ProviderConfig(name='p', domain='https://example.com')

	result = execute_check_in(client, 'acc', provider, {})

	assert result['success'] is False
	assert result['status'] == 'failed'
	assert 'HTTP 500' in result['message']


def test_execute_check_in_auth_failure_branch():
	resp = _MockResponse(200, {'ret': 0, 'msg': 'invalid api user'})
	client = _MockClient(resp)
	provider = ProviderConfig(name='p', domain='https://example.com')

	result = execute_check_in(client, 'acc', provider, {})

	assert result['success'] is False
	assert result['status'] == 'failed'
	assert 'invalid api user' in result['message'].lower()


def test_execute_check_in_network_failure_branch():
	resp = _MockResponse(200, {'ret': 0, 'msg': 'connection timed out'})
	client = _MockClient(resp)
	provider = ProviderConfig(name='p', domain='https://example.com')

	result = execute_check_in(client, 'acc', provider, {})

	assert result['success'] is False
	assert result['status'] == 'failed'
	assert 'timed out' in result['message'].lower()


def test_scheduler_cookie_mode_records_already_checked_in(monkeypatch):
	provider = ProviderConfig(
		name='new-api',
		domain='https://example.com',
		login_path='/login',
		sign_in_path='/api/user/sign_in',
		user_info_path='/api/user/self',
		api_user_key='new-api-user',
		bypass_method='waf_cookies',
		waf_cookie_names=['acw_tc'],
	)

	account_row = {
		'id': 1,
		'name': 'acc',
		'provider': 'new-api',
		'api_user': '123',
		'cookies': '{}',
	}

	monkeypatch.setattr(scheduler, '_build_provider_config', AsyncMock(return_value=provider))
	monkeypatch.setattr(scheduler, 'update_account', AsyncMock())
	monkeypatch.setattr(scheduler, 'get_cached_waf_cookies', AsyncMock(return_value={'acw_tc': 'cached'}))
	monkeypatch.setattr(scheduler, 'save_waf_cookies', AsyncMock())
	monkeypatch.setattr(scheduler, 'delete_waf_cookies', AsyncMock())
	log_mock = AsyncMock()
	monkeypatch.setattr(scheduler, 'add_checkin_log', log_mock)

	import checkin as checkin_module

	async def _fake_check_in_account(*args, **kwargs):
		return True, {
			'success': True,
			'quota': 10.0,
			'used_quota': 1.0,
			'checkin_status': 'already_checked_in',
			'checkin_message': 'already checked in',
		}

	monkeypatch.setattr(checkin_module, 'check_in_account', _fake_check_in_account)

	result = asyncio.run(scheduler._run_cookie_checkin(account_row, triggered_by='manual'))

	assert result['success'] is True
	assert 'already checked in' in result['message']
	assert log_mock.await_count == 1
	assert log_mock.await_args.kwargs['status'] == 'already_checked_in'


def test_scheduler_browser_mode_records_already_checked_in(monkeypatch):
	provider = ProviderConfig(
		name='new-api',
		domain='https://example.com',
		login_path='/login',
		sign_in_path='/api/user/sign_in',
		user_info_path='/api/user/self',
		api_user_key='new-api-user',
		bypass_method='waf_cookies',
		waf_cookie_names=['acw_tc'],
	)

	account_row = {
		'id': 1,
		'name': 'acc',
		'provider': 'new-api',
		'auth_method': 'browser_login',
		'username': 'u',
		'password': 'p',
	}

	monkeypatch.setattr(scheduler, '_build_provider_config', AsyncMock(return_value=provider))
	monkeypatch.setattr(scheduler, 'update_account', AsyncMock())
	log_mock = AsyncMock()
	monkeypatch.setattr(scheduler, 'add_checkin_log', log_mock)

	from web import browser_checkin

	monkeypatch.setattr(
		browser_checkin,
		'browser_login_checkin',
		AsyncMock(return_value={'success': False, 'message': 'Already checked in today'}),
	)

	result = asyncio.run(scheduler._run_browser_login_checkin(account_row, triggered_by='manual'))

	assert result['success'] is True
	assert 'checked in' in result['message'].lower()
	assert log_mock.await_count == 1
	assert log_mock.await_args.kwargs['status'] == 'already_checked_in'
