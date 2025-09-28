#!/usr/bin/env python3
"""
Edge cases testing for config.py
"""

import tempfile
import os
from dataclasses import dataclass

from config import (
    BaseConfig,
    global_param,
    local_param,
    nested_param,
)


@dataclass
class DeepNestedConfig(BaseConfig):
    """Deep nested configuration"""
    value: str = local_param(required=False, default="deep")


@dataclass
class NestedConfig(BaseConfig):
    """Nested configuration"""
    name: str = local_param(required=False, default="nested")
    deep: DeepNestedConfig = nested_param(DeepNestedConfig, required=False, default=None)


@dataclass
class MainConfig(BaseConfig):
    """Main configuration"""
    app_name: str = global_param(required=True, default="TestApp")
    nested: NestedConfig = nested_param(NestedConfig, required=False, default=None)


def test_deep_nesting():
    """Test deep nesting a.b.c.d"""
    print("=== Testing Deep Nesting ===")

    toml_content = """
[global]
app_name = "DeepApp"

[main]
[main.nested]
name = "level2"

[main.nested.deep]
value = "level3"
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write(toml_content)
        temp_path = f.name

    try:
        config = MainConfig.from_toml(temp_path, module_section="main")
        print(f"Loaded config: {config}")

        # 验证嵌套结构
        assert config.nested is not None
        assert config.nested.name == "level2"
        assert config.nested.deep is not None
        assert config.nested.deep.value == "level3"

        print("✓ Deep nesting works")

    except Exception as e:
        print(f"✗ Deep nesting failed: {e}")
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_empty_config():
    """Test configuration with all optional fields"""
    print("\n=== Testing Empty Config ===")

    toml_content = """
[global]
app_name = "EmptyApp"

[main]
# All nested configs are optional
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write(toml_content)
        temp_path = f.name

    try:
        config = MainConfig.from_toml(temp_path, module_section="main")
        print(f"Empty config: {config}")

        assert config.app_name == "EmptyApp"
        assert config.nested is None

        print("✓ Empty config works")

    except Exception as e:
        print(f"✗ Empty config failed: {e}")
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_malformed_toml():
    """Test malformed TOML file"""
    print("\n=== Testing Malformed TOML ===")

    toml_content = """
[global]
app_name = "BadApp
# Missing closing quote - invalid TOML
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write(toml_content)
        temp_path = f.name

    try:
        config = MainConfig.from_toml(temp_path, module_section="main")
        print("✗ Should have failed with malformed TOML")

    except ValueError as e:
        print(f"✓ Correctly caught TOML error: {e}")
    except Exception as e:
        print(f"✓ Caught error (different type): {e}")
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_missing_file():
    """Test missing TOML file"""
    print("\n=== Testing Missing File ===")

    try:
        config = MainConfig.from_toml("/nonexistent/file.toml", module_section="main")
        print("✗ Should have failed with missing file")

    except Exception as e:
        print(f"✓ Correctly caught file error: {e}")


def test_type_mismatch():
    """Test type mismatches in TOML"""
    print("\n=== Testing Type Mismatch ===")

    # Try to put array where string expected
    toml_content = """
[global]
app_name = ["not", "a", "string"]

[main]
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write(toml_content)
        temp_path = f.name

    try:
        config = MainConfig.from_toml(temp_path, module_section="main")
        print(f"Config with type mismatch: {config}")
        print("Note: Python is dynamically typed, so this might work")

    except Exception as e:
        print(f"✓ Caught type mismatch error: {e}")
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


if __name__ == "__main__":
    print("Running Edge Case Tests...")

    test_deep_nesting()
    test_empty_config()
    test_malformed_toml()
    test_missing_file()
    test_type_mismatch()

    print("\n=== Edge Case Tests Completed ===")