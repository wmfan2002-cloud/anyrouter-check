"""
浏览器自动登录签到模块

通过 Playwright 无头浏览器模拟用户登录，登录成功后自动完成签到，
然后通过 API 获取余额信息。
"""

import asyncio
import logging
import tempfile

from playwright.async_api import async_playwright

logger = logging.getLogger('browser_checkin')


async def browser_login_checkin(
	account_name: str,
	domain: str,
	login_path: str,
	username: str,
	password: str,
	user_info_path: str = '/api/user/self',
) -> dict:
	"""
	使用浏览器登录并完成签到。

	返回:
		{
			'success': bool,
			'quota': float | None,
			'used_quota': float | None,
			'message': str,
		}
	"""
	login_url = f'{domain}{login_path}'
	logger.info(f'[PROCESSING] {account_name}: Starting browser login to {domain}')

	async with async_playwright() as p:
		with tempfile.TemporaryDirectory() as temp_dir:
			context = await p.chromium.launch_persistent_context(
				user_data_dir=temp_dir,
				headless=True,
				user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
				viewport={'width': 1920, 'height': 1080},
				args=[
					'--disable-blink-features=AutomationControlled',
					'--disable-dev-shm-usage',
					'--disable-web-security',
					'--disable-features=VizDisplayCompositor',
					'--no-sandbox',
				],
			)

			page = await context.new_page()

			try:
				# Step 1: Navigate to login page (WAF challenge resolves automatically)
				logger.info(f'[PROCESSING] {account_name}: Navigating to login page...')
				await page.goto(login_url, wait_until='networkidle', timeout=30000)

				# Wait for login form to appear after WAF
				logger.info(f'[PROCESSING] {account_name}: Waiting for login form...')
				try:
					await page.wait_for_selector('input[type="password"]', timeout=15000)
				except Exception:
					# Sometimes the WAF redirects, try waiting more
					await page.wait_for_timeout(3000)
					await page.wait_for_selector('input[type="password"]', timeout=15000)

				# Step 2: Fill in credentials
				logger.info(f'[PROCESSING] {account_name}: Filling in credentials...')

				# Find the username/email input - it's typically the text input before password
				# Try common selectors for NewAPI/OneAPI login forms
				username_input = None
				for selector in [
					'input[name="username"]',
					'input[name="email"]',
					'input[type="email"]',
					'input[type="text"]',
					'input[id="username"]',
					'input[id="email"]',
				]:
					elem = page.locator(selector).first
					if await elem.count() > 0 and await elem.is_visible():
						username_input = elem
						break

				if not username_input:
					# Fallback: find all visible text/email inputs
					inputs = page.locator('input:visible').all()
					for inp in await inputs:
						input_type = await inp.get_attribute('type') or 'text'
						if input_type in ('text', 'email', 'tel'):
							username_input = inp
							break

				if not username_input:
					await context.close()
					return {
						'success': False,
						'quota': None,
						'used_quota': None,
						'message': 'Cannot find username input field',
					}

				password_input = page.locator('input[type="password"]').first

				# Clear and fill
				await username_input.click()
				await username_input.fill(username)
				await password_input.click()
				await password_input.fill(password)

				# Step 3: Click login button
				logger.info(f'[PROCESSING] {account_name}: Submitting login...')
				submit_btn = None
				for selector in [
					'button[type="submit"]',
					'button:has-text("登录")',
					'button:has-text("Login")',
					'button:has-text("Sign in")',
					'input[type="submit"]',
				]:
					elem = page.locator(selector).first
					if await elem.count() > 0 and await elem.is_visible():
						submit_btn = elem
						break

				if not submit_btn:
					# Fallback: press Enter on password field
					await password_input.press('Enter')
				else:
					await submit_btn.click()

				# Step 4: Wait for login to complete (URL changes away from /login)
				logger.info(f'[PROCESSING] {account_name}: Waiting for login result...')
				try:
					await page.wait_for_url(
						lambda url: '/login' not in url,
						timeout=15000,
					)
				except Exception:
					# Check if still on login page with error
					current_url = page.url
					if '/login' in current_url:
						# Try to find error message on page
						error_text = ''
						for sel in ['.error', '.alert', '[role="alert"]', '.MuiAlert-message', '.ant-message']:
							elem = page.locator(sel).first
							if await elem.count() > 0:
								error_text = await elem.text_content()
								break
						await context.close()
						return {
							'success': False,
							'quota': None,
							'used_quota': None,
							'message': f'Login failed: {error_text or "still on login page after timeout"}',
						}

				logger.info(f'[SUCCESS] {account_name}: Login successful, current URL: {page.url}')

				# Step 5: Wait for page to stabilize (auto check-in may happen)
				await page.wait_for_timeout(3000)

				# Step 6: Fetch balance via API using the browser's authenticated session
				logger.info(f'[PROCESSING] {account_name}: Fetching balance info...')
				user_info_url = f'{domain}{user_info_path}'

				api_response = await page.evaluate(f'''
					async () => {{
						try {{
							const res = await fetch("{user_info_url}", {{
								headers: {{ "Accept": "application/json" }}
							}});
							return await res.json();
						}} catch(e) {{
							return {{ error: e.message }};
						}}
					}}
				''')

				quota = None
				used_quota = None

				if api_response and api_response.get('success'):
					user_data = api_response.get('data', {})
					quota = round(user_data.get('quota', 0) / 500000, 2)
					used_quota = round(user_data.get('used_quota', 0) / 500000, 2)
					logger.info(f'[SUCCESS] {account_name}: Balance=${quota}, Used=${used_quota}')
				elif api_response and api_response.get('error'):
					logger.warning(f'[WARN] {account_name}: API error: {api_response["error"]}')
				else:
					logger.warning(f'[WARN] {account_name}: Unexpected API response')

				await context.close()

				msg = f'Balance: ${quota}, Used: ${used_quota}' if quota is not None else 'Login OK, balance unknown'
				return {
					'success': True,
					'quota': quota,
					'used_quota': used_quota,
					'message': msg,
				}

			except Exception as e:
				logger.error(f'[FAILED] {account_name}: Browser login error: {e}')
				await context.close()
				return {
					'success': False,
					'quota': None,
					'used_quota': None,
					'message': str(e)[:200],
				}
