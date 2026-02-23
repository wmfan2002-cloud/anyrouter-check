from fastapi import APIRouter, Request

from web.database import get_all_accounts, get_checkin_logs, get_log_count
from web.failure_reason import categorize_checkin_result

router = APIRouter()

PAGE_SIZE = 30


@router.get('/logs')
async def logs_page(request: Request):
	from web.app import templates

	page = int(request.query_params.get('page', 1))
	status = request.query_params.get('status', '') or None
	account_id = request.query_params.get('account_id', '') or None

	if account_id:
		account_id_int = int(account_id)
	else:
		account_id_int = None

	offset = (page - 1) * PAGE_SIZE
	logs = await get_checkin_logs(limit=PAGE_SIZE, offset=offset, account_id=account_id_int, status=status)
	for log in logs:
		log['error_category'] = categorize_checkin_result(log.get('status'), log.get('message'))

	total = await get_log_count(account_id=account_id_int, status=status)
	total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

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
