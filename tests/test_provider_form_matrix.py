import sys
from pathlib import Path

# Add project root to import path.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_provider_form_has_required_templates():
	template = (project_root / 'web' / 'templates' / 'providers.html').read_text(encoding='utf-8')
	assert 'new-api 标准模板' in template
	assert 'agentrouter 自动签到模板' in template
	assert '完全自定义' in template


def test_provider_form_uses_current_field_values_on_submit():
	template = (project_root / 'web' / 'templates' / 'providers.html').read_text(encoding='utf-8')
	assert "sign_in_path: document.getElementById('pf-signin-path').value" in template
	assert "user_info_path: document.getElementById('pf-userinfo-path').value" in template
	assert "api_user_key: document.getElementById('pf-api-user-key').value" in template


def test_provider_form_has_client_side_validation_messages():
	template = (project_root / 'web' / 'templates' / 'providers.html').read_text(encoding='utf-8')
	assert '域名格式不正确，请使用 http(s):// 开头的完整地址' in template
	assert 'WAF Cookie 名称只能包含字母、数字、下划线或短横线' in template
