#!/usr/bin/env python3
"""
More edge cases testing for config.py
"""

import tempfile
import os
from dataclasses import dataclass

from config import (
    BaseConfig,
    global_param,
    local_param,
    nested_param,
    global_first_param,
    local_first_param,
)


@dataclass
class CircularA(BaseConfig):
    """For testing circular references"""
    name: str = local_param(required=False, default="A")
    # circular_b: CircularB = nested_param(CircularB, required=False, default=None)


@dataclass
class CircularB(BaseConfig):
    """For testing circular references"""
    name: str = local_param(required=False, default="B")
    circular_a: CircularA = nested_param(CircularA, required=False, default=None)


@dataclass
class ConflictConfig(BaseConfig):
    """For testing parameter conflicts"""
    app_name: str = global_param(required=True, default="TestApp")

    # Same parameter name with different scopes - should cause issues
    debug: bool = local_param(required=False, default=False)
    debug_global: bool = global_param(required=False, default=True)


def test_section_case_sensitivity():
    """Test case sensitivity in section names"""
    print("=== Testing Case Sensitivity ===")

    toml_content = """
[global]
app_name = "CaseApp"

[MAIN]
debug = true

[main]
other_field = "value"
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write(toml_content)
        temp_path = f.name

    try:
        # Try with lowercase - should find [main] but not [MAIN]
        from config import BaseConfig, local_param, global_param

        @dataclass
        class CaseTestConfig(BaseConfig):
            app_name: str = global_param(required=True)
            debug: bool = local_param(required=False, default=False)
            other_field: str = local_param(required=False, default="default")

        config = CaseTestConfig.from_toml(temp_path, module_section="main")
        print(f"Case test result: {config}")
        print("✓ Case sensitivity test completed")

    except Exception as e:
        print(f"Case sensitivity test result: {e}")
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_merge_functionality():
    """Test the merge functionality"""
    print("\n=== Testing Merge Functionality ===")

    try:
        from config import BaseConfig, global_param, local_param

        @dataclass
        class ConfigA(BaseConfig):
            name_a: str = global_param(required=False, default="A")
            value_a: int = local_param(required=False, default=1)

        @dataclass
        class ConfigB(BaseConfig):
            name_b: str = global_param(required=False, default="B")
            value_b: int = local_param(required=False, default=2)

        config_a = ConfigA()
        config_b = ConfigB()

        # Test merge
        merged = BaseConfig.merge([config_a, config_b], "MergedTestConfig")
        print(f"Merged config: {merged}")

        # Should have fields: a, b (after removing "config" from class names)
        assert hasattr(merged, 'a')
        assert hasattr(merged, 'b')
        print("✓ Merge functionality works")

    except Exception as e:
        print(f"✗ Merge functionality failed: {e}")


def test_parameter_priority_conflicts():
    """Test parameter priority with conflicts"""
    print("\n=== Testing Parameter Priority Conflicts ===")

    toml_content = """
[global]
app_name = "PriorityApp"
priority_param = "global_value"

[main]
priority_param = "local_value"
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
        f.write(toml_content)
        temp_path = f.name

    try:
        @dataclass
        class PriorityConfig(BaseConfig):
            app_name: str = global_param(required=True)
            priority_param: str = global_first_param(required=False, default="default")

        config = PriorityConfig.from_toml(temp_path, module_section="main")
        print(f"Priority config: {config}")

        # Should use global value due to global_first_param
        assert config.priority_param == "global_value"
        print("✓ Parameter priority works correctly")

    except Exception as e:
        print(f"✗ Parameter priority test failed: {e}")
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def test_roundtrip_with_nested():
    """Test complete roundtrip with nested configurations"""
    print("\n=== Testing Roundtrip with Nested ===")

    try:
        @dataclass
        class NestedRoundtrip(BaseConfig):
            nested_name: str = local_param(required=False, default="nested_default")
            nested_value: int = local_param(required=False, default=42)

        @dataclass
        class MainRoundtrip(BaseConfig):
            app_name: str = global_param(required=True, default="RoundtripApp")
            main_value: str = local_param(required=False, default="main_default")
            nested: NestedRoundtrip = nested_param(NestedRoundtrip, required=False, default=None)

        # Create original config
        original = MainRoundtrip(
            app_name="OriginalApp",
            main_value="original_main",
            nested=NestedRoundtrip(nested_name="original_nested", nested_value=123)
        )

        # Save to TOML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.toml', delete=False) as f:
            temp_path = f.name

        original.to_toml(temp_path, module_section="main")

        # Debug: read and print the TOML content
        with open(temp_path, 'r') as f:
            toml_content = f.read()
        print("Generated TOML:")
        print(toml_content)

        # Read back
        loaded = MainRoundtrip.from_toml(temp_path, module_section="main")

        print(f"Original: {original}")
        print(f"Loaded:   {loaded}")

        # Verify all values match
        assert loaded.app_name == original.app_name
        assert loaded.main_value == original.main_value
        assert loaded.nested is not None
        assert loaded.nested.nested_name == original.nested.nested_name
        assert loaded.nested.nested_value == original.nested.nested_value

        print("✓ Complete roundtrip with nested configs works")

    except Exception as e:
        print(f"✗ Roundtrip test failed: {e}")
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


if __name__ == "__main__":
    print("Running More Edge Case Tests...")

    test_section_case_sensitivity()
    test_merge_functionality()
    test_parameter_priority_conflicts()
    test_roundtrip_with_nested()

    print("\n=== More Edge Case Tests Completed ===")