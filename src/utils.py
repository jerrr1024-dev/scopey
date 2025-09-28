import inspect
from functools import wraps
from pathlib import Path


def check_path(
    check_type: str = "both",
    path_param: str = "path",
    prefix: str = None,
    suffix: str = None,
):
    """Decorator to validate file or directory paths before executing the decorated function.

    This decorator verifies that a path exists and optionally checks if it's a file or directory.
    For files, it can also validate the prefix and suffix of the path.

    Args:
        check_type (str, optional): Type of path to check. Must be one of ['both', 'file', 'dir'].
            - 'both': Accept either file or directory (only existence is checked)
            - 'file': Path must be a file
            - 'dir': Path must be a directory
            Defaults to 'both'.
        prefix (str, optional): Required prefix for the filepath. Only applies when check_type is 'file'.
            Defaults to None (no prefix check).
        suffix (str, optional): Required file extension without the dot (e.g., 'txt', 'png').
            Only applies when check_type is 'file'. Defaults to None (no suffix check).
        path_param (str, optional): Name of the parameter in the decorated function that contains
            the path to validate. Defaults to "path".

    Raises:
        ValueError: If check_type is not one of the allowed values.
        FileNotFoundError: If the path doesn't exist or isn't a file when check_type is 'file'.
        NotADirectoryError: If the path isn't a directory when check_type is 'dir'.
        ValueError: If prefix/suffix checks fail.

    Returns:
        callable: The decorated function that will perform path validation.
    """
    # Validate check_type parameter
    allowed_types = ["both", "file", "dir"]
    if check_type not in allowed_types:
        raise ValueError(
            f"check_type must be one of {allowed_types}, got '{check_type}'"
        )

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get the signature of the decorated function
            sig = inspect.signature(func)
            param_names = list(sig.parameters.keys())

            # Try to get the path value
            path_value = None

            # First, check if the path is in kwargs
            if path_param in kwargs:
                path_value = kwargs[path_param]
            # Otherwise, check if it's in args based on position
            elif path_param in param_names:
                param_index = param_names.index(path_param)
                if param_index < len(args):
                    path_value = args[param_index]

            # If we couldn't find the path parameter, raise an error
            if path_value is None:
                raise ValueError(
                    f"Could not find parameter '{path_param}' in function arguments"
                )

            # Convert to Path object
            path = Path(path_value)

            # Check if path exists
            if not path.exists():
                raise FileNotFoundError(f"Path does not exist: {path}")

            # Check path type based on check_type parameter
            if check_type == "dir":
                if not path.is_dir():
                    raise NotADirectoryError(f"Path is not a directory: {path}")
            elif check_type == "file":
                if not path.is_file():
                    raise FileNotFoundError(f"Path is not a file: {path}")

                # Only perform prefix/suffix checks for files
                if prefix:
                    prefix_path = Path(prefix)
                    try:
                        # Check if the path is under the prefix path
                        path.resolve().relative_to(prefix_path.resolve())
                    except ValueError:
                        raise ValueError(
                            f"Path is not under the required prefix '{prefix}': {path}"
                        )

                if suffix:
                    # Remove the leading dot if present in suffix
                    clean_suffix = suffix.lstrip(".")
                    # Get file extension without the dot
                    file_suffix = path.suffix.lstrip(".")

                    if file_suffix != clean_suffix:
                        raise ValueError(
                            f"Path does not have the required extension '.{clean_suffix}': {path}"
                        )

            # Call the decorated function if all checks pass
            return func(*args, **kwargs)

        return wrapper

    return decorator
