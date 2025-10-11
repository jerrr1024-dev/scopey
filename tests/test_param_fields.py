"""
Unit tests for parameter field functions
"""

from dataclasses import fields

import pytest

from scopey.config import (
    ParamScope,
    global_first_param,
    global_param,
    local_first_param,
    local_param,
    nested_param,
    param_field,
)


@pytest.mark.unit
class TestParamField:
    """Test the base param_field function"""

    def test_param_field_creates_field_with_metadata(self):
        """Test that param_field creates a field with proper metadata"""
        field = param_field(ParamScope.GLOBAL, required=True, default="test")

        assert field.metadata["param_scope"] == ParamScope.GLOBAL
        assert field.metadata["required"] is True
        assert field.default_factory() == "test"

    def test_param_field_deepcopy_default(self):
        """Test that param_field deep copies default values"""
        default_list = [1, 2, 3]
        field = param_field(ParamScope.LOCAL, required=False, default=default_list)

        # Get value from factory
        value1 = field.default_factory()
        value2 = field.default_factory()

        # Should be equal but not the same object
        assert value1 == value2
        assert value1 is not value2

        # Modifying one should not affect the other
        value1.append(4)
        assert len(value1) == 4
        assert len(value2) == 3


@pytest.mark.unit
class TestGlobalParam:
    """Test global_param function"""

    def test_global_param_default_required(self):
        """Test that global_param is required by default"""
        field = global_param()

        assert field.metadata["param_scope"] == ParamScope.GLOBAL
        assert field.metadata["required"] is True
        assert field.default_factory() is None

    def test_global_param_with_default(self):
        """Test global_param with custom default"""
        field = global_param(required=False, default="default_value")

        assert field.metadata["param_scope"] == ParamScope.GLOBAL
        assert field.metadata["required"] is False
        assert field.default_factory() == "default_value"


@pytest.mark.unit
class TestLocalParam:
    """Test local_param function"""

    def test_local_param_default_required(self):
        """Test that local_param is required by default"""
        field = local_param()

        assert field.metadata["param_scope"] == ParamScope.LOCAL
        assert field.metadata["required"] is True
        assert field.default_factory() is None

    def test_local_param_with_default(self):
        """Test local_param with custom default"""
        field = local_param(required=False, default=42)

        assert field.metadata["param_scope"] == ParamScope.LOCAL
        assert field.metadata["required"] is False
        assert field.default_factory() == 42


@pytest.mark.unit
class TestGlobalFirstParam:
    """Test global_first_param function"""

    def test_global_first_param_scope(self):
        """Test that global_first_param has correct scope"""
        field = global_first_param()

        assert field.metadata["param_scope"] == ParamScope.GLOBAL_FIRST
        assert field.metadata["required"] is True

    def test_global_first_param_optional(self):
        """Test global_first_param with optional flag"""
        field = global_first_param(required=False, default=10)

        assert field.metadata["required"] is False
        assert field.default_factory() == 10


@pytest.mark.unit
class TestLocalFirstParam:
    """Test local_first_param function"""

    def test_local_first_param_scope(self):
        """Test that local_first_param has correct scope"""
        field = local_first_param()

        assert field.metadata["param_scope"] == ParamScope.LOCAL_FIRST
        assert field.metadata["required"] is True

    def test_local_first_param_optional(self):
        """Test local_first_param with optional flag"""
        field = local_first_param(required=False, default=20)

        assert field.metadata["required"] is False
        assert field.default_factory() == 20


@pytest.mark.unit
class TestNestedParam:
    """Test nested_param function"""

    def test_nested_param_with_class(self):
        """Test nested_param with nested class"""
        from conftest import SimpleConfig

        field = nested_param(SimpleConfig, required=True, default=None)

        assert field.metadata["param_scope"] == ParamScope.NESTED
        assert field.metadata["required"] is True
        assert field.metadata["nested_class"] == SimpleConfig
        assert field.default_factory() is None

    def test_nested_param_optional(self):
        """Test nested_param with optional flag"""
        from conftest import DatabaseConfig

        field = nested_param(DatabaseConfig, required=False, default=None)

        assert field.metadata["required"] is False
        assert field.metadata["nested_class"] == DatabaseConfig

    def test_nested_param_deepcopy_default(self):
        """Test that nested_param deep copies default instances"""
        from conftest import SimpleConfig

        default_instance = SimpleConfig(name="default", count=1)
        field = nested_param(SimpleConfig, required=False, default=default_instance)

        value1 = field.default_factory()
        value2 = field.default_factory()

        # Should be equal but not the same object
        assert value1.name == value2.name
        assert value1 is not value2


@pytest.mark.unit
class TestParamScope:
    """Test ParamScope enum"""

    def test_param_scope_values(self):
        """Test that all expected ParamScope values exist"""
        assert hasattr(ParamScope, "GLOBAL")
        assert hasattr(ParamScope, "LOCAL")
        assert hasattr(ParamScope, "NESTED")
        assert hasattr(ParamScope, "GLOBAL_FIRST")
        assert hasattr(ParamScope, "LOCAL_FIRST")

    def test_param_scope_uniqueness(self):
        """Test that ParamScope values are unique"""
        scopes = [
            ParamScope.GLOBAL,
            ParamScope.LOCAL,
            ParamScope.NESTED,
            ParamScope.GLOBAL_FIRST,
            ParamScope.LOCAL_FIRST,
        ]

        assert len(scopes) == len(set(scopes))
