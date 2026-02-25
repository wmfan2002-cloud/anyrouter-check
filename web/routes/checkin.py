from fastapi import APIRouter
from fastapi.responses import JSONResponse

from web.database import get_account

router = APIRouter()


@router.post('/api/checkin/all')
async def api_checkin_all():
	from web.scheduler import run_checkin_task
	try:
		result = await run_checkin_task(triggered_by='manual')
		return JSONResponse({
			'success': True,
			'success_count': result['success_count'],
			'total_count': result['total_count'],
		})
	except Exception as e:
		return JSONResponse({'success': False, 'message': str(e)})


@router.post('/api/checkin/{account_id}')
async def api_checkin_single(account_id: int):
	from web.scheduler import run_checkin_single
	account = await get_account(account_id)
	if not account:
		return JSONResponse({'success': False, 'message': '账号不存在'})

	try:
		result = await run_checkin_single(account, triggered_by='manual')
		status = result.get('status')
		if not status:
			status = 'success' if result.get('success') else 'failed'
		return JSONResponse({
			'success': result['success'],
			'status': status,
			'message': result.get('message', ''),
		})
	except Exception as e:
		return JSONResponse({'success': False, 'message': str(e)})
