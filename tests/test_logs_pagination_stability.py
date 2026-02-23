import sys
from pathlib import Path

# Add project root to import path.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from web.routes.logs import _parse_positive_int


def test_parse_positive_int_handles_invalid_values():
	assert _parse_positive_int('3', 1) == 3
	assert _parse_positive_int('0', 1) == 1
	assert _parse_positive_int('-1', 1) == 1
	assert _parse_positive_int('abc', 1) == 1
	assert _parse_positive_int('', 1) == 1


def test_logs_query_uses_stable_desc_order():
	source = (project_root / 'web' / 'database.py').read_text(encoding='utf-8')
	assert 'ORDER BY created_at DESC, id DESC' in source


def test_logs_template_keeps_filters_in_pagination_links():
	template = (project_root / 'web' / 'templates' / 'logs.html').read_text(encoding='utf-8')
	assert 'status={{ filter_status or \'\' }}&account_id={{ filter_account or \'\' }}' in template
