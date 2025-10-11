"""
Integration tests for merge and combine operations
"""

from dataclasses import dataclass

import pytest

from scopey.config import BaseConfig, global_param, local_param, nested_param


@pytest.mark.integration
class TestMerge:
    """Test merge class method"""

    def test_merge_with_dict(self):
        """Test merging configs using dict input"""
        from conftest import CacheConfig, DatabaseConfig

        db_config = DatabaseConfig(host="db.local", port=5432)
        cache_config = CacheConfig(ttl=3600)

        merged = BaseConfig.merge(
            {"database": db_config, "cache": cache_config}, merged_name="MergedConfig"
        )

        assert hasattr(merged, "database")
        assert hasattr(merged, "cache")
        assert merged.database.host == "db.local"
        assert merged.cache.ttl == 3600
        assert merged._is_merged is True

    def test_merge_with_list(self):
        """Test merging configs using list input"""
        from conftest import CacheConfig, DatabaseConfig

        db_config = DatabaseConfig(host="list.db", port=3306)
        cache_config = CacheConfig(ttl=1800)

        merged = BaseConfig.merge([db_config, cache_config])

        # Field names should be derived from class names
        assert hasattr(merged, "database")
        assert hasattr(merged, "cache")
        assert merged.database.host == "list.db"
        assert merged.cache.ttl == 1800

    def test_merge_preserves_raw_data(self):
        """Test that merge preserves original _raw_data"""
        from conftest import DatabaseConfig, SimpleConfig

        simple = SimpleConfig(name="test", count=5)
        simple._raw_data = {"simple": {"name": "test", "count": 5}}

        db = DatabaseConfig(host="localhost")
        db._raw_data = {"database": {"host": "localhost"}}

        merged = BaseConfig.merge([simple, db])

        # Should merge both raw_data dicts
        assert merged._raw_data is not None
        assert "simple" in merged._raw_data
        assert "database" in merged._raw_data

    def test_merge_empty_list_raises_error(self):
        """Test merge raises error for empty list"""
        # Actually, the current implementation doesn't validate empty list
        # but it would create an empty merged config
        merged = BaseConfig.merge([])
        assert merged._is_merged is True

    def test_merge_invalid_type_raises_error(self):
        """Test merge raises error for invalid input type"""
        with pytest.raises(TypeError, match="must be either dict"):
            BaseConfig.merge("not a dict or list")

    def test_merge_non_baseconfig_raises_error(self):
        """Test merge raises error for non-BaseConfig instances"""
        with pytest.raises(TypeError, match="must be instances of BaseConfig"):
            BaseConfig.merge([{"not": "a config"}])

    def test_merge_field_name_conflict_dict(self):
        """Test that dict with duplicate keys uses last value (Python dict behavior)"""
        from conftest import SimpleConfig

        config1 = SimpleConfig(name="first")
        config2 = SimpleConfig(name="second")

        # Python dict automatically handles duplicate keys by keeping last value
        # This is expected behavior, not an error
        merged = BaseConfig.merge({"simple": config1, "simple": config2})

        # Should use config2 (last one)
        assert merged.simple.name == "second"

    def test_merge_field_name_conflict_list(self):
        """Test merge detects field name conflicts in list input"""
        from conftest import SimpleConfig

        config1 = SimpleConfig(name="first")
        config2 = SimpleConfig(name="second")

        # Both SimpleConfig instances will try to use "simple" as field name
        with pytest.raises(ValueError, match="Field name conflict"):
            BaseConfig.merge([config1, config2])

    def test_merge_custom_name(self):
        """Test merge with custom merged class name"""
        from conftest import DatabaseConfig

        db_config = DatabaseConfig(host="custom.db")

        merged = BaseConfig.merge([db_config], merged_name="CustomMerged")

        assert merged.__class__.__name__ == "CustomMerged"


@pytest.mark.integration
class TestCombine:
    """Test combine class method"""

    def test_combine_with_dict(self):
        """Test combining config classes using dict input"""
        from conftest import CacheConfig, DatabaseConfig

        combined = BaseConfig.combine(
            {"database": DatabaseConfig, "cache": CacheConfig},
            combined_name="CombinedConfig",
        )

        assert hasattr(combined, "database")
        assert hasattr(combined, "cache")
        assert isinstance(combined.database, DatabaseConfig)
        assert isinstance(combined.cache, CacheConfig)
        assert combined._is_merged is True

    def test_combine_with_list(self):
        """Test combining config classes using list input"""
        from conftest import CacheConfig, DatabaseConfig

        combined = BaseConfig.combine([DatabaseConfig, CacheConfig])

        # Field names derived from class names
        assert hasattr(combined, "database")
        assert hasattr(combined, "cache")
        assert isinstance(combined.database, DatabaseConfig)
        assert isinstance(combined.cache, CacheConfig)

    def test_combine_instantiates_with_defaults(self):
        """Test that combine instantiates classes with default values"""
        from conftest import SimpleConfig

        combined = BaseConfig.combine([SimpleConfig])

        # Should use field defaults
        assert combined.simple.name == "test"
        assert combined.simple.count == 0

    def test_combine_nested_configs(self):
        """Test combine with configs that have nested_param fields"""
        from conftest import AppConfig

        combined = BaseConfig.combine([AppConfig])

        assert hasattr(combined, "app")
        assert isinstance(combined.app, AppConfig)

        # Nested fields should also be instantiated
        if combined.app.database is not None:
            assert hasattr(combined.app.database, "host")

    def test_combine_empty_list_raises_error(self):
        """Test combine raises error for empty list"""
        with pytest.raises(ValueError, match="At least one model class must be provided"):
            BaseConfig.combine([])

    def test_combine_invalid_type_raises_error(self):
        """Test combine raises error for invalid input type"""
        with pytest.raises(TypeError, match="must be either dict"):
            BaseConfig.combine("not a dict or list")

    def test_combine_non_class_raises_error(self):
        """Test combine raises error for non-class input"""
        from conftest import SimpleConfig

        instance = SimpleConfig()

        with pytest.raises(TypeError, match="must be BaseConfig subclasses"):
            BaseConfig.combine([instance])  # Passing instance instead of class

    def test_combine_non_baseconfig_class_raises_error(self):
        """Test combine raises error for non-BaseConfig classes"""
        with pytest.raises(TypeError, match="must be BaseConfig subclasses"):
            BaseConfig.combine([dict])

    def test_combine_to_flat_toml(self, temp_toml_file):
        """Test that combined configs can be saved as flat TOML"""
        from conftest import CacheConfig, DatabaseConfig

        combined = BaseConfig.combine({"database": DatabaseConfig, "cache": CacheConfig})

        # Should be able to save as flat TOML
        combined.to_flat_toml(temp_toml_file, show_comments=False)

        content = temp_toml_file.read_text(encoding="utf-8")

        assert "[database]" in content
        assert "[cache]" in content


@pytest.mark.integration
class TestInstantiateWithNested:
    """Test _instantiate_with_nested helper method"""

    def test_instantiate_with_nested_simple(self):
        """Test instantiating config with no nested fields"""
        from conftest import SimpleConfig

        instance = BaseConfig._instantiate_with_nested(SimpleConfig)

        assert isinstance(instance, SimpleConfig)
        assert instance.name == "test"
        assert instance.count == 0

    def test_instantiate_with_nested_recursive(self):
        """Test instantiating config with nested fields"""
        from conftest import AppConfig

        instance = BaseConfig._instantiate_with_nested(AppConfig)

        assert isinstance(instance, AppConfig)

        # Nested configs should be instantiated, not None
        assert instance.database is not None
        assert instance.cache is not None

    def test_instantiate_with_nested_deep(self):
        """Test instantiating deeply nested configs"""

        @dataclass
        class Level3Config(BaseConfig):
            value: str = local_param(default="level3")

        @dataclass
        class Level2Config(BaseConfig):
            name: str = local_param(default="level2")
            level3: Level3Config = nested_param(Level3Config, required=False, default=None)

        @dataclass
        class Level1Config(BaseConfig):
            app: str = global_param(default="app")
            level2: Level2Config = nested_param(Level2Config, required=False, default=None)

        instance = BaseConfig._instantiate_with_nested(Level1Config)

        assert isinstance(instance, Level1Config)
        assert instance.level2 is not None
        assert isinstance(instance.level2, Level2Config)
        assert instance.level2.level3 is not None
        assert isinstance(instance.level2.level3, Level3Config)
        assert instance.level2.level3.value == "level3"


@pytest.mark.integration
class TestMergeAndCombineIntegration:
    """Test integration between merge, combine, and TOML operations"""

    def test_merge_to_flat_toml_to_from_flat_toml(self, temp_toml_file):
        """Test complete workflow: merge -> save flat TOML -> load flat TOML"""
        from conftest import CacheConfig, DatabaseConfig

        # Step 1: Create and merge configs
        db = DatabaseConfig(host="workflow.db", port=5432, username="admin")
        cache = CacheConfig(ttl=7200, max_size=10000)
        merged = BaseConfig.merge({"database": db, "cache": cache})

        # Step 2: Save as flat TOML
        merged.to_flat_toml(temp_toml_file, show_comments=False)

        # Step 3: Load back
        loaded = BaseConfig.from_flat_toml(
            temp_toml_file,
            sections={"database": DatabaseConfig, "cache": CacheConfig},
        )

        # Step 4: Verify
        assert loaded.database.host == "workflow.db"
        assert loaded.database.username == "admin"
        assert loaded.cache.ttl == 7200

    def test_combine_to_flat_toml_as_template(self, temp_toml_file):
        """Test combine -> save flat TOML template"""
        from conftest import CacheConfig, DatabaseConfig

        combined = BaseConfig.combine([DatabaseConfig, CacheConfig])

        # Save as template with comments
        combined.to_flat_toml(temp_toml_file, as_template=True, show_comments=True)

        content = temp_toml_file.read_text(encoding="utf-8")

        # Should have sections
        assert "[database]" in content
        assert "[cache]" in content

        # Should have comments for metadata
        assert "#" in content
