from datetime import date

import pytest

from radar.config import Settings
from radar.db import Database
from radar.models import Watch


@pytest.fixture
def settings(tmp_path):
    return Settings(db_path=str(tmp_path / "radar.db"), providers=["demo"], request_delay=0.0)


@pytest.fixture
def db(settings):
    database = Database(settings.db_path)
    yield database
    database.close()


@pytest.fixture
def watch():
    return Watch(
        name="Teste",
        origins=["GRU"],
        destinations=["LIS"],
        start_date=date(2027, 3, 1),
        end_date=date(2027, 3, 20),
        min_nights=7,
        max_nights=10,
        explore_days=10,
    )
