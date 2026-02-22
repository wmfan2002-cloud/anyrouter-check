// Toast notification - Memphis style
function showToast(message, type = 'success') {
	const container = document.getElementById('toast-container');
	const toast = document.createElement('div');
	const colors = type === 'success'
		? 'bg-[#1dd1a1] text-black border-4 border-black'
		: type === 'error'
			? 'bg-[#ff6b6b] text-white border-4 border-black'
			: 'bg-[#48dbfb] text-black border-4 border-black';

	toast.className = `toast ${colors} px-5 py-3 shadow-[4px_4px_0px_#000] font-black text-sm`;
	toast.textContent = message;
	container.appendChild(toast);
	setTimeout(() => toast.remove(), 3000);
}

// Check-in all accounts
async function runCheckinAll() {
	const btn = document.getElementById('btn-checkin-all');
	if (btn) {
		btn.disabled = true;
		btn.innerHTML = '<svg class="animate-spin w-5 h-5 mr-2" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path></svg>签到中...';
	}
	try {
		const res = await fetch('/api/checkin/all', { method: 'POST' });
		const result = await res.json();
		if (result.success) {
			showToast(`签到完成: ${result.success_count}/${result.total_count} 成功`, 'success');
			setTimeout(() => location.reload(), 1500);
		} else {
			showToast(result.message || '签到失败', 'error');
		}
	} catch (e) {
		showToast('请求失败: ' + e.message, 'error');
	} finally {
		if (btn) {
			btn.disabled = false;
			btn.innerHTML = '<svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" stroke-width="3" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/></svg>立即全部签到';
		}
	}
}

// Check-in single account
async function runCheckinSingle(accountId) {
	showToast('签到中...', 'info');
	try {
		const res = await fetch(`/api/checkin/${accountId}`, { method: 'POST' });
		const result = await res.json();
		if (result.success) {
			showToast('签到成功', 'success');
			setTimeout(() => location.reload(), 1500);
		} else {
			showToast(result.message || '签到失败', 'error');
		}
	} catch (e) {
		showToast('请求失败: ' + e.message, 'error');
	}
}
