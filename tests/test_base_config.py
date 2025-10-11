"""
Unit tests for BaseConfig core methods
"""

from dataclasses import dataclass

import pytest

from scopey.config import BaseConfig, ParamScope, global_param, local_param


@pytest.mark.unit
class TestBaseConfigInit:
    """Test BaseConfig initialization"""

    def test_post_init_sets_raw_data(self, simple_config):
        """Test that __post_init__ initializes _raw_data"""
        assert hasattr(simple_config, "_raw_data")

    def test_post_init_sets_is_merged(self, simple_config):
        """Test that __post_init__ initializes _is_merged"""
        assert hasattr(simple_config, "_is_merged")
        assert simple_config._is_merged is False

    def test_validate_called_on_init(self):
        """Test that validate() is called during initialization"""

        @dataclass
        class ValidatedConfig(BaseConfig):
            name: str = local_param(required=True, default="test")
            validate_called: bool = False

            def validate(self):
                # This will be called during __post_init__
                object.__setattr__(self, "validate_called", True)

        config = ValidatedConfig()
        assert config.validate_called is True


@pytest.mark.unit
class TestFromDict:
    """Test from_dict class method"""

    def test_from_dict_basic(self):
        """Test from_dict with basic configuration"""
        from conftest import SimpleConfig

        data = {"simple": {"name": "test_app", "count": 10}}

        config = SimpleConfig.from_dict(data, module_section="simple")

        assert config.name == "test_app"
        assert config.count == 10
        assert config._raw_data == data

    def test_from_dict_with_global_section(self):
        """Test from_dict with global and local sections"""
        from conftest import DatabaseConfig

        data = {
            "global": {"username": "admin", "password": "secret"},
            "database": {"host": "db.example.com", "port": 3306},
        }

        config = DatabaseConfig.from_dict(data, module_section="database")

        assert config.host == "db.example.com"
        assert config.port == 3306
        assert config.username == "admin"
        assert config.password == "secret"

    def test_from_dict_missing_module_section(self):
        """Test from_dict raises error when module section is missing"""
        from conftest import SimpleConfig

        data = {"other": {"name": "test"}}

        with pytest.raises(ValueError, match="Can not find section 'simple'"):
            SimpleConfig.from_dict(data, module_section="simple")

    def test_from_dict_invalid_data_type(self):
        """Test from_dict raises error for non-dict data"""
        from conftest import SimpleConfig

        with pytest.raises(TypeError, match="Expected dict"):
            SimpleConfig.from_dict("not a dict", module_section="simple")

    def test_from_dict_missing_required_param(self):
        """Test from_dict validates required parameters"""

        @dataclass
        class StrictConfig(BaseConfig):
            required_field: str = global_param(required=True, default=None)

        data = {"global": {}, "strict": {}}

        with pytest.raises(ValueError, match="required"):
            StrictConfig.from_dict(data, module_section="strict")

    def test_from_dict_with_nested_config(self):
        """Test from_dict with nested configuration"""
        from conftest import AppConfig

        data = {
            "global": {"app_name": "TestApp", "username": "admin"},
            "app": {
                "debug": True,
                "database": {"host": "localhost", "port": 5432},
            },
        }

        config = AppConfig.from_dict(data, module_section="app")

        assert config.app_name == "TestApp"
        assert config.debug is True
        assert config.database is not None
        assert config.database.host == "localhost"
        assert config.database.username == "admin"

    def test_from_dict_enable_default_override_false(self):
        """Test from_dict with enable_default_override=False"""
        from conftest import SimpleConfig

        data = {"simple": {"name": "override", "count": 99}}

        config = SimpleConfig.from_dict(
            data, module_section="simple", enable_default_override=False
        )

        # Should use field defaults, not data values
        assert config.name == "test"
        assert config.count == 0


@pytest.mark.unit
class TestGetParamValue:
    """Test get_param_value class method"""

    def test_get_param_value_global_scope(self):
        """Test extracting GLOBAL scope parameter"""
        from conftest import DatabaseConfig

        data = {"global": {"username": "admin"}, "database": {}}

        value = DatabaseConfig.get_param_value(
            data=data,
            field_name="username",
            scope=ParamScope.GLOBAL,
            global_section="global",
            module_section="database",
            warn_on_override=False,
            required=False,
        )

        assert value == "admin"

    def test_get_param_value_global_in_local_raises_error(self):
        """Test that GLOBAL param in local section raises error"""
        from conftest import DatabaseConfig

        data = {"global": {"username": "admin"}, "database": {"username": "local_admin"}}

        with pytest.raises(ValueError, match="cannot be set in local section"):
            DatabaseConfig.get_param_value(
                data=data,
                field_name="username",
                scope=ParamScope.GLOBAL,
                global_section="global",
                module_section="database",
                warn_on_override=False,
            )

    def test_get_param_value_local_scope(self):
        """Test extracting LOCAL scope parameter"""
        from conftest import DatabaseConfig

        data = {"global": {}, "database": {"host": "localhost"}}

        value = DatabaseConfig.get_param_value(
            data=data,
            field_name="host",
            scope=ParamScope.LOCAL,
            global_section="global",
            module_section="database",
            warn_on_override=False,
        )

        assert value == "localhost"

    def test_get_param_value_local_in_global_raises_error(self):
        """Test that LOCAL param in global section raises error"""
        from conftest import DatabaseConfig

        data = {"global": {"host": "localhost"}, "database": {"host": "db.local"}}

        with pytest.raises(ValueError, match="cannot be set in global section"):
            DatabaseConfig.get_param_value(
                data=data,
                field_name="host",
                scope=ParamScope.LOCAL,
                global_section="global",
                module_section="database",
                warn_on_override=False,
            )

    def test_get_param_value_global_first_priority(self):
        """Test GLOBAL_FIRST prioritizes global section"""
        from conftest import AppConfig

        data = {
            "global": {"max_workers": 10},
            "app": {"max_workers": 20},
        }

        value = AppConfig.get_param_value(
            data=data,
            field_name="max_workers",
            scope=ParamScope.GLOBAL_FIRST,
            global_section="global",
            module_section="app",
            warn_on_override=False,
        )

        assert value == 10

    def test_get_param_value_local_first_priority(self):
        """Test LOCAL_FIRST prioritizes local section"""
        from conftest import AppConfig

        data = {
            "global": {"timeout": 10},
            "app": {"timeout": 20},
        }

        value = AppConfig.get_param_value(
            data=data,
            field_name="timeout",
            scope=ParamScope.LOCAL_FIRST,
            global_section="global",
            module_section="app",
            warn_on_override=False,
        )

        assert value == 20

    def test_get_param_value_global_first_fallback(self):
        """Test GLOBAL_FIRST falls back to local if global not present"""
        from conftest import AppConfig

        data = {"global": {}, "app": {"max_workers": 20}}

        value = AppConfig.get_param_value(
            data=data,
            field_name="max_workers",
            scope=ParamScope.GLOBAL_FIRST,
            global_section="global",
            module_section="app",
            warn_on_override=False,
        )

        assert value == 20

    def test_get_param_value_local_first_fallback(self):
        """Test LOCAL_FIRST falls back to global if local not present"""
        from conftest import AppConfig

        data = {"global": {"timeout": 10}, "app": {}}

        value = AppConfig.get_param_value(
            data=data,
            field_name="timeout",
            scope=ParamScope.LOCAL_FIRST,
            global_section="global",
            module_section="app",
            warn_on_override=False,
        )

        assert value == 10

    def test_get_param_value_nested_scope(self):
        """Test extracting NESTED scope parameter"""
        from conftest import AppConfig, DatabaseConfig

        data = {
            "global": {"username": "admin"},
            "app": {"database": {"host": "db.example.com"}},
        }

        value = AppConfig.get_param_value(
            data=data,
            field_name="database",
            scope=ParamScope.NESTED,
            global_section="global",
            module_section="app",
            warn_on_override=False,
            nested_class=DatabaseConfig,
        )

        assert isinstance(value, DatabaseConfig)
        assert value.host == "db.example.com"
        assert value.username == "admin"


@pytest.mark.unit
class TestValidateRequiredParams:
    """Test _validate_required_params method"""

    def test_validate_required_params_success(self):
        """Test validation passes with all required params"""

        @dataclass
        class TestConfig(BaseConfig):
            required_field: str = global_param(required=True, default="value")

        config = TestConfig()
        # Should not raise
        config._validate_required_params()

    def test_validate_required_params_missing(self):
        """Test validation fails with missing required params"""

        @dataclass
        class TestConfig(BaseConfig):
            required_field: str = global_param(required=True, default=None)

        config = TestConfig()

        with pytest.raises(ValueError, match="Missing required parameters"):
            config._validate_required_params()


@pytest.mark.unit
class TestValidate:
    """Test validate hook method"""

    def test_validate_custom_logic(self):
        """Test that custom validate logic is executed"""

        @dataclass
        class PortConfig(BaseConfig):
            port: int = local_param(required=False, default=8080)

            def validate(self):
                if self.port < 1 or self.port > 65535:
                    raise ValueError(f"Invalid port: {self.port}")

        # Valid port should work
        config = PortConfig(port=8080)
        assert config.port == 8080

        # Invalid port should raise error
        with pytest.raises(ValueError, match="Invalid port"):
            PortConfig(port=99999)


@pytest.mark.unit
class TestToDict:
    """Test to_dict method"""

    def test_to_dict_basic(self, simple_config):
        """Test to_dict with simple configuration"""
        result = simple_config.to_dict()

        assert "simple" in result
        assert result["simple"]["name"] == "test_app"
        assert result["simple"]["count"] == 5

    def test_to_dict_with_global_section(self, database_config):
        """Test to_dict includes global section"""
        result = database_config.to_dict()

        assert "global" in result
        assert "database" in result
        assert result["database"]["host"] == "db.example.com"
        assert result["global"]["username"] == "admin"

    def test_to_dict_custom_section_names(self, simple_config):
        """Test to_dict with custom section names"""
        result = simple_config.to_dict(
            global_section="config", module_section="custom"
        )

        assert "config" in result
        assert "custom" in result
        assert result["custom"]["name"] == "test_app"

    def test_to_dict_include_none_false(self, database_config):
        """Test to_dict excludes None values when include_none=False"""
        result = database_config.to_dict(include_none=False)

        # password is None, should be excluded
        assert "password" not in result["global"]

    def test_to_dict_include_global_section_false(self, database_config):
        """Test to_dict excludes empty global section when include_global_section=False"""
        result = database_config.to_dict(include_global_section=False, include_none=False)

        # When include_global_section=False and include_none=False,
        # global section should not be created if empty
        if "global" in result:
            # If global exists, it should at least have some non-None values
            assert len(result["global"]) > 0
        assert "database" in result

    def test_to_dict_with_nested_config(self, app_config):
        """Test to_dict with nested configuration"""
        app_config.database = app_config.database or type(app_config.database)()

        result = app_config.to_dict()

        assert "app" in result
        assert "database" in result["app"]
        assert isinstance(result["app"]["database"], dict)
