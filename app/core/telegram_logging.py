import logging
from telegram import Bot
from telegram.error import TelegramError
from telegram.request import HTTPXRequest
import asyncio
import json
from app.core.logging import LogCategory

class TelegramLogHandler(logging.Handler):
    def __init__(self, bot_token: str, chat_id: str):
        super().__init__()
        self.bot = Bot(token=bot_token, request=HTTPXRequest(connection_pool_size=300))
        self.chat_id = chat_id
        
    def emit(self, record: logging.LogRecord):
        if self._should_skip_log(record):
            return
            
        log_entry = self.format(record)
        
        extra_info = ""
        if hasattr(record, 'client_ip'):
            extra_info += f"\nIP: {record.client_ip}"
        
        if hasattr(record, 'query_params') and record.query_params:
            extra_info += f"\nQuery Params: {self._format_dict(record.query_params)}"
            
        if hasattr(record, 'request_body') and record.request_body:
            extra_info += f"\nRequest Body: {self._format_dict(record.request_body)}"
            
        if extra_info:
            log_entry += extra_info

        try:
            loop = asyncio.get_running_loop()
            asyncio.create_task(self._send_log_to_telegram(log_entry))
        except RuntimeError:
            asyncio.run(self._send_log_to_telegram(log_entry))
    
    def _should_skip_log(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.ERROR:
            return False
        
        skip_markers = [LogCategory.DB, LogCategory.DEBUG]
        if hasattr(record, "msg") and isinstance(record.msg, str):
            if "request started:" in record.msg.lower():
                # Проверяем, что это POST запрос
                if "POST" in record.msg:
                    return False
                else:
                    return True
            if "request completed:" in record.msg.lower():
                return True
                
            for category in LogCategory:
                marker = f"[{category.value}]"
                if marker in record.msg:
                    return category.value in [sm.value for sm in skip_markers]

        return True
    
    def _format_dict(self, data: dict) -> str:
        try:
            json_str = json.dumps(data, ensure_ascii=False)
            if len(json_str) > 500:
                return json_str[:500] + "..."
            return json_str
        except:
            return str(data)

    async def _send_log_to_telegram(self, log_entry: str):
        try:
            if len(log_entry) > 4000:
                log_entry = log_entry[:3997] + "..."
            await self.bot.send_message(chat_id=self.chat_id, text=log_entry)
        except TelegramError as e:
            print(f"Не удалось отправить лог в Telegram: {e}")