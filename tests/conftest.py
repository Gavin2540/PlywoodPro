import os, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from database.db import DatabaseManager


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "data" / "test.db")
    DatabaseManager.initialize(path)
    yield path
    DatabaseManager.close()


@pytest.fixture
def demo_db(tmp_path):
    """A temp database filled with ~75 days of realistic demo data."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
    import seed_demo
    path = seed_demo.seed(str(tmp_path / "data" / "demo.db"))
    DatabaseManager.initialize(path)
    yield path
    DatabaseManager.close()


@pytest.fixture
def window(qtbot, demo_db):
    """The real main window over the demo database (offscreen)."""
    from ui import theme
    from ui.main_window import MainWindow
    theme.apply("dark")
    w = MainWindow(check_updates=False)
    qtbot.addWidget(w)
    w.show()
    return w


# Qt can crash while Python tears it down after an offscreen run, turning a
# fully passing run into a failing exit code. Leave with the real result instead.
_exit_status = {"code": None}


def pytest_sessionfinish(session, exitstatus):
    _exit_status["code"] = int(exitstatus)


def pytest_unconfigure(config):
    if _exit_status["code"] is not None:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(_exit_status["code"])
