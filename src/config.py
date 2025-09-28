import copy
import warnings
from dataclasses import Field, dataclass, field, fields, make_dataclass
from enum import Enum, auto
from pathlib import Path

import toml

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
    default: any,
) -> Field:

    metadata = {"param_scope": scope, "required": required}

    # use deepcopy to prevent unintended mutation of original object
    return field(default_factory=lambda: copy.deepcopy(default), metadata=metadata)


def global_param(required: bool = True, default: any = None) -> Field:
    return param_field(ParamScope.GLOBAL, required, default)


def local_param(required: bool = True, default: any = None) -> Field:
    return param_field(ParamScope.LOCAL, required, default)


def global_first_param(required: bool = True, default: any = None) -> Field:
    return param_field(ParamScope.GLOBAL_FIRST, required, default)


def local_first_param(required: bool = True, default: any = None) -> Field:
    return param_field(ParamScope.LOCAL_FIRST, required, default)


def nested_param(
    nested_class: type, required: bool = True, default: any = None
) -> Field:
    metadata = {
        "param_scope": ParamScope.NESTED,
        "required": required,
        "nested_class": nested_class,
    }
    return field(default_factory=lambda: copy.deepcopy(default), metadata=metadata)


@dataclass
class BaseConfig:
    def __post_init__(self) -> None:
        # Initialize original data storage
        if not hasattr(self, "_raw_data"):
            self._raw_data = None

        self.validate()

    @classmethod
    @check_path(check_type="file", suffix="toml")  # check file path, must be toml
    def from_toml(
        cls,
        path: str | Path,
        module_section: str,
        global_section: str = "global",
        enable_default_override: bool = True,  # Whether to allow overriding default values in definitions
        warn_on_override: bool = True,  # Whether to warn when first-level parameter override occurs
    ):
        try:
            with open(file=path, mode="r", encoding="utf-8") as f:
                toml_data = toml.load(f=f)

            return cls.from_dict(
                toml_data,
                module_section,
                global_section,
                enable_default_override,
                warn_on_override,
            )  # Whether to warn when first-level parameter override occurs

        except Exception as e:
            raise ValueError(f"Can not load TOML config from {path}: {e}")

    @classmethod
    def from_dict(
        cls,
        data: dict[str, any],
        module_section: str,
        global_section: str = "global",
        enable_default_override: bool = True,  # Whether to allow overriding default values in definitions
        warn_on_override: bool = True,  # Whether to warn when first-level parameter override occurs
    ):

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
                value = f.default_factory()

            params[field_name] = value

        instance = cls(**params)
        # validate required params
        instance._validate_required_params()
        # Save original data
        instance._raw_data = copy.deepcopy(data)
        return instance

    @classmethod
    def get_param_value(
        cls,
        data: dict[str, any],
        field_name: str,
        scope: ParamScope,
        global_section: str,
        module_section: str,
        warn_on_override: bool,
        required: bool = True,
        nested_class: type = None,  # if nested, pass the Class to call
    ):
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

            tmp_data = {field_name: nested_data}
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

    def _validate_required_params(self):

        missing_required = []
        for f in fields(self):
            is_required = f.metadata.get("required", False)
            current_value = getattr(self, f.name)

            if is_required and current_value is None:
                missing_required.append(f.name)

        if missing_required:
            raise ValueError(f"Missing required parameters: {missing_required}")

    def validate(self) -> None:
        # validate in baseconfig
        pass

    def to_dict(
        self,
        global_section: str = "global",
        module_section: str | None = None,
        include_none: bool = True,
        include_global_section: bool = True,
    ) -> dict[str, any]:

        if module_section is None:
            module_section = self.__class__.__name__.lower().replace("config", "")

        result = {}

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

    def to_toml(
        self,
        path: str | Path | None = None,
        global_section: str = "global",
        module_section: str | None = None,
        **kwargs,
    ):
        """Save configuration object as TOML format"""
        data_dict = self.to_dict(
            global_section=global_section, module_section=module_section, **kwargs
        )

        if path is None:
            # Automatically generate filename based on class name
            class_name = self.__class__.__name__
            filename = class_name.lower().replace("config", "") + ".toml"
            path = Path(filename)
        else:
            path = Path(path)

        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, "w", encoding="utf-8") as f:
                toml.dump(data_dict, f)
        except Exception as e:
            raise ValueError(f"Unable to save TOML config to {path}: {e}")

    @classmethod
    def merge(
        cls, configs: list["BaseConfig"], class_name: str = "MergedConfig"
    ) -> "BaseConfig":
        """Merge configuration list, generate new dynamic class"""

        # Collect field definitions
        field_definitions = []
        merged_data = {}
        seen_field_names = set()
        merged_raw_data = {}

        for config in configs:
            if not isinstance(config, BaseConfig):
                raise TypeError(
                    f"All configurations must be instances of BaseConfig, got: {type(config)}"
                )

            # Use configuration class name as field name (DataLoaderConfig -> dataloader)
            field_name = config.__class__.__name__.lower().replace("config", "")

            # Check field name conflicts
            if field_name in seen_field_names:
                raise ValueError(f"Field name conflict: '{field_name}' already exists")
            seen_field_names.add(field_name)

            # Use default_factory to avoid mutable default value problems
            field_definitions.append(
                (field_name, type(config), field(default_factory=lambda c=config: c))
            )
            merged_data[field_name] = config

            # Merge original data
            if hasattr(config, "_raw_data") and config._raw_data:
                merged_raw_data.update(config._raw_data)

        # Dynamically create merged class
        MergedConfig = make_dataclass(
            class_name,
            field_definitions,
            bases=(BaseConfig,),
            namespace={"__module__": cls.__module__},
        )

        merged_instance = MergedConfig(**merged_data)
        # Save merged original data
        merged_instance._raw_data = merged_raw_data
        return merged_instance
