import sys
from pathlib import Path

# Add project root to import path.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest

from web.routes.providers import _is_valid_domain, _normalize_waf_cookie_names


def test_is_valid_domain_accepts_http_and_https():
	assert _is_valid_domain('https://example.com')
	assert _is_valid_domain('http://localhost:8080')


def test_is_valid_domain_rejects_invalid_values():
	assert not _is_valid_domain('')
	assert not _is_valid_domain('example.com')
	assert not _is_valid_domain('ftp://example.com')


def test_normalize_waf_cookie_names_accepts_list_and_string():
	assert _normalize_waf_cookie_names(['acw_tc', 'cdn_sec_tc']) == ['acw_tc', 'cdn_sec_tc']
	assert _normalize_waf_cookie_names('acw_tc, cdn_sec_tc') == ['acw_tc', 'cdn_sec_tc']
	assert _normalize_waf_cookie_names(None) == []


def test_normalize_waf_cookie_names_rejects_invalid_name():
	with pytest.raises(ValueError):
		_normalize_waf_cookie_names(['acw tc'])

	with pytest.raises(ValueError):
		_normalize_waf_cookie_names('acw_tc;bad')
