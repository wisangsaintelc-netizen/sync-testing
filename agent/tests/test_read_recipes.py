import unittest
from datetime import date

from bapps_sync_agent.domain.read_recipes import RecipeValidationError, ReadRecipe, recipe_for_sync
from bapps_sync_agent.infrastructure.read_recipe_query import compile_read_query


def factura_recipe() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "recipe_code": "profit_factura_current_year",
        "recipe_version": 1,
        "engine": "declarative_table_reader",
        "minimum_agent_version": "0.6.0",
        "source": {
            "profile_ref": "profit_principal",
            "driver": "sqlserver",
            "schema": "dbo",
            "table": "factura",
            "columns": ["fact_num", "fec_emis", "co_cli"],
        },
        "scope": {
            "where": {"operator": "date_window", "column": "fec_emis", "window": "current_calendar_year"},
        },
        "target": {
            "profile_ref": "bapps_mysql",
            "table": "factura_sync",
            "strategy": "full_snapshot",
            "ownership": "managed_only",
        },
        "limits": {"batch_rows": 1000, "statement_timeout_seconds": 60, "max_runtime_seconds": 1800},
    }


class ReadRecipeTest(unittest.TestCase):
    def test_parses_explicit_profit_recipe(self) -> None:
        recipe = ReadRecipe.from_payload(factura_recipe())

        self.assertEqual(recipe.source.driver, "sqlserver")
        self.assertEqual(recipe.source.columns, ("fact_num", "fec_emis", "co_cli"))
        self.assertEqual(recipe.target.table, "factura_sync")

    def test_rejects_raw_sql_and_select_star(self) -> None:
        payload = factura_recipe()
        payload["query"] = "SELECT * FROM dbo.factura"
        with self.assertRaisesRegex(RecipeValidationError, "no permitidos"):
            ReadRecipe.from_payload(payload)

        payload = factura_recipe()
        payload["source"]["columns"] = ["*"]
        with self.assertRaises(RecipeValidationError):
            ReadRecipe.from_payload(payload)

    def test_compiles_current_year_as_parameters(self) -> None:
        query = compile_read_query(ReadRecipe.from_payload(factura_recipe()), today=date(2026, 7, 27))

        self.assertEqual(
            query.sql,
            "SELECT s.[fact_num], s.[fec_emis], s.[co_cli] FROM [dbo].[factura] AS s "
            "WHERE s.[fec_emis] >= ? AND s.[fec_emis] < ?",
        )
        self.assertEqual(query.params, (date(2026, 1, 1), date(2027, 1, 1)))

    def test_compiles_parent_scope_without_a_configured_join(self) -> None:
        payload = factura_recipe()
        payload["source"]["table"] = "reng_fac"
        payload["source"]["columns"] = ["fact_num", "reng_num"]
        payload["scope"] = {
            "parent_scope": {
                "schema": "dbo", "table": "factura", "child_column": "fact_num", "parent_column": "fact_num",
                "where": {"operator": "date_window", "column": "fec_emis", "window": "current_calendar_year"},
            },
        }

        query = compile_read_query(ReadRecipe.from_payload(payload), today=date(2026, 7, 27))

        self.assertIn("EXISTS (SELECT 1 FROM [dbo].[factura] AS p", query.sql)
        self.assertNotIn(" JOIN ", query.sql)
        self.assertEqual(query.params, (date(2026, 1, 1), date(2027, 1, 1)))

    def test_firebird_recipe_omits_schema_and_uses_a_single_qualified_table(self) -> None:
        payload = factura_recipe()
        payload["recipe_code"] = "valery_clientes"
        payload["source"] = {
            "profile_ref": "valery_piloto",
            "driver": "firebird",
            "table": "CLIENTES",
            "columns": ["CODIGO", "NOMBRE"],
        }
        payload["scope"] = {}
        payload["target"]["table"] = "clientes_valery_pilot"

        recipe = ReadRecipe.from_payload(payload)
        query = compile_read_query(recipe)

        self.assertIsNone(recipe.source.schema)
        self.assertEqual(query.sql, 'SELECT s."CODIGO", s."NOMBRE" FROM "CLIENTES" AS s')

    def test_firebird_recipe_rejects_a_misleading_schema(self) -> None:
        payload = factura_recipe()
        payload["source"]["driver"] = "firebird"

        with self.assertRaisesRegex(RecipeValidationError, "no aplica a Firebird"):
            ReadRecipe.from_payload(payload)

    def test_reads_recipe_from_the_assigned_sync_only(self) -> None:
        config = {"syncs": [{"code": "profit_factura", "config": {"recipe": factura_recipe()}}]}

        self.assertEqual(recipe_for_sync(config, "profit_factura").recipe_code, "profit_factura_current_year")
