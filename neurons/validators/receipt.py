from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, UniqueConstraint, select
from datetime import datetime, timedelta
from loguru import logger
import bittensor
from typing import Any, List, Dict
from base_db_manager import BaseDBManager, Receipts


class ReceiptManager(BaseDBManager):
    def __init__(self, db_url='sqlite:///./miners.db'):
        super().__init__(db_url)

    def get_prompt_history(self, start_time: datetime, end_time: datetime, miner_hotkey: str = None) -> Dict[str, Any]:
        with self.Session() as session:
            try:
                query = select(Receipts).where(
                    Receipts.timestamp >= start_time,
                    Receipts.timestamp <= end_time
                )
                if miner_hotkey:
                    query = query.where(Receipts.miner_hotkey == miner_hotkey)

                result = session.execute(query)
                receipts = result.scalars().all()
                return {
                    'prompts_count': len(receipts),
                    'completion_tokens': sum(res.completion_tokens for res in receipts),
                    'prompt_tokens': sum(res.prompt_tokens for res in receipts),
                    'total_tokens': sum(res.total_tokens for res in receipts)
                }
            except Exception as e:
                logger.error(f'Error occurred while getting prompt history: {{"exception_type": {e.__class__.__name__}, "exception_message": {str(e)}, "exception_args": {e.args}}}')
                return {}

    def get_prompt_history_for_miner(self, miner_hotkey: str) -> Dict[str, Dict[str, Any]]:
        current_time = datetime.utcnow()
        daily_result = self.get_prompt_history(current_time - timedelta(days=1), current_time, miner_hotkey)
        weekly_result = self.get_prompt_history(current_time - timedelta(days=7), current_time, miner_hotkey)
        monthly_result = self.get_prompt_history(current_time - timedelta(days=30), current_time, miner_hotkey)
        return {
            'daily': daily_result,
            'weekly': weekly_result,
            'monthly': monthly_result
        }

    def get_prompt_history_for_all_miners(self, metagraph) -> Dict[str, Dict[str, Dict[str, Any]]]:
        result = {}
        for miner_hotkey in metagraph.hotkeys:
            result[miner_hotkey] = self.get_prompt_history_for_miner(miner_hotkey)
        return result
