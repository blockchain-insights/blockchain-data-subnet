from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship, joinedload
from datetime import datetime, timedelta
import traceback
from loguru import logger
from neurons.validators.base_db_manager import BaseDBManager, Miners, Downtimes


class MinerUptimeManager(BaseDBManager):
    def __init__(self, db_url='sqlite:///miners.db'):
        super().__init__(db_url)
        self.immunity_period = 8000 * 12

    def up(self, uid, hotkey):
        try:
            with self.session_scope() as session:
                miner = session.query(Miners).filter(Miners.hotkey == hotkey).first()
                if not miner:
                    new_miner = Miners(uid=uid, hotkey=hotkey)
                    session.add(new_miner)
                elif miner:
                    if miner.uid != uid:
                        miner.uid = uid
                        miner.uptime_start = datetime.utcnow()
                    last_downtime = session.query(Downtimes).filter(Downtimes.miner_id == miner.id, Downtimes.end_time == None).first()
                    if last_downtime:
                        last_downtime.end_time = datetime.utcnow()
        except Exception as e:
            logger.error("Error occurred during uptime end", miner_hotkey=hotkey, error=traceback.format_exc())

    def down(self, uid, hotkey):
        try:
            with self.session_scope() as session:
                miner = session.query(Miners).filter(Miners.hotkey == hotkey).first()
                if not miner:
                    miner = Miners(uid=uid, hotkey=hotkey)
                    session.add(miner)
                if miner:
                    most_recent_downtime = session.query(Downtimes).filter(Downtimes.miner_id == miner.id).order_by(Downtimes.start_time.desc()).first()
                    if not most_recent_downtime or most_recent_downtime.end_time is not None:
                        new_downtime = Downtimes(miner_id=miner.id, start_time=datetime.utcnow(), end_time=None)
                        session.add(new_downtime)
        except Exception as e:
            logger.error("Error occurred during downtime start", miner_hotkey=hotkey, error=traceback.format_exc())

    def get_miner(self, hotkey):
        try:
            with self.session_scope() as session:
                miner = session.query(Miners).options(joinedload(Miners.downtimes)).filter(Miners.hotkey == hotkey).first()
                if miner:
                    session.expunge(miner)
                    return miner
                return None
        except Exception as e:
            logger.error("Error occurred during miner retrieval", miner_hotkey=hotkey, error=traceback.format_exc())
            return None

    def calculate_uptimes(self, hotkey, period_seconds):
        try:
            with self.session_scope() as session:
                query = session.query(Miners).options(joinedload(Miners.downtimes)).filter(Miners.hotkey == hotkey)
                miner = query.first()
                if miner is None:
                    return 0  # No miner found for the UID and hotkey provided

                active_period_end = datetime.utcnow()
                active_period_start = miner.uptime_start + timedelta(seconds=self.immunity_period)

                result = {}

                for period_second in period_seconds:
                    if active_period_start > active_period_end:
                        result[period_second] = 1
                        continue
                    
                    adjusted_start = max(active_period_start, datetime.utcnow() - timedelta(seconds=period_second))

                    active_seconds = (active_period_end - adjusted_start).total_seconds()
                    total_downtime = sum(
                        (log.end_time - log.start_time).total_seconds()
                        for log in miner.downtimes
                        if log.start_time >= adjusted_start and log.end_time and log.end_time <= active_period_end
                    )
                    actual_uptime_seconds = max(0, active_seconds - total_downtime)

                    result[period_second] = actual_uptime_seconds / period_second if active_seconds > 0 else 0
                return result

        except Exception as e:
            logger.error("Error occurred during uptime calculation", miner_hotkey=hotkey, error=traceback.format_exc())
            raise e

    def get_uptime_scores(self, metagraph, uid_value):
        day = 86400
        week = 604800
        month = 2629746
        miner_ip = metagraph.axons[uid_value].ip
        miner_port = metagraph.axons[uid_value].port
        miner_hotkey = metagraph.hotkeys[uid_value]
        miner_coldkey = metagraph.coldkeys[uid_value]
        result = self.calculate_uptimes(miner_hotkey, [day, week, month])
        average = (result[day] + result[week] + result[month]) / 3


        logger.debug('Uptime Scores', miner_uid=uid_value, miner_ip = miner_ip, miner_port = miner_port,  miner_hotkey = miner_hotkey, miner_coldkey =miner_coldkey, result = result)

        return {'daily': result[day], 'weekly': result[week], 'monthly': result[month], 'average': average}
