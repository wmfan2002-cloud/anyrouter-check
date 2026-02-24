import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from dotenv import load_dotenv

# 添加项目根目录到 PATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv(project_root / '.env')

from utils.notify import NotificationKit


@pytest.fixture
def notification_kit():
	return NotificationKit()


@pytest.fixture
def email_kit(monkeypatch):
	"""带邮件配置的 NotificationKit"""
	monkeypatch.setenv('EMAIL_USER', 'test@example.com')
	monkeypatch.setenv('EMAIL_PASS', 'password')
	monkeypatch.setenv('EMAIL_TO', 'to@example.com')
	return NotificationKit()


@pytest.fixture
def pushplus_kit(monkeypatch):
	"""带 PushPlus 配置的 NotificationKit"""
	monkeypatch.setenv('PUSHPLUS_TOKEN', 'test_token')
	return NotificationKit()


@pytest.fixture
def dingtalk_kit(monkeypatch):
	"""带钉钉配置的 NotificationKit"""
	monkeypatch.setenv('DINGDING_WEBHOOK', 'https://oapi.dingtalk.com/robot/send?access_token=test')
	return NotificationKit()


@pytest.fixture
def feishu_kit(monkeypatch):
	"""带飞书配置的 NotificationKit"""
	monkeypatch.setenv('FEISHU_WEBHOOK', 'https://open.feishu.cn/open-apis/bot/v2/hook/test')
	return NotificationKit()


@pytest.fixture
def wecom_kit(monkeypatch):
	"""带企业微信配置的 NotificationKit"""
	monkeypatch.setenv('WEIXIN_WEBHOOK', 'http://weixin.example.com')
	return NotificationKit()


@pytest.fixture
def gotify_kit(monkeypatch):
	"""带 Gotify 配置的 NotificationKit"""
	monkeypatch.setenv('GOTIFY_URL', 'https://gotify.example.com/message')
	monkeypatch.setenv('GOTIFY_TOKEN', 'test_token')
	return NotificationKit()


def test_real_notification(notification_kit):
	"""真实接口测试，需要配置.env.local文件"""
	if os.getenv('ENABLE_REAL_TEST') != 'true':
		pytest.skip('未启用真实接口测试')

	notification_kit.push_message(
		'测试消息', f'这是一条测试消息\n发送时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
	)


@patch('smtplib.SMTP_SSL')
def test_send_email(mock_smtp, email_kit):
	mock_server = MagicMock()
	mock_smtp.return_value.__enter__.return_value = mock_server

	email_kit.send_email('测试标题', '测试内容')

	assert mock_server.login.called
	assert mock_server.send_message.called


@patch('utils.notify.httpx.Client')
def test_send_pushplus(mock_client_class, pushplus_kit):
	mock_client_instance = MagicMock()
	mock_client_class.return_value.__enter__.return_value = mock_client_instance

	pushplus_kit.send_pushplus('测试标题', '测试内容')

	mock_client_instance.post.assert_called_once()
	call_kwargs = mock_client_instance.post.call_args
	assert 'test_token' in str(call_kwargs)


@patch('utils.notify.httpx.Client')
def test_send_dingtalk(mock_client_class, dingtalk_kit):
	mock_client_instance = MagicMock()
	mock_client_class.return_value.__enter__.return_value = mock_client_instance

	dingtalk_kit.send_dingtalk('测试标题', '测试内容')

	mock_client_instance.post.assert_called_once()
	call_args = mock_client_instance.post.call_args
	assert call_args[0][0] == 'https://oapi.dingtalk.com/robot/send?access_token=test'
	assert call_args[1]['json'] == {'msgtype': 'text', 'text': {'content': '测试标题\n测试内容'}}


@patch('utils.notify.httpx.Client')
def test_send_feishu(mock_client_class, feishu_kit):
	mock_client_instance = MagicMock()
	mock_client_class.return_value.__enter__.return_value = mock_client_instance

	feishu_kit.send_feishu('测试标题', '测试内容')

	mock_client_instance.post.assert_called_once()
	call_kwargs = mock_client_instance.post.call_args[1]
	assert 'card' in call_kwargs['json']


@patch('utils.notify.httpx.Client')
def test_send_wecom(mock_client_class, wecom_kit):
	mock_client_instance = MagicMock()
	mock_client_class.return_value.__enter__.return_value = mock_client_instance

	wecom_kit.send_wecom('测试标题', '测试内容')

	mock_client_instance.post.assert_called_once_with(
		'http://weixin.example.com', json={'msgtype': 'text', 'text': {'content': '测试标题\n测试内容'}}
	)


@patch('utils.notify.httpx.Client')
def test_send_gotify(mock_client_class, gotify_kit):
	mock_client_instance = MagicMock()
	mock_client_class.return_value.__enter__.return_value = mock_client_instance

	gotify_kit.send_gotify('测试标题', '测试内容')

	expected_url = 'https://gotify.example.com/message?token=test_token'
	expected_data = {'title': '测试标题', 'message': '测试内容', 'priority': 9}

	mock_client_instance.post.assert_called_once_with(expected_url, json=expected_data)


def test_missing_config(monkeypatch):
	monkeypatch.delenv('EMAIL_USER', raising=False)
	monkeypatch.delenv('EMAIL_PASS', raising=False)
	monkeypatch.delenv('EMAIL_TO', raising=False)
	monkeypatch.delenv('PUSHPLUS_TOKEN', raising=False)
	kit = NotificationKit()

	with pytest.raises(ValueError, match='Email configuration not set'):
		kit.send_email('测试', '测试')

	with pytest.raises(ValueError, match='PushPlus Token not configured'):
		kit.send_pushplus('测试', '测试')


@patch('utils.notify.NotificationKit.send_email')
@patch('utils.notify.NotificationKit.send_dingtalk')
@patch('utils.notify.NotificationKit.send_wecom')
@patch('utils.notify.NotificationKit.send_pushplus')
@patch('utils.notify.NotificationKit.send_feishu')
@patch('utils.notify.NotificationKit.send_gotify')
def test_push_message(mock_gotify, mock_feishu, mock_pushplus, mock_wecom, mock_dingtalk, mock_email, notification_kit):
	notification_kit.push_message('测试标题', '测试内容')

	assert mock_email.called
	assert mock_dingtalk.called
	assert mock_wecom.called
	assert mock_pushplus.called
	assert mock_feishu.called
	assert mock_gotify.called
