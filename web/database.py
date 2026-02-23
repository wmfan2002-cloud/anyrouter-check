import json
import os
from datetime import datetime

import aiosqlite

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'checkin.db')


async def get_db():
	os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
	db = await aiosqlite.connect(DB_PATH)
	db.row_factory = aiosqlite.Row
	await db.execute('PRAGMA journal_mode=WAL')
	return db


async def init_db():
	db = await get_db()
	try:
		await db.executescript('''
			CREATE TABLE IF NOT EXISTS accounts (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL,
				provider TEXT NOT NULL DEFAULT 'anyrouter',
				auth_method TEXT NOT NULL DEFAULT 'cookie',
				cookies TEXT NOT NULL DEFAULT '',
				api_user TEXT NOT NULL DEFAULT '',
				username TEXT NOT NULL DEFAULT '',
				password TEXT NOT NULL DEFAULT '',
				enabled INTEGER NOT NULL DEFAULT 1,
				last_checkin TEXT,
				last_status TEXT,
				last_balance REAL,
				last_used REAL,
				created_at TEXT NOT NULL,
				updated_at TEXT NOT NULL
			);

			CREATE TABLE IF NOT EXISTS providers (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL UNIQUE,
				domain TEXT NOT NULL,
				login_path TEXT DEFAULT '/login',
				sign_in_path TEXT DEFAULT '/api/user/sign_in',
				user_info_path TEXT DEFAULT '/api/user/self',
				api_user_key TEXT DEFAULT 'new-api-user',
				bypass_method TEXT,
				waf_cookie_names TEXT,
				is_builtin INTEGER NOT NULL DEFAULT 0,
				created_at TEXT NOT NULL
			);

			CREATE TABLE IF NOT EXISTS checkin_logs (
				id INTEGER PRIMARY KEY AUTOINCREMENT,
				account_id INTEGER,
				account_name TEXT NOT NULL,
				provider TEXT NOT NULL,
				status TEXT NOT NULL,
				balance REAL,
				used_quota REAL,
				message TEXT,
				triggered_by TEXT NOT NULL DEFAULT 'schedule',
				created_at TEXT NOT NULL
			);

			CREATE TABLE IF NOT EXISTS settings (
				key TEXT PRIMARY KEY,
				value TEXT NOT NULL
			);
		''')
		await _init_builtin_providers(db)
		await _migrate_accounts_table(db)
		await db.commit()
	finally:
		await db.close()


async def _init_builtin_providers(db):
	builtins = [
		('new-api', 'https://new-api.example.com', '/login', '/api/user/sign_in',
		 '/api/user/self', 'new-api-user', 'waf_cookies',
		 json.dumps(['acw_tc'])),
		('anyrouter', 'https://anyrouter.top', '/login', '/api/user/sign_in',
		 '/api/user/self', 'new-api-user', 'waf_cookies',
		 json.dumps(['acw_tc', 'cdn_sec_tc', 'acw_sc__v2'])),
		('agentrouter', 'https://agentrouter.org', '/login', None,
		 '/api/user/self', 'new-api-user', 'waf_cookies',
		 json.dumps(['acw_tc'])),
	]
	for b in builtins:
		existing = await db.execute('SELECT id FROM providers WHERE name = ?', (b[0],))
		row = await existing.fetchone()
		if not row:
			await db.execute(
				'''INSERT INTO providers (name, domain, login_path, sign_in_path, user_info_path,
				   api_user_key, bypass_method, waf_cookie_names, is_builtin, created_at)
				   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)''',
				(*b, datetime.now().isoformat())
			)


async def _migrate_accounts_table(db):
	"""Add new columns to existing accounts table if missing."""
	cursor = await db.execute('PRAGMA table_info(accounts)')
	columns = {row[1] for row in await cursor.fetchall()}
	migrations = [
		('auth_method', "ALTER TABLE accounts ADD COLUMN auth_method TEXT NOT NULL DEFAULT 'cookie'"),
		('username', "ALTER TABLE accounts ADD COLUMN username TEXT NOT NULL DEFAULT ''"),
		('password', "ALTER TABLE accounts ADD COLUMN password TEXT NOT NULL DEFAULT ''"),
	]
	for col_name, sql in migrations:
		if col_name not in columns:
			await db.execute(sql)


# --- Account CRUD ---

async def get_all_accounts():
	db = await get_db()
	try:
		cursor = await db.execute('SELECT * FROM accounts ORDER BY id')
		rows = await cursor.fetchall()
		return [dict(r) for r in rows]
	finally:
		await db.close()


async def get_account(account_id: int):
	db = await get_db()
	try:
		cursor = await db.execute('SELECT * FROM accounts WHERE id = ?', (account_id,))
		row = await cursor.fetchone()
		return dict(row) if row else None
	finally:
		await db.close()


async def get_enabled_accounts():
	db = await get_db()
	try:
		cursor = await db.execute('SELECT * FROM accounts WHERE enabled = 1 ORDER BY id')
		rows = await cursor.fetchall()
		return [dict(r) for r in rows]
	finally:
		await db.close()


async def create_account(name: str, provider: str, auth_method: str = 'cookie',
						 cookies: str = '', api_user: str = '',
						 username: str = '', password: str = ''):
	now = datetime.now().isoformat()
	db = await get_db()
	try:
		cursor = await db.execute(
			'''INSERT INTO accounts (name, provider, auth_method, cookies, api_user,
			   username, password, enabled, created_at, updated_at)
			   VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)''',
			(name, provider, auth_method, cookies, api_user, username, password, now, now)
		)
		await db.commit()
		return cursor.lastrowid
	finally:
		await db.close()


async def update_account(account_id: int, **kwargs):
	kwargs['updated_at'] = datetime.now().isoformat()
	set_clause = ', '.join(f'{k} = ?' for k in kwargs)
	values = list(kwargs.values()) + [account_id]
	db = await get_db()
	try:
		await db.execute(f'UPDATE accounts SET {set_clause} WHERE id = ?', values)
		await db.commit()
	finally:
		await db.close()


async def delete_account(account_id: int):
	db = await get_db()
	try:
		await db.execute('DELETE FROM accounts WHERE id = ?', (account_id,))
		await db.commit()
	finally:
		await db.close()


async def toggle_account(account_id: int):
	db = await get_db()
	try:
		await db.execute('UPDATE accounts SET enabled = 1 - enabled, updated_at = ? WHERE id = ?',
						 (datetime.now().isoformat(), account_id))
		await db.commit()
	finally:
		await db.close()


# --- Provider CRUD ---

async def get_all_providers():
	db = await get_db()
	try:
		cursor = await db.execute('SELECT * FROM providers ORDER BY is_builtin DESC, id')
		rows = await cursor.fetchall()
		return [dict(r) for r in rows]
	finally:
		await db.close()


async def get_provider(name: str):
	db = await get_db()
	try:
		cursor = await db.execute('SELECT * FROM providers WHERE name = ?', (name,))
		row = await cursor.fetchone()
		return dict(row) if row else None
	finally:
		await db.close()


async def create_provider(name: str, domain: str, **kwargs):
	now = datetime.now().isoformat()
	db = await get_db()
	try:
		waf_names = kwargs.get('waf_cookie_names', '')
		if isinstance(waf_names, list):
			waf_names = json.dumps(waf_names)
		await db.execute(
			'''INSERT INTO providers (name, domain, login_path, sign_in_path, user_info_path,
			   api_user_key, bypass_method, waf_cookie_names, is_builtin, created_at)
			   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)''',
			(name, domain,
			 kwargs.get('login_path', '/login'),
			 kwargs.get('sign_in_path', '/api/user/sign_in'),
			 kwargs.get('user_info_path', '/api/user/self'),
			 kwargs.get('api_user_key', 'new-api-user'),
			 kwargs.get('bypass_method'),
			 waf_names,
			 now)
		)
		await db.commit()
	finally:
		await db.close()


async def update_provider(name: str, **kwargs):
	if 'waf_cookie_names' in kwargs and isinstance(kwargs['waf_cookie_names'], list):
		kwargs['waf_cookie_names'] = json.dumps(kwargs['waf_cookie_names'])
	set_clause = ', '.join(f'{k} = ?' for k in kwargs)
	values = list(kwargs.values()) + [name]
	db = await get_db()
	try:
		await db.execute(f'UPDATE providers SET {set_clause} WHERE name = ? AND is_builtin = 0', values)
		await db.commit()
	finally:
		await db.close()


async def delete_provider(name: str):
	db = await get_db()
	try:
		await db.execute('DELETE FROM providers WHERE name = ? AND is_builtin = 0', (name,))
		await db.commit()
	finally:
		await db.close()


# --- Log CRUD ---

async def add_checkin_log(account_id: int, account_name: str, provider: str,
						  status: str, balance=None, used_quota=None,
						  message='', triggered_by='schedule'):
	db = await get_db()
	try:
		await db.execute(
			'''INSERT INTO checkin_logs (account_id, account_name, provider, status,
			   balance, used_quota, message, triggered_by, created_at)
			   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
			(account_id, account_name, provider, status,
			 balance, used_quota, message, triggered_by,
			 datetime.now().isoformat())
		)
		await db.commit()
	finally:
		await db.close()


async def get_checkin_logs(limit=50, offset=0, account_id=None, status=None):
	db = await get_db()
	try:
		conditions = []
		params = []
		if account_id is not None:
			conditions.append('account_id = ?')
			params.append(account_id)
		if status:
			conditions.append('status = ?')
			params.append(status)

		where = f'WHERE {" AND ".join(conditions)}' if conditions else ''
		query = f'SELECT * FROM checkin_logs {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?'
		params.extend([limit, offset])

		cursor = await db.execute(query, params)
		rows = await cursor.fetchall()
		return [dict(r) for r in rows]
	finally:
		await db.close()


async def get_log_count(account_id=None, status=None):
	db = await get_db()
	try:
		conditions = []
		params = []
		if account_id is not None:
			conditions.append('account_id = ?')
			params.append(account_id)
		if status:
			conditions.append('status = ?')
			params.append(status)

		where = f'WHERE {" AND ".join(conditions)}' if conditions else ''
		cursor = await db.execute(f'SELECT COUNT(*) as cnt FROM checkin_logs {where}', params)
		row = await cursor.fetchone()
		return row['cnt']
	finally:
		await db.close()


# --- Settings ---

async def get_setting(key: str, default=None):
	db = await get_db()
	try:
		cursor = await db.execute('SELECT value FROM settings WHERE key = ?', (key,))
		row = await cursor.fetchone()
		return row['value'] if row else default
	finally:
		await db.close()


async def set_setting(key: str, value: str):
	db = await get_db()
	try:
		await db.execute(
			'INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
			(key, value)
		)
		await db.commit()
	finally:
		await db.close()
