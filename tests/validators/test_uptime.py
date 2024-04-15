import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from neurons.validators.uptime import DowntimeLog, Base, MinerUptimeManager, MinerUptime


class TestMinerUptimeManager(unittest.TestCase):
    def setUp(self):
        # Use an in-memory SQLite database for testing
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(self.session_factory)
        self.uptime_manager = MinerUptimeManager('sqlite:///:memory:')
        self.uptime_manager.Session = self.Session
        self.session = self.Session()

    def tearDown(self):
        self.session.rollback()
        self.session.close()
        self.Session.remove()
        self.engine.dispose()

    def test_get_miner(self):
        miner = MinerUptime(uid=123, hotkey='key123')
        self.session.add(miner)
        self.session.commit()

        retrieved_miner = self.uptime_manager.get_miner(123, 'key123')
        self.assertIsNotNone(retrieved_miner)
        self.assertEqual(retrieved_miner.uid, 123)
        self.assertEqual(retrieved_miner.hotkey, 'key123')

    def test_try_update_miner(self):
        self.uptime_manager.try_update_miner(123, 'key123')
        miner = self.session.query(MinerUptime).first()
        self.assertEqual(miner.uid, 123)
        self.assertEqual(miner.hotkey, 'key123')

        self.uptime_manager.try_update_miner(123, 'key124')
        updated_miner = self.session.query(MinerUptime).filter_by(uid=123).first()
        self.assertTrue(updated_miner.is_deregistered)
        self.assertIsNotNone(updated_miner.deregistered_date)

    def test_up_down_sequence(self):
        self.uptime_manager.try_update_miner(123, 'key123')
        success_up = self.uptime_manager.up(123, 'key123')
        self.assertTrue(success_up)

        success_down = self.uptime_manager.down(123, 'key123')
        self.assertTrue(success_down)

        retrieved_miner = self.uptime_manager.get_miner(123, 'key123')
        self.assertEqual(len(retrieved_miner.downtimes), 1)


class TestUptimeCalculation(unittest.TestCase):
    def setUp(self):
        self.miner = MinerUptime(uid=123, hotkey='key123', uptime_start=datetime.utcnow() - timedelta(days=400))  # Starting well before any test period
        self.miner.downtimes = []
        self.manager = MinerUptimeManager()  # Assuming this manager has the calculate_proportional_uptime method

    def test_variable_period_and_downtime(self):
        periods = {
            'day': 86400,
            'week': 604800,
            'month': 2592000,
            'quarter': 7889400,
            'year': 31536000
        }
        # Header for the results table
        print(f"{'Period':<10} | {'Downtime/Day':<15} | {'Uptime Ratio':<15}")
        print('-' * 42)

        # Iterate over each period
        for period_name, period_seconds in periods.items():
            for num_downtimes in range(1, 7):  # From 1 to 6 downtimes per day
                # Clear previous downtimes
                self.miner.downtimes = []
                downtime_duration = timedelta(minutes=15 * num_downtimes)
                total_downtime_minutes = 15 * num_downtimes

                # Add downtimes for each day within the period
                num_days = period_seconds // 86400
                for day in range(num_days):
                    start_time = datetime.utcnow() - timedelta(days=num_days - day, hours=24 - num_downtimes)
                    end_time = start_time + downtime_duration
                    self.miner.downtimes.append(DowntimeLog(start_time=start_time, end_time=end_time))

                # Calculate uptime
                result = self.manager.calculate_proportional_uptime(self.miner, period_seconds)
                # Print the result in table format
                print(f"{period_name.capitalize():<10} | {total_downtime_minutes:<15} | {result:<15.4f}")


    def test_day_without_downtime(self):
        # One day without any downtimes
        result = self.manager.calculate_proportional_uptime(self.miner, 86400)  # 24 hours in seconds
        self.assertEqual(result, 1.0, "Expected full uptime for one day without downtimes.")

    def test_day_with_three_downtimes(self):
        # One day with three 1-hour downtimes
        for i in range(3):
            start_time = datetime.utcnow() - timedelta(hours=(24 - (i * 3 + 1)))
            end_time = start_time + timedelta(hours=1)
            self.miner.downtimes.append(DowntimeLog(start_time=start_time, end_time=end_time))
        result = self.manager.calculate_proportional_uptime(self.miner, 86400)
        print(result)
        #self.assertAlmostEqual(result, (21 / 24), msg="Expected uptime calculation with three 1-hour downtimes within one day.")

    def test_week_with_daily_downtimes(self):
        # One week, each day with 3 hours of downtime
        for day in range(7):
            for hour in range(3):
                start_time = self.current_time - timedelta(days=(7 - day), hours=(24 - hour))
                end_time = start_time + timedelta(hours=1)
                self.miner.downtimes.append(DowntimeLog(start_time=start_time, end_time=end_time))
        result = self.manager.calculate_proportional_uptime(self.miner, 604800)  # One week in seconds

        print(result)
        #self.assertAlmostEqual(result, expected, msg="Expected uptime calculation for a week with each day having 3 hours of downtime.")

    def test_month_with_daily_downtime(self):
        # One month, each day with 1 hour of downtime
        for day in range(30):
            start_time = datetime.utcnow() - timedelta(days=(30 - day), hours=23)
            end_time = start_time + timedelta(minutes=45)
            self.miner.downtimes.append(DowntimeLog(start_time=start_time, end_time=end_time))
        result = self.manager.calculate_proportional_uptime(self.miner, 2592000)  # 30 days in seconds
        print(result)
        self.assertAlmostEqual(result, 0.09375)

    def test_quarter_and_year_with_daily_downtime(self):
        # A quarter and a year with daily 1-hour downtimes
        for day in range(365):
            start_time = datetime.utcnow() - timedelta(days=(365 - day), hours=23)
            end_time = start_time + timedelta(hours=1)
            self.miner.downtimes.append(DowntimeLog(start_time=start_time, end_time=end_time))
        quarter_result = self.manager.calculate_proportional_uptime(self.miner, 7889400)  # Approximately three months in seconds
        year_result = self.manager.calculate_proportional_uptime(self.miner, 31536000)  # One year in seconds

        print(quarter_result)
        print(year_result)

        #self.assertAlmostEqual(quarter_result, (23 * 90 / (24 * 90)), msg="Expected uptime calculation for a quarter.")
        #self.assertAlmostEqual(year_result, (23 * 365 / (24 * 365)), msg="Expected uptime calculation for a year.")


if __name__ == '__main__':
    unittest.main()