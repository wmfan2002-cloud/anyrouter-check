import sys
from pathlib import Path

# Add project root to import path.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest

from web.failure_reason import categorize_checkin_result


@pytest.mark.parametrize(
	'status,message,expected',
	[
		('failed', 'cookie expired, please login again', 'auth_failed'),
		('failed', 'Missing WAF cookies: acw_tc', 'waf_blocked'),
		('failed', 'connection timed out while requesting user info', 'network_error'),
		('failed', 'something unexpected happened', 'unknown_error'),
		('already_checked_in', 'Already checked in today', 'already_checked_in'),
		('failed', 'already checked in today', 'already_checked_in'),
	],
)
def test_categorize_checkin_result(status, message, expected):
	assert categorize_checkin_result(status, message) == expected


def test_categorize_checkin_result_uses_priority_for_conflicts():
	message = 'cookie expired after waf challenge timeout'
	assert categorize_checkin_result('failed', message) == 'auth_failed'
