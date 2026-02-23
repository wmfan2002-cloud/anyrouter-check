import sys
from pathlib import Path

# Add project root to import path.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_dashboard_recent_logs_limit_stays_10():
	source = (project_root / 'web' / 'app.py').read_text(encoding='utf-8')
	assert 'get_checkin_logs(limit=10)' in source


def test_dashboard_template_has_logs_history_entry():
	template = (project_root / 'web' / 'templates' / 'dashboard.html').read_text(encoding='utf-8')
	assert '查看全部执行记录' in template
	assert 'href="/logs"' in template
