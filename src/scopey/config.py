import copy
import warnings
from dataclasses import Field, dataclass, field, fields, make_dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Self

import tomlkit

from .utils import check_path


class ParamScope(Enum):
    GLOBAL = auto()
    LOCAL = auto()
    NESTED = auto()
    GLOBAL_FIRST = auto()
    LOCAL_FIRST = auto()


def param_field(
    scope: ParamScope,
    required: bool,
    default: Any,
) -> Field:
    """
    Create a dataclass field with parameter scope metadata.

    This is the base function used by all param helper functions (global_param,
    local_param, etc.). It uses default_factory with deepcopy to prevent mutable
    default value issues.

    Args:
        scope: The parameter scope (GLOBAL, LOCAL, NESTED, etc.)
        required: Whether this parameter is required
        default: The default value (will be deep-copied)

    Returns:
        A dataclass Field with scope metadata
    """
    metadata = {"param_scope": scope, "required": required}

    # use deepcopy to prevent unintended mutation of original object
    return field(default_factory=lambda: copy.deepcopy(default), metadata=metadata)


def global_param(required: bool = True, default: Any = None) -> Field:
    """
    Create a GLOBAL scope parameter field.

    GLOBAL parameters must be defined in the global section only. They cannot
    appear in module-specific sections.

    Args:
        required: Whether this parameter is required (default: True)
        default: Default value if not provided (default: None)

    Returns:
        A dataclass Field configured for GLOBAL scope

    Example:
        >>> @dataclass
        >>> class MyConfig(BaseConfig):
        ...     log_level: str = global_param(default="INFO")
    """
    return param_field(ParamScope.GLOBAL, required, default)


def local_param(required: bool = True, default: Any = None) -> Field:
    """
    Create a LOCAL scope parameter field.

    LOCAL parameters must be defined in the module-specific section only.
    They cannot appear in the global section.

    Args:
        required: Whether this parameter is required (default: True)
        default: Default value if not provided (default: None)

    Returns:
        A dataclass Field configured for LOCAL scope

    Example:
        >>> @dataclass
        >>> class MyConfig(BaseConfig):
        ...     module_name: str = local_param(default="mymodule")
    """
    return param_field(ParamScope.LOCAL, required, default)


def global_first_param(required: bool = True, default: Any = None) -> Field:
    """
    Create a GLOBAL_FIRST scope parameter field.

    GLOBAL_FIRST parameters prioritize the global section but fall back to
    the module section if not found. Warns if both are defined.

    Args:
        required: Whether this parameter is required (default: True)
        default: Default value if not provided (default: None)

    Returns:
        A dataclass Field configured for GLOBAL_FIRST scope

    Example:
        >>> @dataclass
        >>> class MyConfig(BaseConfig):
        ...     timeout: int = global_first_param(default=30)
    """
    return param_field(ParamScope.GLOBAL_FIRST, required, default)


def local_first_param(required: bool = True, default: Any = None) -> Field:
    """
    Create a LOCAL_FIRST scope parameter field.

    LOCAL_FIRST parameters prioritize the module section but fall back to
    the global section if not found. Warns if both are defined.

    Args:
        required: Whether this parameter is required (default: True)
        default: Default value if not provided (default: None)

    Returns:
        A dataclass Field configured for LOCAL_FIRST scope

    Example:
        >>> @dataclass
        >>> class MyConfig(BaseConfig):
        ...     batch_size: int = local_first_param(default=32)
    """
    return param_field(ParamScope.LOCAL_FIRST, required, default)


def nested_param(
    nested_class: type, required: bool = True, default: Any = None
) -> Field:
    """
    Create a NESTED scope parameter field.

    NESTED parameters contain nested configuration objects of another
    BaseConfig subclass. The nested class is recursively instantiated.

    Args:
        nested_class: The BaseConfig subclass to use for nested configuration
        required: Whether this parameter is required (default: True)
        default: Default value if not provided (default: None)

    Returns:
        A dataclass Field configured for NESTED scope with nested class metadata

    Example:
        >>> @dataclass
        >>> class DatabaseConfig(BaseConfig):
        ...     host: str = local_param(default="localhost")
        >>>
        >>> @dataclass
        >>> class AppConfig(BaseConfig):
        ...     database: DatabaseConfig = nested_param(nested_class=DatabaseConfig)
    """
    metadata = {
        "param_scope": ParamScope.NESTED,
        "required": required,
        "nested_class": nested_class,
    }
    return field(default_factory=lambda: copy.deepcopy(default), metadata=metadata)


@dataclass
class BaseConfig:
    def __post_init__(self) -> None:
        """
        Initialize configuration instance after dataclass initialization.

        This method is automatically called after __init__. It performs the following:
        1. Initializes _raw_data to store the original configuration dict
        2. Initializes _is_merged flag to track if this is a merged configuration
        3. Calls validate() for custom validation logic

        Note:
            _raw_data and _is_merged are instance attributes, not dataclass fields.
            They won't appear in fields() or __init__ parameters.
        """
        # Initialize original data storage
        if not hasattr(self, "_raw_data"):
            self._raw_data = None

        # Initialize merged flag
        if not hasattr(self, "_is_merged"):
            self._is_merged = False

        self.validate()

    @classmethod
    @check_path(check_type="file", suffix="toml")  # check file path, must be toml
    def from_toml(
        cls,
        path: str | Path,
        module_section: str,
        global_section: str = "global",
        enable_default_override: bool = True,
        warn_on_override: bool = True,
    ) -> Self:
        """
        Create a configuration instance from a TOML file.

        Args:
            path: Path to the TOML file (must have .toml extension)
            module_section: Name of the module-specific section in the TOML file
            global_section: Name of the global section (default: "global")
            enable_default_override: Whether to allow TOML values to override field defaults (default: True)
            warn_on_override: Whether to warn when priority-based parameter override occurs (default: True)

        Returns:
            A new instance of the configuration class with values loaded from the TOML file

        Raises:
            ValueError: If the file cannot be loaded or parsed

        Example:
            >>> config = MyConfig.from_toml("config.toml", module_section="mymodule")
        """
        try:
            with open(file=path, mode="r", encoding="utf-8") as f:
                toml_data = tomlkit.load(f)

            return cls.from_dict(
                toml_data,
                module_section,
                global_section,
                enable_default_override,
                warn_on_override,
            )

        except Exception as e:
            raise ValueError(f"Can not load TOML config from {path}: {e}")

    @classmethod
    @check_path(check_type="file", suffix="toml")
    def from_flat_toml(
        cls,
        path: str | Path,
        sections: dict[str, type["BaseConfig"]],
        global_section: str = "global",
        merged_name: str = "MergedConfig",
        enable_default_override: bool = True,
        warn_on_override: bool = True,
    ) -> Self:
        """
        Create a merged configuration instance from a flat TOML file.

        This method is the inverse of to_flat_toml(). It reads a flat TOML structure
        where multiple configurations are at the top level, instantiates each section
        with its corresponding config class, and merges them into a single configuration.

        Args:
            path: Path to the flat TOML file (must have .toml extension)
            sections: Dictionary mapping section names to their corresponding BaseConfig classes
                     e.g., {"database": DatabaseConfig, "cache": CacheConfig}
            global_section: Name of the global section (default: "global")
            merged_name: Name for the dynamically created merged class (default: "MergedConfig")
            enable_default_override: Whether to allow TOML values to override field defaults (default: True)
            warn_on_override: Whether to warn when priority-based parameter override occurs (default: True)

        Returns:
            A merged configuration instance with _is_merged flag set to True

        Raises:
            ValueError: If the file cannot be loaded or a specified section is not found
            TypeError: If any section class is not a BaseConfig subclass

        Example:
            >>> # Given a flat TOML file:
            >>> # [global]
            >>> # log_level = "INFO"
            >>> #
            >>> # [database]
            >>> # host = "localhost"
            >>> #
            >>> # [cache]
            >>> # ttl = 3600
            >>>
            >>> merged = Config.from_flat_toml(
            ...     "config.toml",
            ...     sections={"database": DatabaseConfig, "cache": CacheConfig}
            ... )
            >>> # Now you can use merged.database.host or merged.cache.ttl
        """
        # Validate section classes
        for section_name, config_class in sections.items():
            if not isinstance(config_class, type) or not issubclass(
                config_class, BaseConfig
            ):
                raise TypeError(
                    f"Section '{section_name}' must be a BaseConfig subclass, got: {config_class}"
                )

        try:
            with open(file=path, mode="r", encoding="utf-8") as f:
                toml_data = tomlkit.load(f)
        except Exception as e:
            raise ValueError(f"Cannot load TOML config from {path}: {e}")

        # Instantiate each section with its corresponding class
        config_instances: dict[str, Self] = {}
        for section_name, config_class in sections.items():
            if section_name not in toml_data:
                raise ValueError(
                    f"Section '{section_name}' not found in {path}. "
                    f"Available sections: {list(toml_data.keys())}"
                )

            # Create a temporary data structure for this section
            # The flat TOML has each config at top level, we need to restructure it
            section_data = {section_name: toml_data[section_name]}

            # Include global section if it exists
            if global_section in toml_data:
                section_data[global_section] = toml_data[global_section]

            # Instantiate the config for this section
            config_instance = config_class.from_dict(
                data=section_data,
                module_section=section_name,
                global_section=global_section,
                enable_default_override=enable_default_override,
                warn_on_override=warn_on_override,
            )
            config_instances[section_name] = config_instance  # type: ignore[assignment]

        # Merge all instances into a single configuration
        return cls.merge(config_instances, merged_name=class_name)

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        module_section: str,
        global_section: str = "global",
        enable_default_override: bool = True,
        warn_on_override: bool = True,
    ) -> Self:
        """
        Create a configuration instance from a dictionary.

        This method handles the complex logic of mapping dictionary data to configuration
        fields based on their parameter scopes (GLOBAL, LOCAL, NESTED, etc.).

        Args:
            data: Dictionary containing configuration data, typically with global and module sections
            module_section: Name of the module-specific section to read from
            global_section: Name of the global section (default: "global")
            enable_default_override: Whether to allow dict values to override field defaults (default: True)
            warn_on_override: Whether to warn when priority-based parameter override occurs (default: True)

        Returns:
            A new instance of the configuration class populated with data from the dict

        Raises:
            TypeError: If data is not a dict
            ValueError: If module_section is not found in data
            ValueError: If any field is missing param_scope metadata

        Example:
            >>> data = {"global": {"host": "localhost"}, "mymodule": {"port": 8080}}
            >>> config = MyConfig.from_dict(data, module_section="mymodule")
        """

        # Check basic validity of input data
        if not isinstance(data, dict):
            raise TypeError(f"Expected dict, got {type(data)}")

        if module_section not in data:
            raise ValueError(
                f"Can not find section '{module_section}' from available sections: {list(data.keys())}"
            )

        params = {}
        for f in fields(cls):
            field_name = f.name
            scope = f.metadata.get("param_scope")
            required = f.metadata.get("required", False)

            if scope is None:
                raise ValueError(
                    f"Field '{field_name}' in {cls.__name__} must specify param_scope. Use global_param(), local_param(), nested_param(), etc."
                )

            if enable_default_override:  # overwirte default is available
                nested_class = (
                    f.metadata.get("nested_class")
                    if scope == ParamScope.NESTED
                    else None
                )
                value = cls.get_param_value(
                    data=data,
                    field_name=field_name,
                    scope=scope,
                    global_section=global_section,
                    module_section=module_section,
                    warn_on_override=warn_on_override,
                    required=required,
                    nested_class=nested_class,
                )
            else:
                value = None

            if value is None:  # value is None, use default_factory (even be None)
                value = f.default_factory()  # type: ignore[misc]

            params[field_name] = value

        instance = cls(**params)
        # validate required params
        instance._validate_required_params()
        # Save original data
        instance._raw_data = copy.deepcopy(data)  # type: ignore[assignment]
        return instance

    @classmethod
    def get_param_value(
        cls,
        data: dict[str, Any],
        field_name: str,
        scope: ParamScope,
        global_section: str,
        module_section: str,
        warn_on_override: bool,
        required: bool = True,
        nested_class: type["BaseConfig"] | None = None,
    ) -> Any | None:
        """
        Extract a parameter value from configuration data based on its scope.

        This method implements the core logic for parameter scope resolution:
        - GLOBAL: Must be in global section only
        - LOCAL: Must be in module section only
        - GLOBAL_FIRST: Prioritize global, fall back to module
        - LOCAL_FIRST: Prioritize module, fall back to global
        - NESTED: Recursively instantiate nested configuration class

        Args:
            data: Configuration dictionary
            field_name: Name of the field to extract
            scope: Parameter scope defining where to look for the value
            global_section: Name of the global section
            module_section: Name of the module section
            warn_on_override: Whether to warn when priority-based override occurs
            required: Whether this parameter is required (default: True)
            nested_class: For NESTED scope, the BaseConfig subclass to instantiate

        Returns:
            The extracted value, or None if not found and not required

        Raises:
            ValueError: If required parameter is missing or scope rules are violated
            TypeError: If nested data is not a dict
        """
        global_value = data.get(global_section, {}).get(field_name)
        module_value = data.get(module_section, {}).get(field_name)

        if scope == ParamScope.GLOBAL:
            if global_value is None and required:
                raise ValueError(
                    f"Parameter '{field_name}' is marked as GLOBAL and required, but not found in global section '{global_section}'"
                )
            if module_value is not None:
                raise ValueError(
                    f"Parameter '{field_name}' is marked as GLOBAL, cannot be set in local section '{module_section}'"
                )
            return global_value
        elif scope == ParamScope.LOCAL:
            if module_value is None and required:
                raise ValueError(
                    f"Parameter '{field_name}' is marked as LOCAL and required, but not found in local section '{module_section}'"
                )
            if global_value is not None:
                raise ValueError(
                    f"Parameter '{field_name}' is marked as LOCAL, cannot be set in global section '{global_section}'"
                )
            return module_value
        elif scope in [ParamScope.GLOBAL_FIRST, ParamScope.LOCAL_FIRST]:
            # Handle priority logic: GLOBAL_FIRST prioritizes global, LOCAL_FIRST prioritizes local
            is_global_first = scope == ParamScope.GLOBAL_FIRST
            primary_value, secondary_value = (
                (global_value, module_value)
                if is_global_first
                else (module_value, global_value)
            )
            primary_section, secondary_section = (
                (global_section, module_section)
                if is_global_first
                else (module_section, global_section)
            )

            if primary_value is not None:
                if secondary_value is not None and warn_on_override:
                    warnings.warn(
                        f"Parameter '{field_name}' uses {primary_section} section value {primary_value}, "
                        f"ignoring {secondary_section} section value {secondary_value}",
                        UserWarning,
                    )
                return primary_value
            elif secondary_value is not None:
                return secondary_value
            elif required:
                scope_name = "GLOBAL_FIRST" if is_global_first else "LOCAL_FIRST"
                raise ValueError(
                    f"Parameter '{field_name}' is marked as {scope_name} and required, "
                    f"but not found in either global section '{global_section}' or local section '{module_section}'"
                )
            return None
        elif scope == ParamScope.NESTED:
            # NESTED scope processing logic - search in module section for nested data
            module_data = data.get(module_section, {})
            nested_data = module_data.get(field_name)

            if nested_data is None:
                if required:
                    raise ValueError(
                        f"Nested parameter '{field_name}' is required, but not found in section '{module_section}'"
                    )
                return None

            if nested_class is None:
                raise ValueError(
                    f"Nested parameter '{field_name}' missing nested_class"
                )

            # Create temporary data structure for nested class use
            # nested_data should be treated as the module section content for nested class
            if not isinstance(nested_data, dict):
                raise TypeError(
                    f"Nested section '{module_section}.{field_name}' must be a dict, got {type(nested_data)}"
                )

            tmp_data: dict[str, Any] = {field_name: nested_data}
            if global_section in data:
                tmp_data[global_section] = data[global_section]

            # Instantiate using specified nested class
            return nested_class.from_dict(
                data=tmp_data,
                module_section=field_name,
                global_section=global_section,
                warn_on_override=warn_on_override,
            )

        else:
            raise ValueError(f"Unknown parameter scope: {scope}")

    def _validate_required_params(self) -> None:
        """
        Validate that all required parameters have non-None values.

        This method is called automatically during instance creation via from_dict()
        and from_toml(). It checks all fields marked as required=True and ensures
        they have been assigned a value.

        Raises:
            ValueError: If any required parameter is None
        """
        missing_required = []
        for f in fields(self):
            is_required = f.metadata.get("required", False)
            current_value = getattr(self, f.name)

            if is_required and current_value is None:
                missing_required.append(f.name)

        if missing_required:
            raise ValueError(f"Missing required parameters: {missing_required}")

    def validate(self) -> None:
        """
        Custom validation hook for subclasses.

        Override this method in your configuration subclass to implement custom
        validation logic beyond the automatic required parameter checking.

        This method is called automatically during instance initialization in __post_init__,
        after _raw_data and _is_merged are initialized.

        Example:
            >>> class MyConfig(BaseConfig):
            ...     port: int = local_param(default=8080)
            ...
            ...     def validate(self):
            ...         if self.port < 1 or self.port > 65535:
            ...             raise ValueError(f"Invalid port: {self.port}")
        """
        pass

    def to_dict(
        self,
        global_section: str = "global",
        module_section: str | None = None,
        include_none: bool = True,
        include_global_section: bool = True,
    ) -> dict[str, Any]:
        """
        Convert configuration instance to a dictionary representation.

        This method creates a structured dictionary with separate global and module sections,
        respecting parameter scopes and handling nested configurations recursively.

        Args:
            global_section: Name for the global section (default: "global")
            module_section: Name for the module section. If None, derived from class name (default: None)
            include_none: Whether to include fields with None values (default: True)
            include_global_section: Whether to include global section in output (default: True)

        Returns:
            Dictionary with structure: {global_section: {...}, module_section: {...}}

        Example:
            >>> config = MyConfig(host="localhost", port=8080)
            >>> config.to_dict()
            {'global': {'host': 'localhost'}, 'mymodule': {'port': 8080}}
        """

        if module_section is None:
            module_section = self.__class__.__name__.lower().replace("config", "")

        result: dict[str, Any] = {}

        # Decide whether to create global section based on parameter
        if include_global_section:
            result[global_section] = {}

        result[module_section] = {}

        for f in fields(self):
            field_name = f.name
            field_value = getattr(self, field_name)
            scope = f.metadata.get("param_scope")

            # Manually control whether to include None values
            if field_value is None and not include_none:
                continue

            if scope in [ParamScope.GLOBAL, ParamScope.GLOBAL_FIRST]:
                if global_section not in result:
                    result[global_section] = {}
                result[global_section][field_name] = field_value
            elif scope in [ParamScope.LOCAL, ParamScope.LOCAL_FIRST]:
                result[module_section][field_name] = field_value
            elif scope == ParamScope.NESTED:
                # Determine the nested config instance to process
                nested_config = field_value

                if field_value is None:
                    # When nested field is None, create a default instance with all parameters
                    # Get the nested class directly from field metadata
                    nested_class = f.metadata.get("nested_class")

                    if nested_class is None:
                        raise ValueError(
                            f"Nested field '{field_name}' is missing nested_class in metadata"
                        )

                    # Create default instance of nested class
                    nested_config = nested_class()
                else:
                    if not isinstance(field_value, BaseConfig):
                        raise TypeError(
                            f"Nested field '{field_name}' must be an instance of BaseConfig, "
                            f"got {type(field_value)} instead"
                        )

                # Common processing: Get dictionary representation of nested configuration
                nested_dict = nested_config.to_dict(
                    global_section=global_section,
                    module_section=field_name,  # Use field name as nested section name
                    include_none=include_none,
                    include_global_section=include_global_section,
                )

                # Handle global section merging
                if global_section in nested_dict and nested_dict[global_section]:
                    # Merge global section content
                    result[global_section].update(nested_dict[global_section])

                # Create nested structure directly in module section
                if field_name in nested_dict:
                    result[module_section][field_name] = nested_dict[field_name]

        # Clean up empty sections (may occur when include_none=False)
        if not include_none:
            if (
                global_section in result
                and not result[global_section]
                and not include_global_section
            ):
                del result[global_section]

            if not result[module_section]:
                # module section keeps empty dict, don't delete
                pass

        return result

    def _get_type_name(self, type_hint: Any) -> str:
        """Extract type name from type hint"""
        if hasattr(type_hint, "__name__"):
            return type_hint.__name__
        elif hasattr(type_hint, "__origin__"):
            # Handle Optional, Union, etc.
            origin = type_hint.__origin__
            if origin is type(None):
                return "None"
            return getattr(origin, "__name__", str(type_hint))
        else:
            type_str = str(type_hint)
            # Extract from string like "<class 'int'>"
            if "int" in type_str:
                return "int"
            elif "str" in type_str:
                return "str"
            elif "bool" in type_str:
                return "bool"
            elif "float" in type_str:
                return "float"
            elif "list" in type_str:
                return "list"
            return "str"  # Default fallback

    def _get_type_placeholder(self, type_str: str) -> str:
        """Get placeholder value for a type"""
        type_map = {
            "str": '""',
            "int": "0",
            "float": "0.0",
            "bool": "false",
            "list": "[]",
        }
        return type_map.get(type_str, '""')

    def _is_nested_config(self, value: Any) -> bool:
        """Check if a value is a nested config (BaseConfig instance)"""
        return isinstance(value, BaseConfig)

    def _get_field_metadata(self, section_path: str, field_name: str) -> dict[str, Any]:
        """
        Get field metadata with support for nested paths

        Args:
            section_path: Section path like "database" or "database.auth"
            field_name: Field name to look up

        Returns:
            Dict with 'type', 'scope', 'required' keys
        """
        # Parse path to find the correct config class
        path_parts = section_path.split(".")
        current_class = self.__class__

        # Navigate through nested structures
        for part in path_parts[:-1]:
            found = False
            for f in fields(current_class):
                if f.name == part:
                    nested_class = f.metadata.get("nested_class")
                    if nested_class:
                        current_class = nested_class
                        found = True
                        break
            if not found:
                break

        # Find the field in current class
        for f in fields(current_class):
            if f.name == field_name:
                return {
                    "type": self._get_type_name(f.type),
                    "scope": f.metadata.get("param_scope", ParamScope.LOCAL),
                    "required": f.metadata.get("required", False),
                }

        # Default fallback
        return {"type": "str", "scope": ParamScope.LOCAL, "required": False}

    def _format_field_comment(self, key: str, value: Any, meta: dict[str, Any]) -> str:
        """
        Format field comment: type | scope | [required/optional] | [default: value]

        Args:
            key: Field name
            value: Field value (None for unset fields)
            meta: Field metadata dict

        Returns:
            Formatted comment string
        """
        parts = []

        # Type
        parts.append(meta.get("type", "str"))

        # Scope
        scope = meta.get("scope", ParamScope.LOCAL)
        parts.append(scope.name)

        # Required/Optional status (only for None fields)
        if value is None:
            required = meta.get("required", False)
            parts.append("required" if required else "optional")
        # Default value (only for non-None, non-empty fields)
        elif value not in (None, "", 0, False, []):
            parts.append(f"default: {value}")

        return " | ".join(parts)

    def _dict_to_toml_with_comments(
        self, data: dict[str, Any], show_comments: bool = True, parent_path: str = ""
    ) -> str:
        """
        Generate TOML string with comments for None fields

        Args:
            data: Configuration dictionary
            show_comments: Whether to show metadata comments
            parent_path: Parent path for nested sections (e.g., "database.auth")

        Returns:
            TOML formatted string with comments
        """
        lines: list[str] = []

        for section_name, section_data in data.items():
            if not isinstance(section_data, dict):
                continue

            # Skip completely empty sections
            if not section_data:
                continue

            # Build full section path
            full_path = f"{parent_path}.{section_name}" if parent_path else section_name

            # Section header
            lines.append(f"[{full_path}]")

            # Separate fields: valued / None / nested configs
            valued_fields: dict[str, Any] = {}
            none_info: list[tuple[str, dict[str, Any]]] = []
            nested_configs: dict[str, Any] = {}

            for key, value in section_data.items():
                if value is None:
                    # Get metadata immediately for None fields
                    meta = self._get_field_metadata(full_path, key)
                    none_info.append((key, meta))
                elif self._is_nested_config(value):
                    # Nested BaseConfig instance - handle separately
                    nested_configs[key] = value
                elif isinstance(value, dict):
                    # Check if dict contains nested configs
                    if any(self._is_nested_config(v) for v in value.values()):
                        nested_configs[key] = value
                    else:
                        valued_fields[key] = value
                else:
                    valued_fields[key] = value

            # 1. Process valued fields with tomlkit
            if valued_fields:
                valued_toml = tomlkit.dumps(valued_fields).strip()

                # Add comments to each line if requested
                for line in valued_toml.split("\n"):
                    if "=" in line and not line.strip().startswith("#"):
                        key = line.split("=")[0].strip()
                        # Handle quoted keys
                        key = key.strip('"').strip("'")

                        if show_comments:
                            meta = self._get_field_metadata(full_path, key)
                            value = valued_fields.get(key)
                            comment = self._format_field_comment(key, value, meta)
                            lines.append(f"{line}  # {comment}")
                        else:
                            lines.append(line)
                    else:
                        lines.append(line)

            # 2. Process None fields (commented placeholders)
            if none_info:
                if valued_fields:
                    lines.append("")  # Blank line separator

                for key, meta in none_info:
                    placeholder = self._get_type_placeholder(meta["type"])

                    if show_comments:
                        comment = self._format_field_comment(key, None, meta)
                        lines.append(f"# {key} = {placeholder}  # {comment}")
                    else:
                        lines.append(f"# {key} = {placeholder}")

            lines.append("")  # Blank line after section

            # 3. Recursively process nested configs
            for nested_key, nested_value in nested_configs.items():
                if self._is_nested_config(nested_value):
                    # Single nested config
                    nested_dict = nested_value.to_dict(
                        global_section="",  # Don't include global in nested
                        module_section=nested_key,
                        include_none=True,
                    )
                    # Recursively generate
                    nested_toml = self._dict_to_toml_with_comments(
                        nested_dict, show_comments=show_comments, parent_path=full_path
                    )
                    lines.append(nested_toml)
                elif isinstance(nested_value, dict):
                    # Dict of nested configs (from merge)
                    nested_toml = self._dict_to_toml_with_comments(
                        {nested_key: nested_value},
                        show_comments=show_comments,
                        parent_path=full_path,
                    )
                    lines.append(nested_toml)

        return "\n".join(lines)

    def to_toml(
        self,
        path: str | None = None,
        global_section: str = "global",
        module_section: str | None = None,
        as_template: bool = False,
        show_comments: bool = True,
        **kwargs,
    ) -> None:
        """
        Save configuration as a TOML file.

        This method supports two modes:
        - Standard mode: Saves only fields with values, using tomlkit
        - Template mode: Includes None fields as commented placeholders with metadata

        Args:
            path: Output file path. If None, generates filename from class name (default: None)
            global_section: Name for the global section (default: "global")
            module_section: Name for the module section. If None, derived from class name (default: None)
            as_template: Generate template with None fields as comments (default: False)
            show_comments: Show metadata comments (type, scope, required, default) (default: True)
            **kwargs: Additional arguments passed to to_dict()

        Raises:
            ValueError: If unable to write the TOML file

        Examples:
            >>> # Standard save
            >>> config.to_toml("config.toml")

            >>> # Save with metadata comments
            >>> config.to_toml("config.toml", show_comments=True)

            >>> # Generate template
            >>> config.to_toml("template.toml", as_template=True)

            >>> # Generate template with full documentation
            >>> config.to_toml("template.toml", as_template=True, show_comments=True)
        """
        final_path: Path
        if path is None:
            # Automatically generate filename based on class name
            class_name = self.__class__.__name__
            filename = class_name.lower().replace("config", "") + ".toml"
            final_path = Path(filename)
        else:
            final_path = Path(path)

        # Ensure directory exists
        final_path.parent.mkdir(parents=True, exist_ok=True)

        if as_template:
            # Template mode: manually generate with comments
            data_dict = self.to_dict(
                global_section=global_section,
                module_section=module_section,
                include_none=True,
                **kwargs,
            )
            content = self._dict_to_toml_with_comments(
                data_dict, show_comments=show_comments
            )

            try:
                final_path.write_text(content, encoding="utf-8")
            except Exception as e:
                raise ValueError(f"Unable to save TOML config to {path}: {e}")
        else:
            # Standard mode: use tomlkit, skip None fields
            data_dict = self.to_dict(
                global_section=global_section,
                module_section=module_section,
                include_none=False,
                **kwargs,
            )

            if show_comments:
                # Add comments to standard output
                content = self._dict_to_toml_with_comments(
                    data_dict, show_comments=True
                )
                try:
                    final_path.write_text(content, encoding="utf-8")
                except Exception as e:
                    raise ValueError(f"Unable to save TOML config to {path}: {e}")
            else:
                # No comments, pure tomlkit output
                try:
                    with open(final_path, "w", encoding="utf-8") as f:
                        tomlkit.dump(data_dict, f)
                except Exception as e:
                    raise ValueError(f"Unable to save TOML config to {path}: {e}")

    def to_flat_toml(
        self,
        path: str | None = None,
        global_section: str = "global",
        show_comments: bool = True,
        **kwargs,
    ) -> None:
        """
        Save configuration as a flattened TOML file.

        This method is designed for merged configurations created by the merge() or combine()
        methods. It flattens the top-level nested structure, promoting nested config sections
        to the top level.

        For example, a merged config with structure:
            [mergedconfig]
              [mergedconfig.database]
              [mergedconfig.cache]

        Will be flattened to:
            [database]
            [cache]

        Args:
            path: Output file path. If None, generates filename from class name
            global_section: Name of the global section (default: "global")
            show_comments: Whether to add metadata comments to fields (default: True)
            **kwargs: Additional arguments passed to to_dict()

        Raises:
            ValueError: If called on a non-merged configuration

        Note:
            This method only flattens the merge-generated wrapper. User-defined
            nested_param fields within each config are preserved.
        """
        if not getattr(self, "_is_merged", False):
            raise ValueError(
                "to_flat_toml() can only be used on merged configurations created by "
                "merge() or combine() methods. For regular configs, use to_toml() instead."
            )

        # Get the full nested structure
        data_dict = self.to_dict(
            global_section=global_section,
            module_section=None,  # Let it use class name
            **kwargs,
        )

        # Flatten: extract nested configs and promote them to top level
        flattened_dict: dict[str, Any] = {}

        # First, copy the global section if it exists
        if global_section in data_dict:
            flattened_dict[global_section] = data_dict[global_section]

        # Find the wrapper section (the merged config's own section)
        wrapper_section = None
        for key in data_dict.keys():
            if key != global_section:
                wrapper_section = key
                break

        if wrapper_section and isinstance(data_dict[wrapper_section], dict):
            # Extract all nested sections from the wrapper
            for nested_key, nested_value in data_dict[wrapper_section].items():
                if isinstance(nested_value, dict):
                    # This is a nested config, promote it to top level
                    flattened_dict[nested_key] = nested_value
                else:
                    # This is a direct field (shouldn't happen in merged configs, but handle it)
                    if wrapper_section not in flattened_dict:
                        flattened_dict[wrapper_section] = {}
                    flattened_dict[wrapper_section][nested_key] = nested_value

        final_path: Path
        if path is None:
            # Automatically generate filename
            class_name = self.__class__.__name__
            filename = class_name.lower().replace("config", "") + "_flat.toml"
            final_path = Path(filename)
        else:
            final_path = Path(path)

        # Ensure directory exists
        final_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(final_path, "w", encoding="utf-8") as f:
                if show_comments:
                    # Use custom serialization with comments
                    toml_str = self._dict_to_toml_with_comments(
                        flattened_dict, show_comments=True, parent_path=""
                    )
                    f.write(toml_str)
                else:
                    # Use standard tomlkit serialization
                    tomlkit.dump(flattened_dict, f)
        except Exception as e:
            raise ValueError(f"Unable to save flattened TOML config to {path}: {e}")

    @classmethod
    def merge(
        cls, configs: dict[str, Self] | list[Self], merged_name: str = "MergedConfig"
    ) -> Self:
        """
        Merge multiple configuration instances into a single combined configuration.

        This method creates a new dynamic configuration class that contains all input
        configurations as nested fields. Each configuration becomes a nested_param field
        in the merged result.

        Args:
            configs: Either a dict mapping field names to config instances, or a list of
                    config instances (field names will be derived from class names)
            merged_name: Name for the dynamically created merged class (default: "MergedConfig")

        Returns:
            A new configuration instance containing all input configs as nested fields,
            with _is_merged flag set to True

        Raises:
            TypeError: If configs is not a dict or list, or if any config is not a BaseConfig instance
            ValueError: If field name conflicts occur

        Example:
            >>> db_config = DatabaseConfig(host="localhost")
            >>> cache_config = CacheConfig(ttl=3600)
            >>> merged = Config.merge([db_config, cache_config])
            >>> merged.to_toml("merged.toml")  # Creates nested structure
            >>> merged.to_flat_toml("flat.toml")  # Creates flat structure
        """

        # Collect field definitions
        field_definitions: list[tuple[str, type, Field]] = []
        merged_data: dict[str, Any] = {}
        seen_field_names: set[str] = set()
        merged_raw_data: dict[str, Any] = {}

        # Handle different input types
        if isinstance(configs, dict):
            # For dict form: use dict keys directly as field names
            for field_name, config in configs.items():
                if not isinstance(config, BaseConfig):
                    raise TypeError(
                        f"All configurations must be instances of BaseConfig, got: {type(config)}"
                    )

                # Check field name conflicts
                if field_name in seen_field_names:
                    raise ValueError(
                        f"Field name conflict: '{field_name}' already exists"
                    )
                seen_field_names.add(field_name)

                # Use default_factory to avoid mutable default value problems
                field_definitions.append(
                    (
                        field_name,
                        type(config),
                        nested_param(
                            nested_class=type(config), required=False, default=config
                        ),
                    )
                )
                merged_data[field_name] = config

                # Merge original data
                if hasattr(config, "_raw_data") and config._raw_data:
                    merged_raw_data.update(config._raw_data)

        elif isinstance(configs, list):
            # For list form: use class names as field names (original behavior)
            for config in configs:
                if not isinstance(config, BaseConfig):
                    raise TypeError(
                        f"All configurations must be instances of BaseConfig, got: {type(config)}"
                    )

                # Use configuration class name as field name (DataLoaderConfig -> dataloader)
                field_name = config.__class__.__name__.lower().replace("config", "")

                # Check field name conflicts
                if field_name in seen_field_names:
                    raise ValueError(
                        f"Field name conflict: '{field_name}' already exists"
                    )
                seen_field_names.add(field_name)

                # Use default_factory to avoid mutable default value problems
                field_definitions.append(
                    (
                        field_name,
                        type(config),
                        nested_param(
                            nested_class=type(config), required=False, default=config
                        ),
                    )
                )
                merged_data[field_name] = config

                # Merge original data
                if hasattr(config, "_raw_data") and config._raw_data:
                    merged_raw_data.update(config._raw_data)

        else:
            raise TypeError(
                f"configs must be either dict[str, BaseConfig] or list[BaseConfig], got: {type(configs)}"
            )

        # Dynamically create merged class
        MergedConfig = make_dataclass(
            merged_name,
            field_definitions,
            bases=(BaseConfig,),
            namespace={"__module__": cls.__module__},
        )

        merged_instance = MergedConfig(**merged_data)
        # Save merged original data
        merged_instance._raw_data = merged_raw_data
        # Mark as merged config
        merged_instance._is_merged = True
        return merged_instance

    @classmethod
    def _instantiate_with_nested(cls, config_class: type["BaseConfig"]) -> "BaseConfig":
        """
        Recursively instantiate a config class and all its nested_param fields.

        Args:
            config_class: The BaseConfig subclass to instantiate

        Returns:
            An instance with all nested_param fields recursively instantiated
        """
        # Get all fields from the dataclass
        class_fields = fields(config_class)
        init_kwargs: dict[str, Any] = {}

        for field in class_fields:
            # Check if this is a nested_param field
            metadata = field.metadata
            if metadata.get("param_scope") == ParamScope.NESTED:
                nested_class = metadata.get("nested_class")
                if (
                    nested_class
                    and isinstance(nested_class, type)
                    and issubclass(nested_class, BaseConfig)
                ):
                    # Recursively instantiate the nested class
                    init_kwargs[field.name] = cls._instantiate_with_nested(nested_class)

        # Create instance with nested fields
        return config_class(**init_kwargs)  # type: ignore[return-value]

    @classmethod
    def combine(
        cls,
        configs: dict[str, type[Self]] | list[type[Self]],
        combined_name: str = "CombinedConfig",
    ) -> Self:
        """
        Combine multiple BaseConfig subclass definitions into a single Config instance.

        This method converts each class definition to instances, then merges them using
        the merge() method. Useful for generating TOML templates from multiple config classes.

        Args:
            configs: Either a dict mapping field names to BaseConfig subclasses, or a
                    list of BaseConfig subclasses (field names derived from class names)
            combined_name: Name for the dynamically created combined class (default: "CombinedConfig")

        Returns:
            A new Config instance containing all fields from the input classes,
            with _is_merged flag set to True

        Raises:
            ValueError: If no config classes provided
            TypeError: If any input is not a BaseConfig subclass

        Example:
            >>> class DatabaseConfig(BaseConfig):
            ...     host: str = local_param(default="localhost")
            >>> class CacheConfig(BaseConfig):
            ...     ttl: int = local_param(default=3600)
            >>>
            >>> # Using list (field names from class names)
            >>> config = Config.combine([DatabaseConfig, CacheConfig])
            >>>
            >>> # Using dict (custom field names)
            >>> config = Config.combine({"db": DatabaseConfig, "cache": CacheConfig})
            >>> config.to_flat_toml("template.toml")
        """
        # Handle different input types
        if isinstance(configs, dict):
            if not configs:
                raise ValueError("At least one model class must be provided")

            # Validate that all values are BaseConfig subclasses
            for field_name, model_class in configs.items():
                if not isinstance(model_class, type) or not issubclass(
                    model_class, BaseConfig
                ):
                    raise TypeError(
                        f"All values must be BaseConfig subclasses, got {model_class} for key '{field_name}'"
                    )

            # Create instances from each class with recursive nested instantiation
            config_dict_instances: dict[str, Self] = {}
            for field_name, model_class in configs.items():
                instance = cls._instantiate_with_nested(model_class)
                config_dict_instances[field_name] = instance  # type: ignore[assignment]

            # Use merge to combine all instances
            return cls.merge(config_dict_instances, merged_name=combined_name)

        elif isinstance(configs, list):
            if not configs:
                raise ValueError("At least one model class must be provided")

            # Validate that all inputs are BaseConfig subclasses
            for model_class in configs:
                if not isinstance(model_class, type) or not issubclass(
                    model_class, BaseConfig
                ):
                    raise TypeError(
                        f"All arguments must be BaseConfig subclasses, got: {model_class}"
                    )

            # Create instances from each class with recursive nested instantiation
            config_list_instances: list[Self] = []
            for model_class in configs:
                instance = cls._instantiate_with_nested(model_class)
                config_list_instances.append(instance)  # type: ignore[arg-type]

            # Use merge to combine all instances
            return cls.merge(config_list_instances, merged_name=combined_name)

        else:
            raise TypeError(
                f"model_classes must be either dict[str, type[BaseConfig]] or list[type[BaseConfig]], got: {type(configs)}"
            )
