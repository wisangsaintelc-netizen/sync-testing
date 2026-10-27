"""Safe SQL generation for the closed declarative read-recipe grammar."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping

from bapps_sync_agent.domain.read_recipes import ReadRecipe


@dataclass(frozen=True, slots=True)
class CompiledReadQuery:
    sql: str
    params: tuple[Any, ...]


def compile_read_query(recipe: ReadRecipe, today: date | None = None) -> CompiledReadQuery:
    """Compile only validated recipe primitives; values remain DB-API parameters."""
    current = today or date.today()
    quote = _quote_sqlserver if recipe.source.driver == "sqlserver" else _quote_firebird
    source_alias = "s"
    selected = ", ".join(f"{source_alias}.{quote(column)}" for column in recipe.source.columns)
    table = _qualified_table(recipe.source.schema, recipe.source.table, quote)
    clauses: list[str] = []
    params: list[Any] = []
    where = recipe.scope.get("where")
    if isinstance(where, Mapping):
        clause, values = _compile_predicate(where, source_alias, quote, current)
        clauses.append(clause)
        params.extend(values)
    parent_scope = recipe.scope.get("parent_scope")
    if isinstance(parent_scope, Mapping):
        parent_table = _qualified_table(parent_scope.get("schema"), str(parent_scope["table"]), quote)
        parent_where, parent_values = _compile_predicate(parent_scope["where"], "p", quote, current)
        clauses.append(
            f"EXISTS (SELECT 1 FROM {parent_table} AS p WHERE "
            f"p.{quote(str(parent_scope['parent_column']))} = s.{quote(str(parent_scope['child_column']))} "
            f"AND {parent_where})"
        )
        params.extend(parent_values)
    suffix = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return CompiledReadQuery(f"SELECT {selected} FROM {table} AS {source_alias}{suffix}", tuple(params))


def _compile_predicate(predicate: Mapping[str, Any], alias: str, quote: Any, today: date) -> tuple[str, tuple[Any, ...]]:
    operator = predicate["operator"]
    if operator in {"and", "or"}:
        children = [_compile_predicate(child, alias, quote, today) for child in predicate["predicates"]]
        return f"({' {} '.format(operator.upper()).join(item[0] for item in children)})", tuple(
            value for _clause, values in children for value in values
        )
    column = f"{alias}.{quote(str(predicate['column']))}"
    if operator == "eq":
        return f"{column} = ?", (predicate["value"],)
    if operator == "in":
        values = tuple(predicate["values"])
        return f"{column} IN ({', '.join('?' for _ in values)})", values
    if operator == "is_null":
        return f"{column} IS NULL", ()
    if operator == "is_not_null":
        return f"{column} IS NOT NULL", ()
    if operator == "date_window":
        start = date(today.year, 1, 1)
        end = date(today.year + 1, 1, 1)
        return f"{column} >= ? AND {column} < ?", (start, end)
    raise AssertionError(f"Unsupported validated predicate: {operator}")


def _quote_sqlserver(identifier: str) -> str:
    return f"[{identifier.replace(']', ']]')}]"


def _quote_firebird(identifier: str) -> str:
    return f'"{identifier.replace(chr(34), chr(34) * 2)}"'


def _qualified_table(schema: Any, table: str, quote: Any) -> str:
    return f"{quote(str(schema))}.{quote(table)}" if schema is not None else quote(table)
