"""
Tests for metadata collection and global parameter conflict detection
"""

from dataclasses import dataclass

import pytest

from scopey.config import BaseConfig, global_param, local_param


@dataclass
class MetadataTestConfig(BaseConfig):
    """Config for testing metadata collection"""

    global_str: str = global_param(required=False, default="test")
    global_int: int = global_param(required=True, default=42)
    local_float: float = local_param(required=False, default=3.14)
    local_bool: bool = local_param(required=True, default=True)


@dataclass
class ConflictConfig1(BaseConfig):
    """First config with global params"""

    learning_rate: float = global_param(required=False, default=0.001)
    batch_size: int = global_param(required=False, default=32)
    model_name: str = local_param(required=False, default="model1")


@dataclass
class ConflictConfig2(BaseConfig):
    """Second config with conflicting global param type"""

    learning_rate: str = global_param(
        required=False, default="0.001"
    )  # Conflict: str instead of float
    epochs: int = global_param(required=False, default=100)
    data_path: str = local_param(required=False, default="/data")


@dataclass
class ConflictConfig3(BaseConfig):
    """Third config with matching global param type"""

    learning_rate: float = global_param(
        required=False, default=0.01
    )  # Same type as ConflictConfig1
    dropout: float = global_param(required=False, default=0.5)
    optimizer: str = local_param(required=False, default="adam")


@pytest.mark.unit
class TestMetadataCollection:
    """Test metadata collection in to_dict()"""

    def test_to_dict_without_metadata(self):
        """Test to_dict() without metadata returns plain values"""
        config = MetadataTestConfig()
        result = config.to_dict(include_metadata=False)

        assert "global" in result
        assert "metadatatest" in result

        # Should have plain values, not wrapped with _value/_metadata
        assert result["global"]["global_str"] == "test"
        assert result["global"]["global_int"] == 42
        assert result["metadatatest"]["local_float"] == 3.14
        assert result["metadatatest"]["local_bool"] is True

        # No metadata structure
        assert not isinstance(result["global"]["global_str"], dict)

    def test_to_dict_with_metadata(self):
        """Test to_dict() with metadata wraps values with metadata"""
        config = MetadataTestConfig()
        result = config.to_dict(include_metadata=True)

        assert "global" in result
        assert "metadatatest" in result

        # Should have metadata structure
        global_str_data = result["global"]["global_str"]
        assert isinstance(global_str_data, dict)
        assert "_value" in global_str_data
        assert "_metadata" in global_str_data
        assert global_str_data["_value"] == "test"

        # Check metadata content
        metadata = global_str_data["_metadata"]
        assert metadata["type"] == "str"
        assert "scope" in metadata
        assert metadata["required"] is False
        assert metadata["default"] == "test"

    def test_metadata_includes_correct_types(self):
        """Test that metadata correctly identifies field types"""
        config = MetadataTestConfig()
        result = config.to_dict(include_metadata=True)

        # Check each field type
        assert result["global"]["global_str"]["_metadata"]["type"] == "str"
        assert result["global"]["global_int"]["_metadata"]["type"] == "int"
        assert result["metadatatest"]["local_float"]["_metadata"]["type"] == "float"
        assert result["metadatatest"]["local_bool"]["_metadata"]["type"] == "bool"

    def test_metadata_includes_correct_scopes(self):
        """Test that metadata correctly identifies parameter scopes"""
        from scopey.config import ParamScope

        config = MetadataTestConfig()
        result = config.to_dict(include_metadata=True)

        # Check scopes
        assert result["global"]["global_str"]["_metadata"]["scope"] == ParamScope.GLOBAL
        assert result["global"]["global_int"]["_metadata"]["scope"] == ParamScope.GLOBAL
        assert result["metadatatest"]["local_float"]["_metadata"]["scope"] == ParamScope.LOCAL
        assert result["metadatatest"]["local_bool"]["_metadata"]["scope"] == ParamScope.LOCAL

    def test_metadata_includes_required_flags(self):
        """Test that metadata correctly identifies required fields"""
        config = MetadataTestConfig()
        result = config.to_dict(include_metadata=True)

        # Check required flags
        assert result["global"]["global_str"]["_metadata"]["required"] is False
        assert result["global"]["global_int"]["_metadata"]["required"] is True
        assert result["metadatatest"]["local_float"]["_metadata"]["required"] is False
        assert result["metadatatest"]["local_bool"]["_metadata"]["required"] is True

    def test_to_toml_uses_metadata_for_comments(self, temp_toml_file):
        """Test that to_toml() with show_comments=True uses embedded metadata"""
        config = MetadataTestConfig()
        config.to_toml(temp_toml_file, show_comments=True)

        content = temp_toml_file.read_text(encoding="utf-8")

        # Should have type information in comments
        assert "str" in content
        assert "int" in content
        assert "float" in content
        assert "bool" in content

        # Should have scope information
        assert "GLOBAL" in content
        assert "LOCAL" in content

    def test_to_flat_toml_uses_metadata_for_comments(self, temp_toml_file):
        """Test that to_flat_toml() with show_comments=True uses embedded metadata"""
        merged = BaseConfig.combine(
            {"config1": ConflictConfig1, "config3": ConflictConfig3},
            combined_name="MetadataTestMerged",
        )

        merged.to_flat_toml(temp_toml_file, show_comments=True)

        content = temp_toml_file.read_text(encoding="utf-8")

        # Should have correct type information for global params
        # This tests the fix for the original bug where global params showed wrong types
        lines = content.split("\n")

        # Find learning_rate line and check it has correct metadata
        learning_rate_lines = [line for line in lines if "learning_rate" in line and not line.strip().startswith("#")]
        assert len(learning_rate_lines) > 0

        # Should show float type, not str
        for line in learning_rate_lines:
            if "#" in line:
                comment_part = line.split("#")[1]
                assert "float" in comment_part
                assert "GLOBAL" in comment_part


@pytest.mark.unit
class TestGlobalParamConflictDetection:
    """Test global parameter type conflict detection"""

    def test_no_conflict_with_matching_types(self, temp_toml_file):
        """Test that configs with matching global param types don't raise errors"""
        # ConflictConfig1 and ConflictConfig3 both have learning_rate: float
        merged = BaseConfig.combine(
            {"config1": ConflictConfig1, "config3": ConflictConfig3},
            combined_name="NoConflictConfig",
        )

        # Should succeed without error
        merged.to_flat_toml(temp_toml_file, show_comments=True)

        content = temp_toml_file.read_text(encoding="utf-8")
        assert "[config1]" in content
        assert "[config3]" in content

    def test_conflict_with_different_types(self, temp_toml_file):
        """Test that configs with conflicting global param types raise ValueError"""
        # ConflictConfig1 has learning_rate: float
        # ConflictConfig2 has learning_rate: str
        merged = BaseConfig.combine(
            {"config1": ConflictConfig1, "config2": ConflictConfig2},
            combined_name="ConflictConfig",
        )

        # Should raise ValueError when trying to generate TOML with show_comments=True
        with pytest.raises(ValueError, match="Global parameter 'learning_rate' has conflicting type definitions"):
            merged.to_flat_toml(temp_toml_file, show_comments=True)

    def test_conflict_error_message_details(self, temp_toml_file):
        """Test that conflict error message includes helpful details"""
        merged = BaseConfig.combine(
            {"config1": ConflictConfig1, "config2": ConflictConfig2},
            combined_name="ConflictConfig",
        )

        with pytest.raises(ValueError) as exc_info:
            merged.to_flat_toml(temp_toml_file, show_comments=True)

        error_message = str(exc_info.value)

        # Should mention the parameter name
        assert "learning_rate" in error_message

        # Should mention both config sources
        assert "config1" in error_message
        assert "config2" in error_message

        # Should mention both types
        assert "float" in error_message
        assert "str" in error_message

    def test_no_conflict_check_without_show_comments(self, temp_toml_file):
        """Test that conflict detection only runs when show_comments=True"""
        merged = BaseConfig.combine(
            {"config1": ConflictConfig1, "config2": ConflictConfig2},
            combined_name="NoCheckConfig",
        )

        # Should not raise error when show_comments=False
        # because conflict detection only runs when include_metadata=True
        merged.to_flat_toml(temp_toml_file, show_comments=False)

        # Should succeed and create file
        assert temp_toml_file.exists()

    def test_three_configs_with_conflict(self, temp_toml_file):
        """Test conflict detection with three configs where two conflict"""
        merged = BaseConfig.combine(
            {
                "config1": ConflictConfig1,  # learning_rate: float
                "config2": ConflictConfig2,  # learning_rate: str (conflict!)
                "config3": ConflictConfig3,  # learning_rate: float
            },
            combined_name="ThreeConfigConflict",
        )

        # Should detect the conflict between config1/config3 and config2
        with pytest.raises(ValueError, match="conflicting type definitions"):
            merged.to_flat_toml(temp_toml_file, show_comments=True)

    def test_conflict_detection_with_merge_method(self, temp_toml_file):
        """Test that conflict detection also works with merge() method"""
        config1_instance = ConflictConfig1()
        config2_instance = ConflictConfig2()

        merged = BaseConfig.merge(
            {"config1": config1_instance, "config2": config2_instance},
            merged_name="MergedConflict",
        )

        # Should also detect conflict when using merge() instead of combine()
        with pytest.raises(ValueError, match="conflicting type definitions"):
            merged.to_flat_toml(temp_toml_file, show_comments=True)

    def test_no_conflict_with_different_global_params(self, temp_toml_file):
        """Test that different global params (not overlapping) don't conflict"""

        @dataclass
        class ConfigA(BaseConfig):
            param_a: str = global_param(required=False, default="a")
            local_a: int = local_param(required=False, default=1)

        @dataclass
        class ConfigB(BaseConfig):
            param_b: float = global_param(required=False, default=1.0)
            local_b: str = local_param(required=False, default="b")

        merged = BaseConfig.combine(
            {"config_a": ConfigA, "config_b": ConfigB}, combined_name="NoDuplicateParams"
        )

        # Should succeed because param_a and param_b are different parameters
        merged.to_flat_toml(temp_toml_file, show_comments=True)

        content = temp_toml_file.read_text(encoding="utf-8")
        assert "param_a" in content
        assert "param_b" in content

    def test_conflict_with_same_value_different_type(self, temp_toml_file):
        """Test that even with same default value, different types are detected"""

        @dataclass
        class ConfigNumInt(BaseConfig):
            number: int = global_param(required=False, default=42)

        @dataclass
        class ConfigNumFloat(BaseConfig):
            number: float = global_param(required=False, default=42.0)

        merged = BaseConfig.combine(
            {"int_config": ConfigNumInt, "float_config": ConfigNumFloat},
            combined_name="SameValueDiffType",
        )

        # Should detect conflict even though values are semantically similar
        with pytest.raises(ValueError, match="conflicting type definitions"):
            merged.to_flat_toml(temp_toml_file, show_comments=True)


@pytest.mark.integration
class TestMetadataIntegration:
    """Integration tests for metadata with other features"""

    def test_metadata_with_nested_configs(self, temp_toml_file):
        """Test that metadata works correctly with nested configurations"""
        from conftest import AppConfig

        config = AppConfig()
        result = config.to_dict(include_metadata=True)

        # Should have metadata for top-level fields
        assert "_metadata" in result["global"]["app_name"]
        assert "_metadata" in result["app"]["debug"]

        # Nested configs should also have metadata when expanded
        if result["app"]["database"] is not None:
            # Nested config itself is a BaseConfig instance
            # When it gets converted, its fields should have metadata too
            pass

    def test_metadata_preserved_through_roundtrip(self, temp_toml_file):
        """Test that metadata-enhanced TOML can be loaded back"""
        config = MetadataTestConfig()

        # Save with comments (which uses metadata)
        config.to_toml(temp_toml_file, show_comments=True)

        # Load back
        loaded = MetadataTestConfig.from_toml(temp_toml_file, module_section="metadatatest")

        # Values should match
        assert loaded.global_str == config.global_str
        assert loaded.global_int == config.global_int
        assert loaded.local_float == config.local_float
        assert loaded.local_bool == config.local_bool

    def test_conflict_detection_in_to_dict(self):
        """Test that conflict detection happens in to_dict() itself"""
        merged = BaseConfig.combine(
            {"config1": ConflictConfig1, "config2": ConflictConfig2},
            combined_name="ConflictInToDict",
        )

        # The conflict should be detected when calling to_dict with include_metadata=True
        with pytest.raises(ValueError, match="conflicting type definitions"):
            merged.to_dict(include_metadata=True)

    def test_no_conflict_in_to_dict_without_metadata(self):
        """Test that conflict is NOT detected in to_dict() without metadata"""
        merged = BaseConfig.combine(
            {"config1": ConflictConfig1, "config2": ConflictConfig2},
            combined_name="NoConflictCheck",
        )

        # Should succeed without metadata
        result = merged.to_dict(include_metadata=False)

        # Should have both configs
        assert "config1" in result["noconflictcheck"]
        assert "config2" in result["noconflictcheck"]
