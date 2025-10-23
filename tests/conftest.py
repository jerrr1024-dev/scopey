"""
Shared pytest fixtures for scopey tests
"""

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Generator
import sys

# Ensure local source tree has priority over any installed distribution.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from scopey.config import (
    BaseConfig,
    global_first_param,
    global_param,
    local_first_param,
    local_param,
    nested_param,
)


@dataclass
class SimpleConfig(BaseConfig):
    """Simple configuration for testing"""

    name: str = local_param(required=True, default="test")
    count: int = local_param(required=False, default=0)


@dataclass
class DatabaseConfig(BaseConfig):
    """Database configuration for testing"""

    host: str = local_param(required=True, default="localhost")
    port: int = local_param(required=False, default=5432)
    username: str = global_param(required=False, default=None)
    password: str = global_param(required=False, default=None)


@dataclass
class CacheConfig(BaseConfig):
    """Cache configuration for testing"""

    ttl: int = local_param(required=False, default=3600)
    max_size: int = global_param(required=False, default=1000)


@dataclass
class AppConfig(BaseConfig):
    """Application configuration with nested configs"""

    app_name: str = global_param(required=True, default="TestApp")
    debug: bool = local_param(required=False, default=False)
    max_workers: int = global_first_param(required=False, default=4)
    timeout: int = local_first_param(required=False, default=30)
    database: DatabaseConfig = nested_param(
        DatabaseConfig, required=False, default=None
    )
    cache: CacheConfig = nested_param(CacheConfig, required=False, default=None)


@pytest.fixture
def temp_toml_file() -> Generator[Path, None, None]:
    """Create a temporary TOML file for testing"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture
def simple_config() -> SimpleConfig:
    """Provide a simple config instance"""
    return SimpleConfig(name="test_app", count=5)


@pytest.fixture
def database_config() -> DatabaseConfig:
    """Provide a database config instance"""
    return DatabaseConfig(host="db.example.com", port=3306, username="admin")


@pytest.fixture
def app_config() -> AppConfig:
    """Provide an app config instance"""
    return AppConfig(app_name="MyApp", debug=True, max_workers=8)


@pytest.fixture
def basic_toml_content() -> str:
    """Provide basic TOML content for testing"""
    return """
[global]
app_name = "TestApp"

[app]
debug = true
max_workers = 8
"""


@pytest.fixture
def nested_toml_content() -> str:
    """Provide nested TOML content for testing"""
    return """
[global]
app_name = "NestedApp"
username = "admin"
password = "secret"
max_size = 2000

[app]
debug = false
max_workers = 16
timeout = 60

[app.database]
host = "db.example.com"
port = 3306

[app.cache]
ttl = 7200
"""
