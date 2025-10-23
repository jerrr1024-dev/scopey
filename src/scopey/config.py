import copy
import warnings
from dataclasses import MISSING, Field, dataclass, field, fields, make_dataclass
from enum import Enum, auto
from pathlib import Path
from typing import (
    Any,
    Dict,
    ForwardRef,
    List,
    Optional,
    Self,
    Set,
    Tuple,
    Type,
    Union,
    get_args,
    get_origin,
)

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
        path: Union[str, Path],
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
            enable_default_override: Whether to allow TOML values to override
                field defaults. Defaults to True.
            warn_on_override: Whether to warn when priority-based parameter
                override occurs. Defaults to True.

        Returns:
            A new instance of the configuration class with values loaded from the
            TOML file

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
        path: Union[str, Path],
        sections: Dict[str, Type["BaseConfig"]],
        global_section: str = "global",
        merged_name: str = "MergedConfig",
        enable_default_override: bool = True,
        warn_on_override: bool = True,
    ) -> Self:
        """
        Create a merged configuration instance from a flat TOML file.

        This method is the inverse of to_flat_toml(). It reads a flat TOML structure
        where multiple configurations are at the top level. Each section is
        instantiated with its matching config class, then merged into one
        configuration.

        Args:
            path: Path to the flat TOML file (must have .toml extension)
            sections: Mapping of section names to BaseConfig classes.
                Example: {"database": DatabaseConfig, "cache": CacheConfig}
            global_section: Name of the global section (default: "global")
            merged_name: Name for the dynamically created merged class
                (default: "MergedConfig")
            enable_default_override: Whether to allow TOML values to override
                field defaults. Defaults to True.
            warn_on_override: Whether to warn when priority-based parameter
                override occurs. Defaults to True.

        Returns:
            A merged configuration instance with _is_merged flag set to True

        Raises:
            ValueError: If the file cannot be loaded or a specified section isn't found
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
                    f"Section '{section_name}' must be a BaseConfig subclass, "
                    f"got: {config_class}"
                )

        try:
            with open(file=path, mode="r", encoding="utf-8") as f:
                toml_data = tomlkit.load(f)
        except Exception as e:
            raise ValueError(f"Cannot load TOML config from {path}: {e}")

        # Instantiate each section with its corresponding class
        config_instances: Dict[str, Self] = {}
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
            # type: ignore[assignment]
            config_instances[section_name] = config_instance

        # Merge all instances into a single configuration
        return cls.merge(config_instances, merged_name=merged_name)

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        module_section: str,
        global_section: str = "global",
        enable_default_override: bool = True,
        warn_on_override: bool = True,
    ) -> Self:
        """
        Create a configuration instance from a dictionary.

        This method handles the complex logic of mapping dictionary data to
        configuration fields based on their parameter scopes (GLOBAL, LOCAL,
        NESTED, etc.).

        Args:
            data: Dictionary containing configuration data, typically with
                global and module sections
            module_section: Name of the module-specific section to read from
            global_section: Name of the global section (default: "global")
            enable_default_override: Whether to allow dict values to override
                field defaults. Defaults to True.
            warn_on_override: Whether to warn when priority-based parameter
                override occurs. Defaults to True.

        Returns:
            A new instance of the configuration class populated with data from
            the dict

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
                f"Can not find section '{module_section}' from available "
                f"sections: {list(data.keys())}"
            )

        params = {}
        for f in fields(cls):
            field_name = f.name
            scope = f.metadata.get("param_scope")
            required = f.metadata.get("required", False)

            if scope is None:
                raise ValueError(
                    f"Field '{field_name}' in {cls.__name__} must specify "
                    "param_scope. Use global_param(), local_param(), "
                    "nested_param(), etc."
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
        # type: ignore[assignment]
        instance._raw_data = copy.deepcopy(data)
        return instance

    @classmethod
    def get_param_value(
        cls,
        data: Dict[str, Any],
        field_name: str,
        scope: ParamScope,
        global_section: str,
        module_section: str,
        warn_on_override: bool,
        required: bool = True,
        nested_class: Optional[Type["BaseConfig"]] = None,
    ) -> Optional[Any]:
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
                    f"Parameter '{field_name}' is marked as GLOBAL and required, "
                    f"but not found in global section '{global_section}'"
                )
            if module_value is not None:
                raise ValueError(
                    f"Parameter '{field_name}' is marked as GLOBAL, cannot be set "
                    f"in local section '{module_section}'"
                )
            return global_value
        elif scope == ParamScope.LOCAL:
            if module_value is None and required:
                raise ValueError(
                    f"Parameter '{field_name}' is marked as LOCAL and required, "
                    f"but not found in local section '{module_section}'"
                )
            if global_value is not None:
                raise ValueError(
                    f"Parameter '{field_name}' is marked as LOCAL, cannot be set "
                    f"in global section '{global_section}'"
                )
            return module_value
        elif scope in [ParamScope.GLOBAL_FIRST, ParamScope.LOCAL_FIRST]:
            # Handle priority logic: GLOBAL_FIRST prioritizes global, LOCAL_FIRST
            # prioritizes local.
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
                        (
                            f"Parameter '{field_name}' uses {primary_section} "
                            f"section value {primary_value}, ignoring "
                            f"{secondary_section} section value {secondary_value}"
                        ),
                        UserWarning,
                    )
                return primary_value
            elif secondary_value is not None:
                return secondary_value
            elif required:
                scope_name = "GLOBAL_FIRST" if is_global_first else "LOCAL_FIRST"
                raise ValueError(
                    f"Parameter '{field_name}' is marked as {scope_name} and "
                    "required, but not found in either global section "
                    f"'{global_section}' or local section '{module_section}'"
                )
            return None
        elif scope == ParamScope.NESTED:
            # NESTED scope processing logic - search in module section for nested data
            module_data = data.get(module_section, {})
            nested_data = module_data.get(field_name)

            if nested_data is None:
                if required:
                    raise ValueError(
                        f"Nested parameter '{field_name}' is required, but not "
                        f"found in section '{module_section}'"
                    )
                return None

            if nested_class is None:
                raise ValueError(
                    f"Nested parameter '{field_name}' missing nested_class"
                )

            # Create temporary data structure for nested class use.
            # Treat nested_data as the module section content for the nested class.
            if not isinstance(nested_data, dict):
                raise TypeError(
                    f"Nested section '{module_section}.{field_name}' must be a "
                    f"dict, got {type(nested_data)}"
                )

            tmp_data: Dict[str, Any] = {field_name: nested_data}
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

        This method is called automatically during instance creation via
        from_dict() and from_toml(). It checks every field marked
        required=True and ensures it has been assigned a value.

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

        This method is called automatically during instance initialization in
        __post_init__, after _raw_data and _is_merged are initialized.

        Example:
            >>> class MyConfig(BaseConfig):
            ...     port: int = local_param(default=8080)
            ...
            ...     def validate(self):
            ...         if self.port < 1 or self.port > 65535:
            ...             raise ValueError(f"Invalid port: {self.port}")
        """
        pass

    @dataclass
    class _GlobalParamConflictTracker:
        active: bool
        owner: "BaseConfig"
        registry: Dict[str, Dict[str, str]] = field(default_factory=dict)

        def register(
            self, param_name: str, metadata: Dict[str, Any], source: str
        ) -> None:
            if not self.active:
                return

            param_type = metadata.get("type", "str")
            existing = self.registry.get(param_name)

            if existing:
                if not self.owner._is_type_compatible(existing["type"], param_type):
                    raise ValueError(
                        f"Global parameter '{param_name}' has conflicting type "
                        "definitions:\n"
                        f"  - In '{existing['source']}': type={existing['type']}\n"
                        f"  - In '{source}': type={param_type}\n"
                        "Please ensure all configs define the same global "
                        "parameters with compatible types."
                    )
            else:
                self.registry[param_name] = {"type": param_type, "source": source}

    def to_dict(
        self,
        global_section: str = "global",
        module_section: Optional[str] = None,
        include_none: bool = True,
        include_global_section: bool = True,
        include_metadata: bool = False,
    ) -> Dict[str, Any]:
        """
        Convert configuration instance to a dictionary representation.

        This method creates a structured dictionary with separate global and
        module sections, respecting parameter scopes and handling nested
        configurations recursively.

        Args:
            global_section: Name for the global section (default: "global")
            module_section: Name for the module section. If None, derived from
                class name (default: None)
            include_none: Whether to include fields with None values (default: True)
            include_global_section: Whether to include global section in output
                (default: True)
            include_metadata: Whether to include field metadata (type, scope,
                etc.) (default: False)

        Returns:
            Dictionary with structure: {global_section: {...}, module_section: {...}}

            When include_metadata=True, each field value is wrapped as:
            {field_name: {"_value": value, "_metadata": {...}}}

        Example:
            >>> config = MyConfig(host="localhost", port=8080)
            >>> config.to_dict()
            {'global': {'host': 'localhost'}, 'mymodule': {'port': 8080}}

            >>> config.to_dict(include_metadata=True)
            {'global': {'host': {'_value': 'localhost', '_metadata': {...}}}, ...}
        """

        if module_section is None:
            module_section = self.__class__.__name__.lower().replace("config", "")

        result: Dict[str, Any] = {}

        # Decide whether to create global section based on parameter
        if include_global_section:
            result[global_section] = {}

        result[module_section] = {}

        conflict_tracker = self._GlobalParamConflictTracker(
            active=getattr(self, "_is_merged", False) and include_metadata, owner=self
        )

        for f in fields(self):
            field_name = f.name
            field_value = getattr(self, field_name)
            scope = f.metadata.get("param_scope")

            # Manually control whether to include None values
            if field_value is None and not include_none:
                continue

            # Prepare metadata if requested
            if include_metadata:
                # Get default value from field
                default_val = (
                    f.default
                    if f.default is not MISSING
                    else (
                        f.default_factory()
                        if f.default_factory is not MISSING
                        else None
                    )
                )

                field_metadata = {
                    "type": self._get_type_name(f.type),
                    "scope": scope,
                    "required": f.metadata.get("required", False),
                    "default": default_val,
                }

            if scope in [ParamScope.GLOBAL, ParamScope.GLOBAL_FIRST]:
                if global_section not in result:
                    result[global_section] = {}
                if include_metadata:
                    result[global_section][field_name] = {
                        "_value": field_value,
                        "_metadata": field_metadata,
                    }
                else:
                    result[global_section][field_name] = field_value
            elif scope in [ParamScope.LOCAL, ParamScope.LOCAL_FIRST]:
                if include_metadata:
                    result[module_section][field_name] = {
                        "_value": field_value,
                        "_metadata": field_metadata,
                    }
                else:
                    result[module_section][field_name] = field_value
            elif scope == ParamScope.NESTED:
                # Determine the nested config instance to process
                nested_config = field_value

                if field_value is None:
                    # If the nested field is None, create a default instance.
                    # Get the nested class directly from field metadata
                    nested_class = f.metadata.get("nested_class")

                    if nested_class is None:
                        raise ValueError(
                            f"Nested field '{field_name}' is missing "
                            "nested_class in metadata"
                        )

                    # Create default instance of nested class
                    nested_config = nested_class()
                else:
                    if not isinstance(field_value, BaseConfig):
                        raise TypeError(
                            f"Nested field '{field_name}' must be an instance "
                            f"of BaseConfig, got {type(field_value)} instead"
                        )

                # Convert nested configuration to dictionary representation
                nested_dict = nested_config.to_dict(
                    global_section=global_section,
                    module_section=field_name,  # Use field name as nested section name
                    include_none=include_none,
                    include_global_section=include_global_section,
                    include_metadata=include_metadata,  # Propagate metadata flag
                )

                # Handle global section merging
                if global_section in nested_dict and nested_dict[global_section]:
                    if include_metadata:
                        for param_name, param_data in nested_dict[
                            global_section
                        ].items():
                            if (
                                isinstance(param_data, dict)
                                and "_metadata" in param_data
                            ):
                                conflict_tracker.register(
                                    param_name,
                                    param_data["_metadata"],
                                    source=field_name,
                                )

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
        if type_hint is None or type_hint is type(None):
            return "None"

        origin = get_origin(type_hint)
        if origin is None:
            if isinstance(type_hint, ForwardRef):
                return type_hint.__forward_arg__.split(".")[-1]

            if isinstance(type_hint, str):
                # Forward reference stored as string literal
                return type_hint.split(".")[-1].strip("'\"")

            if isinstance(type_hint, type):
                return type_hint.__name__

            # Fallback to string representation
            type_str = str(type_hint).strip("'\"")
            if "." in type_str:
                type_str = type_str.split(".")[-1]
            return type_str

        if origin is Union:
            args = [arg for arg in get_args(type_hint) if arg is not type(None)]
            if args:
                return self._get_type_name(args[0])
            return "None"

        if origin in (list, List):
            return "list"
        if origin in (dict, Dict):
            return "dict"
        if origin in (tuple, Tuple):
            return "tuple"
        if origin in (set, Set):
            return "set"
        if getattr(origin, "__qualname__", "") == "Annotated":
            annotated_args = get_args(type_hint)
            if annotated_args:
                return self._get_type_name(annotated_args[0])

        origin_name = getattr(origin, "__name__", None)
        if origin_name:
            return origin_name

        return str(origin)

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

    def _contains_metadata_dict(
        self, value: Any, memo: Optional[Dict[int, bool]] = None
    ) -> bool:
        """
        Detect metadata placeholder dictionaries of the form
        {'_value': ..., '_metadata': ...}. We treat any dict containing this shape
        (including nested occurrences) as metadata so it won't be serialized
        directly by tomlkit.
        """
        if not isinstance(value, dict):
            return False

        if memo is None:
            memo = {}

        key = id(value)
        if key in memo:
            return memo[key]

        if "_value" in value and "_metadata" in value:
            memo[key] = True
            return True

        for child in value.values():
            if isinstance(child, dict) and self._contains_metadata_dict(child, memo):
                memo[key] = True
                return True

        memo[key] = False
        return False

    def _split_section_entries(
        self, section_data: Dict[str, Any], section_path: str
    ) -> Tuple[
        Dict[str, Any],
        Dict[str, Dict[str, Any]],
        List[Tuple[str, Dict[str, Any]]],
        Dict[str, Any],
    ]:
        """
        Split section entries into valued, None, and nested categories while
        preserving metadata.

        Args:
            section_data: Section dictionary produced by to_dict()
            section_path: Dotted path for metadata lookups (e.g., "app.database")

        Returns:
            A tuple of (plain_values, metadata_cache, none_entries,
            nested_entries)
        """
        plain_values: Dict[str, Any] = {}
        metadata_cache: Dict[str, Dict[str, Any]] = {}
        none_entries: List[Tuple[str, Dict[str, Any]]] = []
        nested_entries: Dict[str, Any] = {}
        metadata_presence: Dict[int, bool] = {}

        for key, value in section_data.items():
            if isinstance(value, dict) and "_value" in value and "_metadata" in value:
                actual_value = value["_value"]
                meta = value["_metadata"]

                if actual_value is None:
                    none_entries.append((key, meta))
                elif self._is_nested_config(actual_value):
                    nested_entries[key] = actual_value
                elif isinstance(actual_value, dict):
                    has_nested = False
                    has_none = False
                    for child in actual_value.values():
                        if not has_nested and self._is_nested_config(child):
                            has_nested = True
                        if not has_none and child is None:
                            has_none = True
                        if has_nested and has_none:
                            break
                    has_metadata = self._contains_metadata_dict(
                        actual_value, metadata_presence
                    )

                    if has_nested or has_none or has_metadata:
                        nested_entries[key] = actual_value
                    else:
                        plain_values[key] = actual_value
                        metadata_cache[key] = meta
                else:
                    plain_values[key] = actual_value
                    metadata_cache[key] = meta
            elif value is None:
                meta = self._get_field_metadata(section_path, key)
                none_entries.append((key, meta))
            elif self._is_nested_config(value):
                nested_entries[key] = value
            elif isinstance(value, dict):
                has_nested = False
                has_none = False
                for child in value.values():
                    if not has_nested and self._is_nested_config(child):
                        has_nested = True
                    if not has_none and child is None:
                        has_none = True
                    if has_nested and has_none:
                        break
                has_metadata = self._contains_metadata_dict(value, metadata_presence)

                if has_nested or has_none or has_metadata:
                    nested_entries[key] = value
                else:
                    plain_values[key] = value
            else:
                plain_values[key] = value

        return plain_values, metadata_cache, none_entries, nested_entries

    def _is_type_compatible(self, type1: str, type2: str) -> bool:
        """
        Check if two type strings are compatible.

        Args:
            type1: First type string (e.g., "int", "float", "str")
            type2: Second type string

        Returns:
            True if types are the same, False otherwise
        """
        return type1 == type2

    def _get_field_metadata(self, section_path: str, field_name: str) -> Dict[str, Any]:
        """
        Get field metadata with support for nested paths

        Args:
            section_path: Section path such as "database",
                "combinedconfig.database", or "database.auth"
            field_name: Field name to look up

        Returns:
            Dict with 'type', 'scope', 'required' keys
        """
        # Parse path to find the correct config class
        path_parts = [p for p in section_path.split(".") if p]  # Remove empty parts
        current_class = self.__class__
        current_instance = self

        # Navigate through the path to find the target class
        for i, part in enumerate(path_parts):
            found = False

            # Try to find this part as a nested field in current class
            for f in fields(current_class):
                if f.name.lower() == part.lower():
                    nested_class = f.metadata.get("nested_class")
                    if nested_class:
                        # Found a nested config, update current class
                        current_class = nested_class

                        # Try to get the actual instance if available
                        if hasattr(current_instance, f.name):
                            attr_value = getattr(current_instance, f.name)
                            if isinstance(attr_value, BaseConfig):
                                current_instance = attr_value

                        found = True
                        break

            if not found:
                # This part might be a generated section name (like "combinedconfig")
                # Continue to next part
                pass

        # Now search for the field in the current class
        for f in fields(current_class):
            if f.name == field_name:
                # Get the actual default value from field
                default_val = (
                    f.default
                    if f.default is not MISSING
                    else (
                        f.default_factory()
                        if f.default_factory is not MISSING
                        else None
                    )
                )

        return {
            "type": self._get_type_name(f.type),
            "scope": f.metadata.get("param_scope", ParamScope.LOCAL),
            "required": f.metadata.get("required", False),
            "default": default_val,
        }

        # Default fallback
        return {
            "type": "str",
            "scope": ParamScope.LOCAL,
            "required": False,
            "default": None,
        }

    def _format_field_comment(self, key: str, value: Any, meta: Dict[str, Any]) -> str:
        """
        Format field comment: type | scope | [required/optional] | [default: value]

        Args:
            key: Field name
            value: Field value (None for unset fields)
            meta: Field metadata dict

        Returns:
            Formatted comment string
        """
        parts: List[str] = []

        # Type
        parts.append(meta.get("type", "str"))

        # Scope
        scope = meta.get("scope", ParamScope.LOCAL)
        parts.append(scope.name)

        # Required/Optional status (only for None fields)
        if value is None:
            required = meta.get("required", False)
            parts.append("required" if required else "optional")

        # Default value (always derived from metadata to preserve falsy literals)
        default_meta = meta.get("default", MISSING)
        if default_meta is not MISSING:
            formatted_default = self._format_default_value(default_meta)
            if formatted_default is not None:
                parts.append(f"default: {formatted_default}")

        return " | ".join(parts)

    def _format_default_value(self, default: Any) -> Optional[str]:
        """Convert stored default metadata into a human-readable string."""
        if default is None:
            return None

        if isinstance(default, str):
            return default if default else '""'

        if isinstance(default, bool):
            return "True" if default else "False"

        return str(default)

    def _render_plain_field_lines(
        self,
        plain_fields: Dict[str, Any],
        metadata_cache: Dict[str, Dict[str, Any]],
        full_path: str,
        show_comments: bool,
    ) -> List[str]:
        if not plain_fields:
            return []

        rendered_lines: List[str] = []
        valued_toml = tomlkit.dumps(plain_fields).strip()

        for line in valued_toml.split("\n"):
            if "=" in line and not line.strip().startswith("#"):
                key = line.split("=")[0].strip().strip('"').strip("'")

                if show_comments:
                    meta = metadata_cache.get(key)
                    if meta is None:
                        meta = self._get_field_metadata(full_path, key)
                    else:
                        # metadata from to_dict may omit defaults if serialized externally;
                        # fall back to dataclass introspection so comments remain complete.
                        if meta.get("default", MISSING) is MISSING:
                            fallback_meta = self._get_field_metadata(full_path, key)
                            if fallback_meta:
                                # merge while preserving existing entries
                                merged_meta = fallback_meta.copy()
                                merged_meta.update(meta)
                                meta = merged_meta

                    actual_value = plain_fields.get(key)
                    comment = self._format_field_comment(key, actual_value, meta)
                    rendered_lines.append(f"{line}  # {comment}")
                else:
                    rendered_lines.append(line)
            else:
                rendered_lines.append(line)

        return rendered_lines

    def _render_none_placeholder_lines(
        self,
        none_info: List[Tuple[str, Dict[str, Any]]],
        show_comments: bool,
        prepend_blank: bool,
    ) -> List[str]:
        if not none_info:
            return []

        lines: List[str] = []
        if prepend_blank:
            lines.append("")

        for key, meta in none_info:
            placeholder = self._get_type_placeholder(meta["type"])

            if show_comments:
                comment = self._format_field_comment(key, None, meta)
                lines.append(f"# {key} = {placeholder}  # {comment}")
            else:
                lines.append(f"# {key} = {placeholder}")

        return lines

    def _render_nested_sections(
        self,
        nested_configs: Dict[str, Any],
        full_path: str,
        show_comments: bool,
    ) -> List[str]:
        rendered: List[str] = []

        for nested_key, nested_value in nested_configs.items():
            if self._is_nested_config(nested_value):
                nested_dict = nested_value.to_dict(
                    global_section="",
                    module_section=nested_key,
                    include_none=True,
                    include_metadata=True,
                )
                rendered.append(
                    self._dict_to_toml_with_comments(
                        nested_dict, show_comments=show_comments, parent_path=full_path
                    )
                )
            elif isinstance(nested_value, dict):
                rendered.append(
                    self._dict_to_toml_with_comments(
                        {nested_key: nested_value},
                        show_comments=show_comments,
                        parent_path=full_path,
                    )
                )

        return rendered

    def _render_section_lines(
        self,
        full_path: str,
        plain_fields: Dict[str, Any],
        metadata_cache: Dict[str, Dict[str, Any]],
        none_info: List[Tuple[str, Dict[str, Any]]],
        show_comments: bool,
    ) -> List[str]:
        section_lines: List[str] = [f"[{full_path}]"]

        plain_lines = self._render_plain_field_lines(
            plain_fields, metadata_cache, full_path, show_comments
        )
        section_lines.extend(plain_lines)

        none_lines = self._render_none_placeholder_lines(
            none_info, show_comments, prepend_blank=bool(plain_lines)
        )
        section_lines.extend(none_lines)

        section_lines.append("")
        return section_lines

    def _dict_to_toml_with_comments(
        self, data: Dict[str, Any], show_comments: bool = True, parent_path: str = ""
    ) -> str:
        """
        Generate a TOML string with comments for None fields.

        Args:
            data: Configuration dictionary that may include metadata produced by
                to_dict(include_metadata=True)
            show_comments: Whether to include metadata comments
            parent_path: Parent path for nested sections (e.g., "database.auth")

        Returns:
            TOML formatted string with comments
        """
        lines: List[str] = []

        for section_name, section_data in data.items():
            if not isinstance(section_data, dict):
                continue

            # Skip completely empty sections
            if not section_data:
                continue

            # Build full section path
            if parent_path:
                full_path = f"{parent_path}.{section_name}"
            else:
                full_path = section_name

            # Separate fields: valued / None / nested configs
            (
                plain_valued_fields,
                metadata_cache,
                none_info,
                nested_configs,
            ) = self._split_section_entries(section_data, full_path)

            lines.extend(
                self._render_section_lines(
                    full_path,
                    plain_valued_fields,
                    metadata_cache,
                    none_info,
                    show_comments,
                )
            )

            lines.extend(
                self._render_nested_sections(
                    nested_configs, full_path=full_path, show_comments=show_comments
                )
            )

        return "\n".join(lines)

    def to_toml(
        self,
        path: Optional[str] = None,
        global_section: str = "global",
        module_section: Optional[str] = None,
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
            path: Output file path. If None, generates filename from class name
                (default: None)
            global_section: Name for the global section (default: "global")
            module_section: Name for the module section. If None, derived from
                class name (default: None)
            as_template: Generate template with None fields as comments
                (default: False)
            show_comments: Show metadata comments (type, scope, required,
                default) (default: True)
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
                include_metadata=show_comments,  # Mirror comment flag
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
                include_metadata=show_comments,  # Mirror comment flag
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
        path: Optional[str] = None,
        global_section: str = "global",
        as_template: bool = False,
        show_comments: bool = True,
        **kwargs,
    ) -> None:
        """
        Save configuration as a flattened TOML file.

        This method is designed for merged configurations created by the
        merge() or combine() methods. It flattens the top-level nested
        structure, promoting nested config sections to the top level.

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
            as_template: Generate template with None fields as comments
                (default: False)
            show_comments: Whether to add metadata comments to fields
                (default: True)
            **kwargs: Additional arguments passed to to_dict()

        Raises:
            ValueError: If called on a non-merged configuration

        Note:
            This method only flattens the merge-generated wrapper. User-defined
            nested_param fields within each config are preserved.
        """
        if not getattr(self, "_is_merged", False):
            raise ValueError(
                "to_flat_toml() can only be used on merged configurations created "
                "by merge() or combine() methods. For regular configs, use "
                "to_toml() instead."
            )

        # Get the full nested structure
        data_dict = self.to_dict(
            global_section=global_section,
            module_section=None,  # Let it use class name
            include_none=as_template,  # Include None fields in template mode
            include_metadata=show_comments,  # Mirror comment flag
            **kwargs,
        )

        # Flatten: extract nested configs and promote them to top level
        flattened_dict: Dict[str, Any] = {}

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
                    # Direct field (unexpected in merged configs), keep it nested
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
                if as_template or show_comments:
                    # Use custom serialization with comments
                    toml_str = self._dict_to_toml_with_comments(
                        flattened_dict, show_comments=show_comments, parent_path=""
                    )
                    f.write(toml_str)
                else:
                    # Use standard tomlkit serialization (no comments, no None fields)
                    tomlkit.dump(flattened_dict, f)
        except Exception as e:
            raise ValueError(f"Unable to save flattened TOML config to {path}: {e}")

    @classmethod
    def merge(
        cls,
        configs: Union[Dict[str, Self], List[Self]],
        merged_name: str = "MergedConfig",
    ) -> Self:
        """
        Merge multiple configuration instances into a single combined
        configuration.

        This method creates a dynamic configuration class that contains all
        input configurations as nested fields. Each configuration becomes
        a nested_param field in the merged result.

        Args:
            configs: Either a dict mapping field names to config instances, or
                a list of config instances (field names derived from class names)
            merged_name: Name for the dynamically created merged class
                (default: "MergedConfig")

        Returns:
            A configuration containing all input configs as nested fields with
            _is_merged flag set to True

        Raises:
            TypeError: If configs is not a dict or list, or if any config is
                not a BaseConfig instance
            ValueError: If field name conflicts occur

        Example:
            >>> db_config = DatabaseConfig(host="localhost")
            >>> cache_config = CacheConfig(ttl=3600)
            >>> merged = Config.merge([db_config, cache_config])
            >>> merged.to_toml("merged.toml")  # Creates nested structure
            >>> merged.to_flat_toml("flat.toml")  # Creates flat structure
        """

        # Collect field definitions
        field_definitions: List[Tuple[str, Type[Any], Field]] = []
        merged_data: Dict[str, Any] = {}
        seen_field_names: Set[str] = set()
        merged_raw_data: Dict[str, Any] = {}

        # Handle different input types
        if isinstance(configs, dict):
            # For dict form: use dict keys directly as field names
            for field_name, config in configs.items():
                if not isinstance(config, BaseConfig):
                    raise TypeError(
                        "All configurations must be instances of BaseConfig, "
                        f"got: {type(config)}"
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
                        "All configurations must be instances of BaseConfig, "
                        f"got: {type(config)}"
                    )

                # Derive field name from class (e.g. -> dataloader)
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
                "configs must be either dict[str, BaseConfig] or list[BaseConfig], "
                f"got: {type(configs)}"
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
        init_kwargs: Dict[str, Any] = {}

        for field_item in class_fields:
            # Check if this is a nested_param field
            metadata = field_item.metadata
            if metadata.get("param_scope") == ParamScope.NESTED:
                nested_class = metadata.get("nested_class")
                if (
                    nested_class
                    and isinstance(nested_class, type)
                    and issubclass(nested_class, BaseConfig)
                ):
                    # Recursively instantiate the nested class
                    init_kwargs[field_item.name] = cls._instantiate_with_nested(
                        nested_class
                    )

        # Create instance with nested fields
        return config_class(**init_kwargs)  # type: ignore[return-value]

    @classmethod
    def combine(
        cls,
        configs: Union[Dict[str, Type[Self]], List[Type[Self]]],
        combined_name: str = "CombinedConfig",
    ) -> Self:
        """
        Combine multiple BaseConfig subclass definitions into a single Config
        instance.

        This method converts each class definition into instances, then merges
        them using the merge() method. Useful for generating TOML templates from
        multiple config classes.

        Args:
            configs: Either a dict mapping field names to BaseConfig subclasses,
                or a list of BaseConfig subclasses (field names derived from
                class names)
            combined_name: Name for the dynamically created combined class
                (default: "CombinedConfig")

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
                        "All values must be BaseConfig subclasses, got "
                        f"{model_class} for key '{field_name}'"
                    )

            # Create instances from each class with recursive nested instantiation
            config_dict_instances: Dict[str, Self] = {}
            for field_name, model_class in configs.items():
                instance = cls._instantiate_with_nested(model_class)
                # type: ignore[assignment]
                config_dict_instances[field_name] = instance

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
                        "All arguments must be BaseConfig subclasses, "
                        f"got: {model_class}"
                    )

            # Create instances from each class with recursive nested instantiation
            config_list_instances: List[Self] = []
            for model_class in configs:
                instance = cls._instantiate_with_nested(model_class)
                config_list_instances.append(instance)  # type: ignore[arg-type]

            # Use merge to combine all instances
            return cls.merge(config_list_instances, merged_name=combined_name)

        else:
            raise TypeError(
                "model_classes must be either dict[str, type[BaseConfig]] or "
                f"list[type[BaseConfig]], got: {type(configs)}"
            )
