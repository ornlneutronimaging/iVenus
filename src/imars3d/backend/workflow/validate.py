import importlib
from importlib.util import find_spec
import json
import jsonschema
from pathlib import Path
import sys
from typing import Any, Dict, Tuple, Union

FilePath = Union[Path, str]

# JSON schema. Cut be here or in its own file
# http://json-schema.org/learn/getting-started-step-by-step.html
SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "instrument": {"type": "string"},
        "ipts": {"type": "string"},
        "name": {"type": "string"},
        "workingdir": {"type": "string"},
        "outputdir": {"type": "string"},
        "tasks": {
            "type": "array",
            "minItems": 1,
            "items": {
                "properties": {
                    "name": {"type": "string"},
                    "function": {"type": "string"},
                    "inputs": {"type": "object"},
                    "outputs": {"type": "array"},
                },
                "required": ["name", "function", "inputs"],
            },
        },
    },
    "required": ["instrument", "ipts", "name", "workingdir", "outputdir", "tasks"],
}


def _validate_schema(json_obj: Any) -> None:
    """Validate the data against the schema for jobs"""
    try:
        jsonschema.validate(json_obj, schema=SCHEMA)
    except jsonschema.ValidationError as e:
        raise JSONValidationError("While validation configuration file") from e


def _function_parts(func_str: str) -> Tuple[str, str]:
    """Convert the function specification into a module and function name"""
    mod_str = ".".join(func_str.split(".")[:-1])
    func_str = func_str.split(".")[-1]
    return (mod_str, func_str)


def _function_exists(func_str: str) -> bool:
    """Returns True if the function exists"""
    mod_str, func_str = _function_parts(func_str)

    return bool(find_spec(mod_str, func_str))


def _validate_tasks_exist(json_obj: Dict) -> None:
    """Go through the list of tasks and verify that all tasks exist"""
    for step, task in enumerate(json_obj["tasks"]):
        func_str = task["function"].strip()
        if not func_str:
            # TODO need better exception
            raise JSONValidationError(f'Step {step} specified empty "function"')
        if "." not in func_str:
            raise JSONValidationError(f"Function '{func_str}' does not appear to be absolute specification")
        if not _function_exists(func_str):
            raise JSONValidationError(f'Step {step} specified nonexistent function "{func_str}"')


def _todict(obj: Union[Dict, Path, str]) -> Dict:
    """Convert the supplied object into a dict. Raise a TypeError if the object is not a type that has a conversion menthod."""
    if isinstance(obj, dict):
        return obj
    elif isinstance(obj, Path):
        with open(obj, "r") as handle:
            return json.load(handle)
    elif isinstance(obj, str):
        return json.loads(obj)
    else:
        raise TypeError(f"Do not know how to convert type={type(obj)} to dict")


class JSONValidationError(RuntimeError):
    """Custom exception for validation errors independent of what created them"""

    pass  # default behavior is good enough


class JSONValid:
    """Descriptor class that validates the json object

    See https://realpython.com/python-descriptors/"""

    def __get__(self, obj, type=None) -> Dict:
        return obj._json

    def __set__(self, obj, value) -> None:
        obj._json = _todict(value)
        self._validate(obj._json)

    def _validate(self, obj: Dict) -> None:
        _validate_schema(obj)
        _validate_tasks_exist(obj)