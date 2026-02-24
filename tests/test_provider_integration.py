import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

# Add project root to import path.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.config import AppConfig
from web import database, scheduler


def test_default_providers_include_newapi(monkeypatch):
	monkeypatch.delenv('PROVIDERS', raising=False)

	config = AppConfig.load_from_env()
	assert 'newapi' in config.providers

	provider = config.providers['newapi']
	assert provider.domain == ''
	assert provider.login_path == '/login'
	assert provider.sign_in_path == '/api/user/checkin'
	assert provider.user_info_path == '/api/user/self'
	assert provider.api_user_key == 'new-api-user'


def test_init_builtin_providers_contains_newapi_defaults():
	select_names = []
	insert_rows = []

	class _Cursor:
		async def fetchone(self):
			return None

	async def _execute(sql, params=()):
		if sql.startswith('SELECT id FROM providers WHERE name = ?'):
			select_names.append(params[0])
			return _Cursor()
		if 'INSERT INTO providers' in sql:
			insert_rows.append(params)
			return None
		return None

	mock_db = AsyncMock()
	mock_db.execute.side_effect = _execute

	asyncio.run(database._init_builtin_providers(mock_db))

	assert 'newapi' in select_names
	newapi_rows = [row for row in insert_rows if row[0] == 'newapi']
	assert len(newapi_rows) == 1
	assert newapi_rows[0][1] == ''
	assert newapi_rows[0][2] == '/login'
	assert newapi_rows[0][3] == '/api/user/checkin'
	assert newapi_rows[0][4] == '/api/user/self'
	assert newapi_rows[0][5] == 'new-api-user'


def test_scheduler_build_provider_config_uses_provider_specific_fields(monkeypatch):
	async def _fake_get_all_providers():
		return [
			{
				'name': 'new-api-a',
				'domain': 'https://a.example.com',
				'login_path': '/login-a',
				'sign_in_path': '/checkin-a',
				'user_info_path': '/self-a',
				'api_user_key': 'x-user-a',
				'bypass_method': 'waf_cookies',
				'waf_cookie_names': '["acw_tc"]',
			},
			{
				'name': 'new-api-b',
				'domain': 'https://b.example.com',
				'login_path': '/login-b',
				'sign_in_path': '/checkin-b',
				'user_info_path': '/self-b',
				'api_user_key': 'x-user-b',
				'bypass_method': None,
				'waf_cookie_names': None,
			},
		]

	monkeypatch.setattr(scheduler, 'get_all_providers', _fake_get_all_providers)

	provider_a = asyncio.run(scheduler._build_provider_config('new-api-a'))
	provider_b = asyncio.run(scheduler._build_provider_config('new-api-b'))

	assert provider_a is not None
	assert provider_b is not None
	assert provider_a.domain == 'https://a.example.com'
	assert provider_b.domain == 'https://b.example.com'
	assert provider_a.sign_in_path == '/checkin-a'
	assert provider_b.sign_in_path == '/checkin-b'
	assert provider_a.api_user_key == 'x-user-a'
	assert provider_b.api_user_key == 'x-user-b'
