import traceback
from contextlib import contextmanager
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Boolean, inspect, \
    MetaData, text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, relationship, selectinload, subqueryload, joinedload
from datetime import datetime, timedelta
from neurons import logger

Base = declarative_base()

class Miners(Base):
    __tablename__ = 'miners'
    id = Column(Integer, primary_key=True)
    hotkey = Column(String, nullable=False)
    uid = Column(Integer, nullable=False)
    uptime_start = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('hotkey', name='hotkey_uc'),)
    downtimes = relationship('Downtimes', back_populates='miner', order_by="desc(Downtimes.start_time)")

class Downtimes(Base):
    __tablename__ = 'downtimes'
    id = Column(Integer, primary_key=True)
    miner_id = Column(Integer, ForeignKey('miners.id'))
    start_time = Column(DateTime)
    end_time = Column(DateTime, nullable=True)
    miner = relationship('Miners', back_populates='downtimes')

class MinerUptimeManager:
    def __init__(self, db_url='sqlite:///miners.db'):
        self.engine = create_engine(db_url)

        if not self.compare_schemas(self.engine):
            with self.engine.connect() as conn:
                inspector = inspect(self.engine)
                table_names = inspector.get_table_names()
                for table_name in table_names:
                    try:
                        conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
                        conn.commit()
                    except ProgrammingError as e:
                        logger.error(f"Failed to drop table {table_name}: {e}")

        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)
        self.immunity_period = 8000 * 12

    def compare_schemas(self, engine):
        # Reflect the database schema
        metadata = MetaData()
        metadata.reflect(bind=engine)

        existing_tables = set(metadata.tables.keys())
        model_tables = set(Base.metadata.tables.keys())

        # Compare table names
        if existing_tables != model_tables:
            return False

        inspector = inspect(engine)

        for table_name in existing_tables.intersection(model_tables):
            existing_columns = set(c['name'] for c in inspector.get_columns(table_name))
            model_columns = set(c.name for c in Base.metadata.tables[table_name].columns)

            # Compare columns
            if existing_columns != model_columns:
                return False

            # Add more detailed comparison logic if needed
            existing_constraints = {c['name']: c for c in inspector.get_unique_constraints(table_name)}
            model_constraints = {c.name: c for c in Base.metadata.tables[table_name].constraints if isinstance(c, UniqueConstraint)}

            if set(existing_constraints.keys()) != set(model_constraints.keys()):
                return False

            for name in existing_constraints.keys():
                if existing_constraints[name]['column_names'] != list(model_constraints[name].columns.keys()):
                    return False

        return True


    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

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
            logger.error("Error occurred during uptime calculation", miner_hotkey=miner.hotkey, error=traceback.format_exc())
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

