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
	sign_in_path: str | None = None,
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
	domain = domain.rstrip('/')
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
				password_visible = False
				try:
					pw_loc = page.locator('input[type="password"]')
					if await pw_loc.count() > 0 and await pw_loc.first.is_visible():
						password_visible = True
					else:
						await page.wait_for_selector('input[type="password"]:visible', timeout=5000)
						password_visible = True
				except Exception:
					password_visible = False

				# If password field not visible, try clicking OAuth → email/password toggle
				if not password_visible:
					logger.info(f'[PROCESSING] {account_name}: Password field hidden, looking for login mode toggle...')
					toggle_found = False
					for toggle_sel in [
						'text=/使用.*邮箱.*登录/',
						'text=/使用.*用户名.*登录/',
						'text=/邮箱.*用户名/',
						'text=/账号密码登录/',
						'text=/密码登录/',
					]:
						try:
							toggle = page.locator(toggle_sel).first
							if await toggle.count() > 0 and await toggle.is_visible():
								logger.info(f'[PROCESSING] {account_name}: Clicking login mode toggle...')
								await toggle.click()
								await page.wait_for_timeout(1500)
								toggle_found = True
								break
						except Exception:
							continue

					if not toggle_found:
						# Try broader search: any visible button/link with email-related keywords
						for sel in ['button:visible', 'a:visible', 'span:visible']:
							try:
								elems = await page.locator(sel).all()
								for el in elems:
									txt = (await el.text_content() or '').strip()
									if any(kw in txt for kw in ['邮箱', '用户名', '密码登录', 'email', 'password']):
										if '继续' not in txt and 'OAuth' not in txt:
											logger.info(f'[PROCESSING] {account_name}: Clicking "{txt}" to reveal password form...')
											await el.click()
											await page.wait_for_timeout(1500)
											toggle_found = True
											break
								if toggle_found:
									break
							except Exception:
								continue

					# Now wait for the password field to appear
					try:
						await page.wait_for_selector('input[type="password"]:visible', timeout=10000)
					except Exception:
						await page.wait_for_timeout(3000)
						pw_loc = page.locator('input[type="password"]')
						if not (await pw_loc.count() > 0 and await pw_loc.first.is_visible()):
							await context.close()
							return {
								'success': False,
								'quota': None,
								'used_quota': None,
								'message': 'Cannot find password field (login page may require OAuth only)',
							}

				# Step 2: Dismiss any popup/modal overlays before filling form
				logger.info(f'[PROCESSING] {account_name}: Checking for popup overlays...')
				try:
					for close_sel in [
						'.semi-portal .semi-modal-content .semi-modal-header .semi-icon-close',
						'.semi-portal .semi-icon-close',
						'.semi-modal-close',
						'.semi-notification-close',
					]:
						close_btn = page.locator(close_sel).first
						if await close_btn.count() > 0 and await close_btn.is_visible():
							await close_btn.click()
							await page.wait_for_timeout(500)
							logger.info(f'{account_name}: Dismissed popup via close button')
							break
					else:
						overlay = page.locator('.semi-portal .semi-modal-mask, .semi-overlay')
						if await overlay.count() > 0 and await overlay.is_visible():
							await overlay.click(position={'x': 10, 'y': 10})
							await page.wait_for_timeout(500)
							logger.info(f'{account_name}: Dismissed popup via overlay click')
						else:
							await page.evaluate('document.querySelectorAll(".semi-portal").forEach(el => el.remove())')
							await page.wait_for_timeout(300)
				except Exception as e:
					logger.debug(f'{account_name}: Popup dismiss attempt: {e}')
					try:
						await page.evaluate('document.querySelectorAll(".semi-portal").forEach(el => el.remove())')
						await page.wait_for_timeout(300)
					except Exception:
						pass

				# Step 3: Fill in credentials
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

				# Step 4: Click login button
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

				# Step 5: Wait for login to complete (URL changes away from /login)
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

				# Step 6: Wait for page to stabilize
				await page.wait_for_timeout(3000)

				# Helper: build auth headers from localStorage
				async def _get_auth_headers_js():
					return await page.evaluate('''
						() => {
							const userToken = localStorage.getItem("user") || "";
							const headers = { "Accept": "application/json" };
							if (userToken) {
								try {
									const parsed = JSON.parse(userToken);
									if (parsed.token) headers["Authorization"] = "Bearer " + parsed.token;
									if (parsed.id) headers["New-Api-User"] = String(parsed.id);
								} catch(e) {
									headers["Authorization"] = "Bearer " + userToken;
								}
							}
							return headers;
						}
					''')

				# Step 7: Execute check-in API call if sign_in_path is configured
				checkin_message = ''
				if sign_in_path:
					checkin_url = f'{domain}{sign_in_path}'
					logger.info(f'[PROCESSING] {account_name}: Calling check-in API: POST {checkin_url}')
					checkin_response = await page.evaluate(f'''
						async () => {{
							try {{
								const userToken = localStorage.getItem("user") || "";
								const headers = {{
									"Accept": "application/json",
									"Content-Type": "application/json",
								}};
								if (userToken) {{
									try {{
										const parsed = JSON.parse(userToken);
										if (parsed.token) headers["Authorization"] = "Bearer " + parsed.token;
										if (parsed.id) headers["New-Api-User"] = String(parsed.id);
									}} catch(e) {{
										headers["Authorization"] = "Bearer " + userToken;
									}}
								}}
								const res = await fetch("{checkin_url}", {{
									method: "POST",
									headers: headers,
								}});
								return await res.json();
							}} catch(e) {{
								return {{ error: e.message }};
							}}
						}}
					''')

					if checkin_response:
						if checkin_response.get('error'):
							logger.warning(f'[WARN] {account_name}: Check-in API error: {checkin_response["error"]}')
							checkin_message = checkin_response['error']
						else:
							raw_msg = (checkin_response.get('msg')
									   or checkin_response.get('message')
									   or checkin_response.get('error')
									   or '')
							is_success = (checkin_response.get('ret') == 1
										  or checkin_response.get('code') == 0
										  or checkin_response.get('success') is True)
							if is_success:
								logger.info(f'[SUCCESS] {account_name}: Check-in API returned success: {raw_msg}')
								checkin_message = raw_msg or 'Check-in successful'
							else:
								logger.info(f'[INFO] {account_name}: Check-in API response: {raw_msg}')
								checkin_message = raw_msg
				else:
					logger.info(f'[INFO] {account_name}: No sign_in_path, skipping explicit check-in call')

				# Brief delay to let the server update the balance after check-in
				if sign_in_path:
					await page.wait_for_timeout(2000)

				# Step 8: Fetch balance via API using the browser's authenticated session
				logger.info(f'[PROCESSING] {account_name}: Fetching balance info...')
				user_info_url = f'{domain}{user_info_path}'

				api_response = await page.evaluate(f'''
					async () => {{
						try {{
							const userToken = localStorage.getItem("user") || "";
							const headers = {{ "Accept": "application/json" }};
							if (userToken) {{
								try {{
									const parsed = JSON.parse(userToken);
									if (parsed.token) headers["Authorization"] = "Bearer " + parsed.token;
									if (parsed.id) headers["New-Api-User"] = String(parsed.id);
								}} catch(e) {{
									headers["Authorization"] = "Bearer " + userToken;
								}}
							}}
							const res = await fetch("{user_info_url}", {{ headers }});
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
					logger.warning(f'[WARN] {account_name}: Unexpected API response: {str(api_response)[:300]}')

				await context.close()

				msg = f'Balance: ${quota}, Used: ${used_quota}' if quota is not None else 'Login OK, balance unknown'
				if checkin_message:
					msg = f'{checkin_message} | {msg}'
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
