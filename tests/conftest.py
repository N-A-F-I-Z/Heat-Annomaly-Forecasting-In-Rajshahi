import pytest

from heatcast.config import load_config
from heatcast.data import make_synthetic


@pytest.fixture(scope="session")
def cfg():
    c = load_config()
    c["hindcast"]["test_start"], c["hindcast"]["test_end"] = 2021, 2022
    return c


@pytest.fixture(scope="session")
def series():
    df = make_synthetic("1991-01-01", "2022-12-31", seed=1)
    s = df.set_index(df.date.astype("datetime64[ns]"))["tmax_c"]
    s.index.name = None
    return s
