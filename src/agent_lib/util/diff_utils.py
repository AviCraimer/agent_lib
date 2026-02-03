from collections.abc import Callable
from deepdiff import parse_path


def make_scope_filter(
    scopes: frozenset[str],
) -> Callable[[object, str], bool]:
    """Create a DeepDiff include_obj_callback that filters to given scopes.

    Args:
        scopes: Set of dot-notation paths, e.g., {'data.user_info', 'config'}

    Returns:
        Callback function for DeepDiff's include_obj_callback parameter
    """

    def callback(_obj: object, path: str) -> bool:
        # Normalize DeepDiff path (e.g., root.data['key']) to dot notation
        # parse_path returns strings for keys and ints for list indices
        normalized = ".".join(str(p) for p in parse_path(path))
        if not normalized:  # root - always traverse
            return True
        for scope in scopes:
            # Include if path is within scope OR scope is within path (for traversal)
            if normalized.startswith(scope) or scope.startswith(normalized):
                return True
        return False

    return callback
