"""Validated, declarative read recipes.

Recipes are data received from the Control Center.  They deliberately cannot
contain raw SQL or executable expressions: this module validates every
identifier and every supported filtering primitive before a connector sees it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import re


class RecipeValidationError(ValueError):
    pass


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_DRIVERS = {"firebird", "sqlserver"}
_STRATEGIES = {"full_snapshot", "daily_history_v1"}
_OWNERSHIPS = {"create_new", "managed_only"}
_TRANSFORMATIONS = {"profit.article_tax_rate_v1"}


@dataclass(frozen=True, slots=True)
class SourceSpec:
    profile_ref: str
    driver: str
    schema: str | None
    table: str
    columns: tuple[str, ...]
    schema_fingerprint: str | None


@dataclass(frozen=True, slots=True)
class TargetSpec:
    profile_ref: str
    table: str
    strategy: str
    ownership: str
    key_columns: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReadRecipe:
    recipe_code: str
    recipe_version: int
    minimum_agent_version: str
    source: SourceSpec
    target: TargetSpec
    scope: Mapping[str, Any]
    constants: Mapping[str, str | int | float | bool | None]
    transformations: tuple[str, ...]
    batch_rows: int
    statement_timeout_seconds: int
    max_runtime_seconds: int

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ReadRecipe":
        _reject_unknown(payload, {
            "schema_version", "recipe_code", "recipe_version", "engine", "minimum_agent_version",
            "source", "scope", "target", "constants", "transformations", "limits",
        }, "receta")
        if payload.get("schema_version") != "1.0":
            raise RecipeValidationError("La receta debe declarar schema_version 1.0.")
        if payload.get("engine") != "declarative_table_reader":
            raise RecipeValidationError("La receta no usa el motor declarativo permitido.")
        recipe_code = _identifier(payload.get("recipe_code"), "recipe_code")
        recipe_version = _positive_int(payload.get("recipe_version"), "recipe_version")
        minimum_agent_version = _version(payload.get("minimum_agent_version"))
        source = _source_spec(payload.get("source"))
        target = _target_spec(payload.get("target"))
        scope = _scope(payload.get("scope", {}), source.driver)
        constants = _constants(payload.get("constants", {}))
        overlap = set(source.columns).intersection(constants)
        if overlap:
            raise RecipeValidationError(
                f"constants no puede sobrescribir columnas origen: {', '.join(sorted(overlap))}."
            )
        transformations = _transformations(payload.get("transformations", []))
        limits = _limits(payload.get("limits"))
        if target.strategy == "daily_history_v1" and not target.key_columns:
            raise RecipeValidationError("daily_history_v1 requiere key_columns.")
        return cls(
            recipe_code=recipe_code,
            recipe_version=recipe_version,
            minimum_agent_version=minimum_agent_version,
            source=source,
            target=target,
            scope=scope,
            constants=constants,
            transformations=transformations,
            **limits,
        )


def recipe_for_sync(active_config: Mapping[str, Any], sync_code: str) -> ReadRecipe:
    syncs = active_config.get("syncs")
    if not isinstance(syncs, list):
        raise RecipeValidationError("La configuración activa no contiene sincronizadores.")
    for assignment in syncs:
        if not isinstance(assignment, Mapping) or assignment.get("code") != sync_code:
            continue
        config = assignment.get("config")
        if not isinstance(config, Mapping):
            break
        payload = config.get("recipe", config)
        if isinstance(payload, Mapping):
            return ReadRecipe.from_payload(payload)
        break
    raise RecipeValidationError(f"No hay una receta válida para {sync_code}.")


def _source_spec(value: Any) -> SourceSpec:
    if not isinstance(value, Mapping):
        raise RecipeValidationError("source debe ser un objeto.")
    _reject_unknown(value, {"profile_ref", "driver", "schema", "table", "columns", "schema_fingerprint"}, "source")
    driver = value.get("driver")
    if driver not in _DRIVERS:
        raise RecipeValidationError("source.driver debe ser firebird o sqlserver.")
    columns = _identifiers(value.get("columns"), "source.columns", maximum=512)
    fingerprint = value.get("schema_fingerprint")
    if fingerprint is not None and (not isinstance(fingerprint, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", fingerprint)):
        raise RecipeValidationError("source.schema_fingerprint es inválido.")
    return SourceSpec(
        profile_ref=_profile_ref(value.get("profile_ref")),
        driver=driver,
        schema=_source_schema(value.get("schema"), "source.schema", driver),
        table=_identifier(value.get("table"), "source.table"),
        columns=columns,
        schema_fingerprint=fingerprint,
    )


def _target_spec(value: Any) -> TargetSpec:
    if not isinstance(value, Mapping):
        raise RecipeValidationError("target debe ser un objeto.")
    _reject_unknown(value, {"profile_ref", "table", "strategy", "ownership", "key_columns"}, "target")
    strategy = value.get("strategy")
    ownership = value.get("ownership")
    if strategy not in _STRATEGIES:
        raise RecipeValidationError("target.strategy no está permitido.")
    if ownership not in _OWNERSHIPS:
        raise RecipeValidationError("target.ownership no está permitido.")
    raw_keys = value.get("key_columns", [])
    return TargetSpec(
        profile_ref=_profile_ref(value.get("profile_ref")),
        table=_identifier(value.get("table"), "target.table"),
        strategy=strategy,
        ownership=ownership,
        key_columns=_identifiers(raw_keys, "target.key_columns", maximum=16, required=False),
    )


def _scope(value: Any, driver: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RecipeValidationError("scope debe ser un objeto.")
    _reject_unknown(value, {"where", "parent_scope"}, "scope")
    normalized: dict[str, Any] = {}
    if "where" in value:
        normalized["where"] = _predicate(value["where"], "scope.where")
    if "parent_scope" in value:
        parent = value["parent_scope"]
        if not isinstance(parent, Mapping):
            raise RecipeValidationError("scope.parent_scope debe ser un objeto.")
        _reject_unknown(parent, {"schema", "table", "child_column", "parent_column", "where"}, "scope.parent_scope")
        normalized["parent_scope"] = {
            "schema": _source_schema(parent.get("schema"), "scope.parent_scope.schema", driver),
            "table": _identifier(parent.get("table"), "scope.parent_scope.table"),
            "child_column": _identifier(parent.get("child_column"), "scope.parent_scope.child_column"),
            "parent_column": _identifier(parent.get("parent_column"), "scope.parent_scope.parent_column"),
            "where": _predicate(parent.get("where"), "scope.parent_scope.where"),
        }
    return normalized


def _predicate(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RecipeValidationError(f"{path} debe ser un objeto.")
    operator = value.get("operator")
    if operator in {"eq", "in", "is_null", "is_not_null", "date_window"}:
        _reject_unknown(value, {
            "operator", "column", "value", "values", "window",
        }, path)
        normalized: dict[str, Any] = {"operator": operator, "column": _identifier(value.get("column"), f"{path}.column")}
        if operator == "eq":
            normalized["value"] = _scalar(value.get("value"), f"{path}.value")
        elif operator == "in":
            values = value.get("values")
            if not isinstance(values, list) or not 1 <= len(values) <= 100:
                raise RecipeValidationError(f"{path}.values debe contener de 1 a 100 valores.")
            normalized["values"] = tuple(_scalar(item, f"{path}.values") for item in values)
        elif operator == "date_window":
            if value.get("window") != "current_calendar_year":
                raise RecipeValidationError(f"{path}.window no está permitido.")
            normalized["window"] = "current_calendar_year"
        return normalized
    if operator in {"and", "or"}:
        _reject_unknown(value, {"operator", "predicates"}, path)
        predicates = value.get("predicates")
        if not isinstance(predicates, list) or not 2 <= len(predicates) <= 20:
            raise RecipeValidationError(f"{path}.predicates debe contener de 2 a 20 condiciones.")
        return {"operator": operator, "predicates": tuple(_predicate(item, f"{path}.predicates") for item in predicates)}
    raise RecipeValidationError(f"{path}.operator no está permitido.")


def _constants(value: Any) -> Mapping[str, str | int | float | bool | None]:
    if not isinstance(value, Mapping) or len(value) > 32:
        raise RecipeValidationError("constants debe tener como máximo 32 valores.")
    return {_identifier(key, "constants"): _scalar(item, f"constants.{key}") for key, item in value.items()}


def _transformations(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > 8 or len(set(value)) != len(value):
        raise RecipeValidationError("transformations es inválido.")
    if any(item not in _TRANSFORMATIONS for item in value):
        raise RecipeValidationError("La receta solicita una transformación no incluida en el agente.")
    return tuple(value)


def _limits(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise RecipeValidationError("limits debe ser un objeto.")
    _reject_unknown(value, {"batch_rows", "statement_timeout_seconds", "max_runtime_seconds"}, "limits")
    batch_rows = _bounded_int(value.get("batch_rows"), "limits.batch_rows", 100, 5_000)
    statement_timeout_seconds = _bounded_int(value.get("statement_timeout_seconds"), "limits.statement_timeout_seconds", 5, 600)
    max_runtime_seconds = _bounded_int(value.get("max_runtime_seconds"), "limits.max_runtime_seconds", 30, 21_600)
    return {
        "batch_rows": batch_rows,
        "statement_timeout_seconds": statement_timeout_seconds,
        "max_runtime_seconds": max_runtime_seconds,
    }


def _profile_ref(value: Any) -> str:
    return _identifier(value, "profile_ref", allow_dash=True)


def _source_schema(value: Any, path: str, driver: str) -> str | None:
    if driver == "sqlserver":
        return _identifier(value, path)
    if value is not None:
        raise RecipeValidationError(f"{path} no aplica a Firebird y debe omitirse.")
    return None


def _identifier(value: Any, path: str, allow_dash: bool = False) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise RecipeValidationError(f"{path} debe ser un identificador válido.")
    pattern = r"^[A-Za-z_][A-Za-z0-9_$-]*$" if allow_dash else _IDENTIFIER.pattern
    if not re.fullmatch(pattern, value):
        raise RecipeValidationError(f"{path} debe ser un identificador válido.")
    return value


def _identifiers(value: Any, path: str, maximum: int, required: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list) or (required and not value) or len(value) > maximum:
        raise RecipeValidationError(f"{path} debe contener identificadores válidos.")
    result = tuple(_identifier(item, path) for item in value)
    if len(set(result)) != len(result):
        raise RecipeValidationError(f"{path} no puede repetir columnas.")
    return result


def _scalar(value: Any, path: str) -> str | int | float | bool | None:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise RecipeValidationError(f"{path} debe ser un valor escalar.")


def _positive_int(value: Any, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise RecipeValidationError(f"{path} debe ser un entero positivo.")
    return value


def _bounded_int(value: Any, path: str, minimum: int, maximum: int) -> int:
    integer = _positive_int(value, path)
    if not minimum <= integer <= maximum:
        raise RecipeValidationError(f"{path} debe estar entre {minimum} y {maximum}.")
    return integer


def _version(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise RecipeValidationError("minimum_agent_version debe tener formato x.y.z.")
    return value


def _reject_unknown(value: Mapping[str, Any], allowed: set[str], path: str) -> None:
    unknown = set(value).difference(allowed)
    if unknown:
        raise RecipeValidationError(f"{path} contiene campos no permitidos: {', '.join(sorted(unknown))}.")
