"""
Integration tests for TOML operations (from_toml, to_toml, etc.)
"""

from pathlib import Path

import pytest

from scopey.config import BaseConfig


@pytest.mark.integration
class TestFromToml:
    """Test from_toml class method"""

    def test_from_toml_basic(self, temp_toml_file, basic_toml_content):
        """Test loading basic TOML file"""
        from conftest import AppConfig

        temp_toml_file.write_text(basic_toml_content, encoding="utf-8")

        config = AppConfig.from_toml(temp_toml_file, module_section="app")

        assert config.app_name == "TestApp"
        assert config.debug is True
        assert config.max_workers == 8

    def test_from_toml_with_nested_config(self, temp_toml_file, nested_toml_content):
        """Test loading TOML with nested configurations"""
        from conftest import AppConfig

        temp_toml_file.write_text(nested_toml_content, encoding="utf-8")

        config = AppConfig.from_toml(temp_toml_file, module_section="app")

        assert config.app_name == "NestedApp"
        assert config.debug is False
        assert config.database is not None
        assert config.database.host == "db.example.com"
        assert config.database.username == "admin"
        assert config.cache is not None
        assert config.cache.ttl == 7200

    def test_from_toml_file_not_found(self):
        """Test from_toml raises error for non-existent file"""
        from conftest import AppConfig

        with pytest.raises(FileNotFoundError, match="Path does not exist"):
            AppConfig.from_toml("nonexistent.toml", module_section="app")

    def test_from_toml_invalid_extension(self):
        """Test from_toml raises error for non-TOML file"""
        from conftest import AppConfig

        with pytest.raises(Exception):  # Should be caught by check_path decorator
            AppConfig.from_toml("config.txt", module_section="app")

    def test_from_toml_custom_global_section(self, temp_toml_file):
        """Test from_toml with custom global section name"""
        from conftest import AppConfig

        toml_content = """
[config]
app_name = "CustomGlobal"

[app]
debug = true
"""
        temp_toml_file.write_text(toml_content, encoding="utf-8")

        config = AppConfig.from_toml(
            temp_toml_file, module_section="app", global_section="config"
        )

        assert config.app_name == "CustomGlobal"

    def test_from_toml_warn_on_override(self, temp_toml_file):
        """Test from_toml warns when override occurs"""
        from conftest import AppConfig

        toml_content = """
[global]
app_name = "TestApp"
max_workers = 10

[app]
max_workers = 20
"""
        temp_toml_file.write_text(toml_content, encoding="utf-8")

        # Should warn because max_workers is GLOBAL_FIRST but defined in both sections
        with pytest.warns(UserWarning, match="uses global section value"):
            config = AppConfig.from_toml(
                temp_toml_file, module_section="app", warn_on_override=True
            )

        # Should use global value (GLOBAL_FIRST priority)
        assert config.max_workers == 10


@pytest.mark.integration
class TestToToml:
    """Test to_toml method"""

    def test_to_toml_basic(self, temp_toml_file, simple_config):
        """Test saving basic configuration to TOML"""
        simple_config.to_toml(temp_toml_file, show_comments=False)

        assert temp_toml_file.exists()

        # Read back and verify
        content = temp_toml_file.read_text(encoding="utf-8")
        assert "test_app" in content
        assert "5" in content

    def test_to_toml_with_nested_config(self, temp_toml_file):
        """Test saving nested configuration to TOML"""
        from conftest import AppConfig, DatabaseConfig

        config = AppConfig(
            app_name="NestedTest", debug=True, database=DatabaseConfig(host="db.local")
        )

        config.to_toml(temp_toml_file, show_comments=False)

        assert temp_toml_file.exists()

        content = temp_toml_file.read_text(encoding="utf-8")
        assert "NestedTest" in content
        assert "db.local" in content

    def test_to_toml_auto_filename(self, simple_config):
        """Test to_toml generates filename automatically"""
        simple_config.to_toml(show_comments=False)

        # Should create simple.toml
        expected_file = Path("simple.toml")
        assert expected_file.exists()

        # Cleanup
        expected_file.unlink()

    def test_to_toml_as_template(self, temp_toml_file, app_config):
        """Test to_toml in template mode includes None fields"""
        app_config.to_toml(temp_toml_file, as_template=True, show_comments=True)

        content = temp_toml_file.read_text(encoding="utf-8")

        # Should include commented None fields
        assert "#" in content

    def test_to_toml_show_comments(self, temp_toml_file, simple_config):
        """Test to_toml includes metadata comments"""
        simple_config.to_toml(temp_toml_file, show_comments=True)

        content = temp_toml_file.read_text(encoding="utf-8")

        # Should include type/scope comments
        assert "#" in content

    def test_to_toml_roundtrip(self, temp_toml_file, database_config):
        """Test saving and loading produces equivalent config"""
        # Save
        database_config.to_toml(temp_toml_file, show_comments=False)

        # Load
        from conftest import DatabaseConfig

        loaded_config = DatabaseConfig.from_toml(temp_toml_file, module_section="database")

        # Compare
        assert loaded_config.host == database_config.host
        assert loaded_config.port == database_config.port
        assert loaded_config.username == database_config.username


@pytest.mark.integration
class TestFromDict:
    """Test from_dict integration scenarios"""

    def test_from_dict_complex_nested(self):
        """Test from_dict with complex nested structure"""
        from conftest import AppConfig

        data = {
            "global": {
                "app_name": "ComplexApp",
                "username": "root",
                "password": "secret",
                "max_size": 5000,
            },
            "app": {
                "debug": False,
                "max_workers": 32,
                "timeout": 120,
                "database": {"host": "prod.db.com", "port": 5432},
                "cache": {"ttl": 1800},
            },
        }

        config = AppConfig.from_dict(data, module_section="app")

        # Verify all levels
        assert config.app_name == "ComplexApp"
        assert config.debug is False
        assert config.max_workers == 32
        assert config.database.host == "prod.db.com"
        assert config.database.username == "root"
        assert config.cache.ttl == 1800
        assert config.cache.max_size == 5000


@pytest.mark.integration
class TestFromFlatToml:
    """Test from_flat_toml class method"""

    def test_from_flat_toml_basic(self, temp_toml_file):
        """Test loading flat TOML with multiple sections"""
        from conftest import CacheConfig, DatabaseConfig

        toml_content = """
[global]
username = "admin"
password = "secret"
max_size = 2000

[database]
host = "db.example.com"
port = 3306

[cache]
ttl = 7200
"""
        temp_toml_file.write_text(toml_content, encoding="utf-8")

        merged = BaseConfig.from_flat_toml(
            temp_toml_file,
            sections={"database": DatabaseConfig, "cache": CacheConfig},
        )

        # Should have both nested configs
        assert hasattr(merged, "database")
        assert hasattr(merged, "cache")
        assert merged.database.host == "db.example.com"
        assert merged.database.username == "admin"
        assert merged.cache.ttl == 7200
        assert merged.cache.max_size == 2000
        assert merged._is_merged is True

    def test_from_flat_toml_missing_section(self, temp_toml_file):
        """Test from_flat_toml raises error for missing section"""
        from conftest import DatabaseConfig

        toml_content = """
[global]
username = "admin"
"""
        temp_toml_file.write_text(toml_content, encoding="utf-8")

        with pytest.raises(ValueError, match="Section 'database' not found"):
            BaseConfig.from_flat_toml(
                temp_toml_file, sections={"database": DatabaseConfig}
            )

    def test_from_flat_toml_invalid_class(self, temp_toml_file):
        """Test from_flat_toml raises error for non-BaseConfig class"""
        toml_content = """
[database]
host = "localhost"
"""
        temp_toml_file.write_text(toml_content, encoding="utf-8")

        with pytest.raises(TypeError, match="must be a BaseConfig subclass"):
            BaseConfig.from_flat_toml(
                temp_toml_file, sections={"database": dict}  # Invalid class
            )


@pytest.mark.integration
class TestToFlatToml:
    """Test to_flat_toml method"""

    def test_to_flat_toml_merged_config(self, temp_toml_file):
        """Test saving merged config as flat TOML"""
        from conftest import CacheConfig, DatabaseConfig

        db_config = DatabaseConfig(host="db.local", username="admin")
        cache_config = CacheConfig(ttl=3600)

        merged = BaseConfig.merge(
            {"database": db_config, "cache": cache_config}, merged_name="MergedConfig"
        )

        merged.to_flat_toml(temp_toml_file, show_comments=False)

        content = temp_toml_file.read_text(encoding="utf-8")

        # Should have top-level sections (not nested under merged config)
        assert "[database]" in content
        assert "[cache]" in content
        assert "db.local" in content
        assert "3600" in content

    def test_to_flat_toml_non_merged_raises_error(self, temp_toml_file, simple_config):
        """Test to_flat_toml raises error on non-merged config"""
        with pytest.raises(ValueError, match="can only be used on merged configurations"):
            simple_config.to_flat_toml(temp_toml_file)

    def test_to_flat_toml_roundtrip(self, temp_toml_file):
        """Test flat TOML save/load roundtrip"""
        from conftest import CacheConfig, DatabaseConfig

        # Create merged config
        db_config = DatabaseConfig(host="test.db", port=5432, username="root")
        cache_config = CacheConfig(ttl=1800, max_size=5000)

        merged = BaseConfig.merge({"database": db_config, "cache": cache_config})

        # Save as flat TOML
        merged.to_flat_toml(temp_toml_file, show_comments=False)

        # Load back
        loaded = BaseConfig.from_flat_toml(
            temp_toml_file,
            sections={"database": DatabaseConfig, "cache": CacheConfig},
        )

        # Verify
        assert loaded.database.host == "test.db"
        assert loaded.database.username == "root"
        assert loaded.cache.ttl == 1800
        assert loaded.cache.max_size == 5000
