import psycopg2
from sqlalchemy import create_engine, inspect, Column, Integer, DateTime, String, Float, ForeignKey, UniqueConstraint, MetaData, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session, relationship
from sqlalchemy.exc import OperationalError, ProgrammingError
from contextlib import contextmanager
from datetime import datetime
from loguru import logger

Base = declarative_base()

class Receipts(Base):
    __tablename__ = 'receipts'
    receiptid = Column(Integer, primary_key=True)
    validator_hotkey = Column(String, nullable=False)
    miner_hotkey = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    execution_time = Column(Float)
    prompt_hash = Column(String, nullable=False)
    prompt_preview = Column(String, nullable=False)
    completion_tokens = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)

class MinerBlacklist(Base):
    __tablename__ = 'miner_blacklist'
    miner_hotkey = Column(String, primary_key=True)
    uid = Column(Integer, nullable=False)
    reason = Column(String)

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

class BaseDBManager:
    def __init__(self, db_url='sqlite:///./miners.db'):
        self.db_url = db_url
        self.engine = create_engine(db_url, echo=True)
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)
        if "postgresql" in self.db_url:
            self.create_database_if_not_exists()
        self.initialize_database()

    def create_database_if_not_exists(self):
        db_url_parts = self.db_url.rsplit('/', 1)
        db_name = db_url_parts[-1]
        base_db_url = db_url_parts[0] + '/postgres'

        conn = psycopg2.connect(base_db_url)
        conn.autocommit = True
        cur = conn.cursor()
        try:
            cur.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{db_name}'")
            exists = cur.fetchone()
            if not exists:
                cur.execute(f"CREATE DATABASE {db_name}")
                logger.info(f"Database {db_name} created successfully.")
        except Exception as e:
            logger.error(f"Error checking/creating database: {e}")
            raise
        finally:
            cur.close()
            conn.close()

    def initialize_database(self):
        try:
            with self.engine.connect() as conn:
                inspector = inspect(conn)
                if not self.compare_schemas(self.engine):
                    with self.engine.connect() as conn:
                        inspector = inspect(self.engine)
                        table_names = inspector.get_table_names()
                        for table_name in table_names:
                            try:
                                if table_name in Base.metadata.tables:
                                    conn.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
                                    conn.commit()
                            except ProgrammingError as e:
                                logger.error(f"Failed to drop table {table_name}: {e}")

                Base.metadata.create_all(self.engine)
        except OperationalError as e:
            logger.error(f"Database connection error: {e}")
            raise
        
    def compare_schemas(self, engine):
        # Reflect the database schema
        metadata = MetaData()
        metadata.reflect(bind=engine)

        existing_tables = set(metadata.tables.keys())
        model_tables = set(Base.metadata.tables.keys())
        logger.info("compare_schemas start")
        # Compare table names
        if not model_tables <= existing_tables:  
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
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
