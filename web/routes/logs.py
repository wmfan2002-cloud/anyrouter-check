from fastapi import APIRouter, Request

from web.database import get_all_accounts, get_checkin_logs, get_log_count
from web.failure_reason import summarize_reason

router = APIRouter()

PAGE_SIZE = 30


def _parse_positive_int(value: str | None, default: int | None = None) -> int | None:
	if value is None or value == '':
		return default
	try:
		parsed = int(value)
	except (TypeError, ValueError):
		return default
	return parsed if parsed > 0 else default


@router.get('/logs')
async def logs_page(request: Request):
	from web.app import templates

	page = _parse_positive_int(request.query_params.get('page'), 1) or 1
	status = request.query_params.get('status', '') or None
	account_id = request.query_params.get('account_id', '') or None

	account_id_int = _parse_positive_int(account_id)

	total = await get_log_count(account_id=account_id_int, status=status)
	total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
	page = min(page, total_pages)

	offset = (page - 1) * PAGE_SIZE
	logs = await get_checkin_logs(limit=PAGE_SIZE, offset=offset, account_id=account_id_int, status=status)
	for log in logs:
		log.update(summarize_reason(log.get('status'), log.get('message')))

	accounts = await get_all_accounts()

	return templates.TemplateResponse('logs.html', {
		'request': request,
		'logs': logs,
		'accounts': accounts,
		'current_page': page,
		'total_pages': total_pages,
		'filter_status': status or '',
		'filter_account': account_id or '',
		'active_page': 'logs',
	})
