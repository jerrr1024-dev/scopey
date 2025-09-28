#!/usr/bin/env python3
"""
Test script for config.py
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from config import (
    BaseConfig,
    global_first_param,
    global_param,
    local_first_param,
    local_param,
    nested_param,
)


@dataclass
class DatabaseConfig(BaseConfig):
    """Database configuration"""

    host: str = local_param(required=True, default="localhost")
    port: int = local_param(required=False, default=5432)
    username: str = global_param(required=False, default=None)
    password: str = global_param(required=False, default=None)
    timeout: int = local_param(required=False, default=30)


@dataclass
class LoggingConfig(BaseConfig):
    """Logging configuration"""

    level: str = local_param(required=False, default="INFO")
    file_path: str = local_param(required=False, default=None)
    max_size: int = global_param(required=False, default=10485760)  # 10MB


@dataclass
class AppConfig(BaseConfig):
    """Main application configuration"""

    app_name: str = global_param(required=True, default="TestApp")
    debug: bool = local_param(required=False, default=False)
    max_workers: int = global_first_param(required=False, default=4)
    database: DatabaseConfig = nested_param(
        DatabaseConfig, required=False, default=None
    )
    logging: LoggingConfig = nested_param(LoggingConfig, required=False, default=None)


def test_basic_config():
    """Test basic configuration creation"""
    print("=== Testing Basic Configuration ===")

    config = AppConfig()
    print(f"Default config created: {config}")

    # Test to_dict
    config_dict = config.to_dict()
    print(f"Config dict: {config_dict}")

    # Test to_dict with include_none=False
    config_dict_no_none = config.to_dict(include_none=False)
    print(f"Config dict (no None): {config_dict_no_none}")

    # Test to_dict with include_global_section=False
    config_dict_no_global = config.to_dict(include_global_section=False)
    print(f"Config dict (no global section): {config_dict_no_global}")


def test_nested_config_none():
    """Test nested configuration when field is None"""
    print("\n=== Testing Nested Config (None) ===")

    config = AppConfig()
    config_dict = config.to_dict()

    # Debug: print all keys
    print(f"All keys in config_dict: {list(config_dict.keys())}")

    # Check that nested sections are created even when None
    assert "app.database" in config_dict, "Database nested section should be created"
    assert "app.logging" in config_dict, "Logging nested section should be created"

    print("✓ Nested sections created for None values")
    print(f"Database section: {config_dict.get('app.database', {})}")
    print(f"Logging section: {config_dict.get('app.logging', {})}")


def test_toml_roundtrip():
    """Test TOML save/load roundtrip"""
    print("\n=== Testing TOML Roundtrip ===")

    # Create config with some values
    config = AppConfig(app_name="MyTestApp", debug=True, max_workers=8)

    # Create temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        temp_path = f.name

    try:
        # Save to TOML
        config.to_toml(temp_path)
        print(f"Config saved to: {temp_path}")

        # Read file content
        with open(temp_path, "r") as f:
            toml_content = f.read()
        print("TOML content:")
        print(toml_content)

        # Load from TOML
        loaded_config = AppConfig.from_toml(temp_path, module_section="app")
        print(f"Loaded config: {loaded_config}")

        # Verify values
        assert loaded_config.app_name == "MyTestApp"
        assert loaded_config.debug == True
        assert loaded_config.max_workers == 8

        print("✓ TOML roundtrip successful")

    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_complex_toml():
    """Test complex TOML with nested configurations"""
    print("\n=== Testing Complex TOML ===")

    # Create TOML content
    toml_content = """
[global]
app_name = "ComplexApp"
username = "admin"
password = "secret123"
max_size = 20971520

[appconfig]
debug = true
max_workers = 16

[appconfig.database]
host = "db.example.com"
port = 3306
timeout = 60

[appconfig.logging]
level = "DEBUG"
file_path = "/var/log/app.log"
"""

    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        temp_path = f.name

    try:
        # Load from TOML
        config = AppConfig.from_toml(temp_path, module_section="appconfig")
        print(f"Loaded complex config: {config}")

        # Test global parameters
        assert config.app_name == "ComplexApp"

        # Test local parameters
        assert config.debug == True
        assert config.max_workers == 16

        # Test nested configurations
        assert config.database is not None
        assert config.database.host == "db.example.com"
        assert config.database.port == 3306
        assert config.database.username == "admin"  # from global
        assert config.database.password == "secret123"  # from global

        assert config.logging is not None
        assert config.logging.level == "DEBUG"
        assert config.logging.file_path == "/var/log/app.log"
        assert config.logging.max_size == 20971520  # from global

        print("✓ Complex TOML loading successful")

        # Test to_dict output
        result_dict = config.to_dict()
        print("Generated dict structure:")
        for key, value in result_dict.items():
            print(f"  {key}: {value}")

    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_global_first_local_first():
    """Test GLOBAL_FIRST and LOCAL_FIRST parameter resolution"""
    print("\n=== Testing GLOBAL_FIRST/LOCAL_FIRST ===")

    # Create TOML with both global and local values
    toml_content = """
[global]
app_name = "TestApp"
max_workers = 10

[appconfig]
max_workers = 20
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(toml_content)
        temp_path = f.name

    try:
        config = AppConfig.from_toml(temp_path, module_section="appconfig")

        # max_workers is global_first_param, so should use global value
        assert config.max_workers == 10, f"Expected 10, got {config.max_workers}"
        print("✓ GLOBAL_FIRST parameter resolution works")

    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_error_handling():
    """Test error handling"""
    print("\n=== Testing Error Handling ===")

    try:
        # Test missing required parameter
        toml_content = """
[appconfig]
debug = true
# Missing required app_name
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write(toml_content)
            temp_path = f.name

        try:
            config = AppConfig.from_toml(temp_path, module_section="appconfig")
            assert False, "Should have raised error for missing required parameter"
        except ValueError as e:
            print(f"✓ Caught expected error: {e}")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except Exception as e:
        print(f"Unexpected error: {e}")


if __name__ == "__main__":
    print("Running Config Tests...")

    # dataclass import moved to top

    test_basic_config()
    test_nested_config_none()
    test_toml_roundtrip()
    test_complex_toml()
    test_global_first_local_first()
    test_error_handling()

    print("\n=== All Tests Completed ===")
