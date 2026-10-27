from decimal import Decimal
import unittest

from bapps_sync_agent.syncs.valery_prs_writer import (
    PrsLine,
    ValeryPrsWriterSynchronizer,
    valery_local_datetime,
)


class ValeryPrsWriterPricingTest(unittest.TestCase):
    def test_calculates_a_taxed_line_from_authorized_usd_gross_price(self) -> None:
        line = PrsLine.calculate("10", "17.04", "16", "730")

        self.assertEqual(line.unit_gross, Decimal("12439.20"))
        self.assertEqual(line.unit_net, Decimal("10723.45"))
        self.assertEqual(line.net, Decimal("107234.50"))
        self.assertEqual(line.tax, Decimal("17157.52"))
        self.assertEqual(line.total, Decimal("124392.02"))

    def test_calculates_exempt_products_without_tax(self) -> None:
        line = PrsLine.calculate("2.5", "4.00", "0", "100")

        self.assertEqual(line.net, Decimal("1000.00"))
        self.assertEqual(line.tax, Decimal("0.00"))
        self.assertEqual(line.total, Decimal("1000.00"))

    def test_rejects_zero_exchange_factor(self) -> None:
        with self.assertRaisesRegex(ValueError, "INVALID_ORDER_AMOUNTS"):
            PrsLine.calculate("1", "10", "16", "0")

    def test_reports_the_exact_firebird_stage_for_an_unexpected_failure(self) -> None:
        def fail() -> None:
            raise ConnectionAbortedError(10053, "conexión abortada")

        with self.assertRaisesRegex(
            RuntimeError,
            "VALERY_FIREBIRD_STAGE_FAILED: fase=insertar_ventas; "
            "causa=ConnectionAbortedError",
        ):
            ValeryPrsWriterSynchronizer._at_stage("insertar_ventas", fail)

    def test_cleanup_does_not_replace_the_original_writer_error(self) -> None:
        class BrokenConnection:
            def rollback(self) -> None:
                raise ConnectionAbortedError(10053, "rollback abortado")

            def close(self) -> None:
                raise ConnectionAbortedError(10053, "cierre abortado")

        connection = BrokenConnection()

        ValeryPrsWriterSynchronizer._rollback_quietly(connection)
        ValeryPrsWriterSynchronizer._close_quietly(connection)

    def test_preserves_catalogued_business_errors_without_wrapping_them(self) -> None:
        def fail() -> None:
            raise RuntimeError("VALERY_INDEX_MISSING: falta índice")

        with self.assertRaisesRegex(RuntimeError, "^VALERY_INDEX_MISSING"):
            ValeryPrsWriterSynchronizer._at_stage("preflight_esquema", fail)

    def test_converts_api_timestamp_to_naive_caracas_time_for_legacy_firebird(self) -> None:
        created = valery_local_datetime("2026-07-30T21:14:11.000000Z")

        self.assertEqual(str(created), "2026-07-30 17:14:11")
        self.assertIsNone(created.tzinfo)

    def test_builds_a_complete_taxed_detail_from_the_product_master(self) -> None:
        writer = ValeryPrsWriterSynchronizer(None, None)
        line = PrsLine.calculate("1", "17.04", "16", "790")

        detail = writer._detail_map(
            9847,
            15931,
            {
                "CODIGO_BUSQUEDA": "111-1",
                "CODIGO_PRODUCTO": "111-1",
                "TIPO_PRODUCTO": "T",
                "NOMBRE": "Producto de prueba",
                "NOMBRE_CORTO": "Producto",
                "UNIDAD": "01",
                "COSTO_UNITARIO": Decimal("10"),
                "COSTO_PROMEDIO": Decimal("9"),
                "IMPUESTO_VENTA_CODIGO": "01",
                "METODO_COSTEO": "P",
            },
            line,
            Decimal("790"),
            {"seller_code": "02"},
            {"warehouse_code": "01", "server_code": "00"},
            client_price_type="4",
            currency_history=1230,
        )

        self.assertEqual(detail["TOTAL_NETO"], Decimal("11604.83"))
        self.assertEqual(detail["TOTAL_IMPUESTO"], Decimal("1856.77"))
        self.assertEqual(detail["TOTAL_IMPUESTO_FISCAL"], Decimal("1856.77"))
        self.assertEqual(detail["TOTAL"], Decimal("13461.60"))
        self.assertEqual(detail["TOTAL_BASE_IMPONIBLE"], Decimal("11604.83"))
        self.assertEqual(detail["TIPO_PRECIO"], "4")
        self.assertEqual(detail["PRODUCTO_MONEDA_HISTORIAL_CORR"], 1230)
        self.assertEqual(detail["COSTO_UNITARIO_IMP"], Decimal("11.60"))

    def test_rejects_a_detail_sum_changed_by_firebird_before_commit(self) -> None:
        class Cursor:
            def execute(self, _query, _params):
                pass

            def fetchone(self):
                return (1, Decimal("1"), Decimal("11604.83"), Decimal("0"), Decimal("13461.60"))

        writer = ValeryPrsWriterSynchronizer(None, None)
        with self.assertRaisesRegex(RuntimeError, "VALERY_WRITE_VALIDATION_FAILED"):
            writer._validate_inserted(
                Cursor(),
                9847,
                {
                    "TOTAL_NETO_LINEAS": Decimal("11604.83"),
                    "TOTAL_IMPUESTO_LINEAS": Decimal("1856.77"),
                    "TOTAL_LINEAS": Decimal("13461.60"),
                    "TOTAL_NETO": Decimal("11604.83"),
                    "IMPUESTO": Decimal("1856.77"),
                    "TOTAL_OPERACION": Decimal("13461.60"),
                    "TOTAL_CANTIDAD_ITEMS": Decimal("1"),
                    "TOTAL_ITEMS": 1,
                },
                [{
                    "CANTIDAD": Decimal("1"),
                    "TOTAL_NETO": Decimal("11604.83"),
                    "TOTAL_IMPUESTO": Decimal("1856.77"),
                    "TOTAL": Decimal("13461.60"),
                }],
            )

    def test_reads_the_tax_rate_from_productos_terminados(self) -> None:
        self.assertEqual(
            ValeryPrsWriterSynchronizer._valery_tax_rate({
                "EXENTO_IMPUESTO": "F",
                "ALICUOTA_IMPUESTO": "16",
            }),
            Decimal("16"),
        )
        self.assertEqual(
            ValeryPrsWriterSynchronizer._valery_tax_rate({
                "EXENTO_IMPUESTO": "T",
                "ALICUOTA_IMPUESTO": "16",
            }),
            Decimal("0"),
        )

    def test_builds_valery_final_document_state_and_extension(self) -> None:
        created = valery_local_datetime("2026-07-30T21:14:11.000000Z")

        state = ValeryPrsWriterSynchronizer._header_state(9857, created, 15)
        extension = ValeryPrsWriterSynchronizer._header_extension(9857, created)

        self.assertEqual(state["CORRELATIVO_PRINCIPAL"], 9857)
        self.assertEqual(state["ETAPA"], 2)
        self.assertEqual(state["PENDIENTE"], "F")
        self.assertEqual(state["IMPRESION_EFECTUADA"], "T")
        self.assertEqual(state["DIAS_CADUCIDAD"], 15)
        self.assertEqual(extension["CORRELATIVO_PRINCIPAL"], 9857)
        self.assertEqual(extension["VERSION_ORIGEN"], "N")
        self.assertEqual(extension["FECHA_HORA_AUTORIZACION"], created)

    def test_uses_client_type_from_master_or_identifier_fallback(self) -> None:
        self.assertEqual(ValeryPrsWriterSynchronizer._client_type({"TIPO_CLIENTE": "JU"}, "V123"), "JU")
        self.assertEqual(ValeryPrsWriterSynchronizer._client_type({}, "V123"), "NA")
        self.assertEqual(ValeryPrsWriterSynchronizer._client_type({}, "J123"), "JU")

    def test_reasserts_legacy_firebird_fiscal_totals_before_validation(self) -> None:
        class Cursor:
            query = ""
            params = ()

            def execute(self, query, params):
                self.query = query
                self.params = params

        cursor = Cursor()
        ValeryPrsWriterSynchronizer._update_detail_totals(cursor, {
            "TOTAL_BRUTO": Decimal("58024.15"),
            "TOTAL_NETO": Decimal("58024.15"),
            "TOTAL_IMPUESTO": Decimal("9283.86"),
            "PORC_IMPUESTO": Decimal("16"),
            "TOTAL": Decimal("67308.01"),
            "TOTAL_BASE_IMPONIBLE": Decimal("58024.15"),
            "TOTAL_IMPUESTO_FISCAL": Decimal("9283.86"),
            "TOTAL_EXENTO": Decimal("0"),
            "CORRELATIVO_PRINCIPAL": 9848,
            "NUMERO_LINEA": 15932,
        })

        self.assertTrue(cursor.query.startswith("UPDATE VENTAS_DETALLES SET"))
        self.assertEqual(cursor.params[2], Decimal("9283.86"))
        self.assertEqual(cursor.params[-2:], (9848, 15932))

    def test_recalculates_tax_inside_firebird_when_parameterized_update_keeps_zero(self) -> None:
        class Cursor:
            def __init__(self) -> None:
                self.queries = []
                self.rows = [
                    (
                        Decimal("11604.83"), Decimal("0"), Decimal("16"),
                        Decimal("13461.60"), Decimal("0"), Decimal("0"), Decimal("0"),
                    ),
                    (
                        Decimal("11604.83"), Decimal("1856.77"), Decimal("16"),
                        Decimal("13461.60"), Decimal("11604.83"), Decimal("1856.77"), Decimal("0"),
                    ),
                ]

            def execute(self, query, params):
                self.queries.append((query, params))

            def fetchone(self):
                return self.rows.pop(0)

        detail = {
            "TOTAL_BRUTO": Decimal("11604.83"),
            "TOTAL_NETO": Decimal("11604.83"),
            "TOTAL_IMPUESTO": Decimal("1856.77"),
            "PORC_IMPUESTO": Decimal("16"),
            "TOTAL": Decimal("13461.60"),
            "TOTAL_BASE_IMPONIBLE": Decimal("11604.83"),
            "TOTAL_IMPUESTO_FISCAL": Decimal("1856.77"),
            "TOTAL_EXENTO": Decimal("0"),
            "CORRELATIVO_PRINCIPAL": 9849,
            "NUMERO_LINEA": 15933,
        }
        cursor = Cursor()

        ValeryPrsWriterSynchronizer._ensure_detail_totals(
            ValeryPrsWriterSynchronizer.__new__(ValeryPrsWriterSynchronizer),
            cursor,
            detail,
        )

        fallback = next(query for query, _params in cursor.queries if "TOTAL - TOTAL_NETO" in query)
        self.assertIn("TOTAL_IMPUESTO = TOTAL - TOTAL_NETO", fallback)

    def test_accepts_legacy_zero_detail_tax_when_core_totals_are_preserved(self) -> None:
        class Cursor:
            def __init__(self) -> None:
                self.rows = [
                    (
                        Decimal("11604.83"), Decimal("0"), Decimal("16"),
                        Decimal("13461.60"), Decimal("0"), Decimal("0"), Decimal("0"),
                    ),
                    (
                        Decimal("11604.83"), Decimal("0"), Decimal("16"),
                        Decimal("13461.60"), Decimal("11604.83"), Decimal("0"), Decimal("0"),
                    ),
                ]

            def execute(self, _query, _params):
                pass

            def fetchone(self):
                return self.rows.pop(0)

        detail = {
            "TOTAL_BRUTO": Decimal("11604.83"),
            "TOTAL_NETO": Decimal("11604.83"),
            "TOTAL_IMPUESTO": Decimal("1856.77"),
            "PORC_IMPUESTO": Decimal("16"),
            "TOTAL": Decimal("13461.60"),
            "TOTAL_BASE_IMPONIBLE": Decimal("11604.83"),
            "TOTAL_IMPUESTO_FISCAL": Decimal("1856.77"),
            "TOTAL_EXENTO": Decimal("0"),
            "CORRELATIVO_PRINCIPAL": 9850,
            "NUMERO_LINEA": 15934,
        }

        ValeryPrsWriterSynchronizer._ensure_detail_totals(
            ValeryPrsWriterSynchronizer.__new__(ValeryPrsWriterSynchronizer),
            Cursor(),
            detail,
        )

    def test_validates_header_strictly_without_requiring_legacy_detail_tax_fields(self) -> None:
        class Cursor:
            def __init__(self) -> None:
                self.rows = [
                    (1, Decimal("1"), Decimal("11604.83"), Decimal("13461.60")),
                    (
                        Decimal("11604.83"), Decimal("1856.77"), Decimal("13461.60"),
                        Decimal("11604.83"), Decimal("1856.77"), Decimal("13461.60"),
                        Decimal("1"), 1,
                    ),
                ]

            def execute(self, _query, _params):
                pass

            def fetchone(self):
                return self.rows.pop(0)

        ValeryPrsWriterSynchronizer(None, None)._validate_inserted(
            Cursor(),
            9851,
            {
                "TOTAL_NETO_LINEAS": Decimal("11604.83"),
                "TOTAL_IMPUESTO_LINEAS": Decimal("1856.77"),
                "TOTAL_LINEAS": Decimal("13461.60"),
                "TOTAL_NETO": Decimal("11604.83"),
                "IMPUESTO": Decimal("1856.77"),
                "TOTAL_OPERACION": Decimal("13461.60"),
                "TOTAL_CANTIDAD_ITEMS": Decimal("1"),
                "TOTAL_ITEMS": 1,
            },
            [{
                "CANTIDAD": Decimal("1"),
                "TOTAL_NETO": Decimal("11604.83"),
                "TOTAL_IMPUESTO": Decimal("1856.77"),
                "TOTAL": Decimal("13461.60"),
            }],
        )

    def test_normalizes_trigger_managed_header_totals_after_inserting_details(self) -> None:
        class Cursor:
            query = ""
            params = ()

            def execute(self, query, params):
                self.query = query
                self.params = params

        cursor = Cursor()
        header = {
            "CORRELATIVO": 9852,
            "TOTAL_BRUTO_LINEAS": Decimal("11604.83"),
            "TOTAL_DESCUENTO_LINEAS": Decimal("0"),
            "TOTAL_NETO_LINEAS": Decimal("11604.83"),
            "TOTAL_IMPUESTO_LINEAS": Decimal("1856.77"),
            "TOTAL_LINEAS": Decimal("13461.60"),
            "TOTAL_NETO": Decimal("11604.83"),
            "IMPUESTO": Decimal("1856.77"),
            "PORC_IMPUESTO": Decimal("16"),
            "TOTAL_OPERACION": Decimal("13461.60"),
            "TOTAL_BASE_IMPONIBLE_LINEAS": Decimal("11604.83"),
            "TOTAL_IMPUESTO_FISCAL_LINEAS": Decimal("1856.77"),
            "TOTAL_EXENTO_LINEAS": Decimal("0"),
            "TOTAL_BASE_IMPONIBLE": Decimal("11604.83"),
            "TOTAL_IMPUESTO_FISCAL": Decimal("1856.77"),
            "TOTAL_EXENTO": Decimal("0"),
            "TOTAL_COSTO": Decimal("6.21"),
            "TOTAL_COSTO_PROMEDIO": Decimal("6.21"),
            "TOTAL_COSTO_IMP": Decimal("7.20"),
            "TOTAL_COSTO_PROMEDIO_IMP": Decimal("7.20"),
            "TOTAL_CANTIDAD_ITEMS": Decimal("1"),
            "TOTAL_ITEMS": 1,
            "TOTAL_BASE_IMP_IMP_CONSUMO_LIN": Decimal("11604.83"),
            "TOTAL_IMP_CONSUMO_LINEAS": Decimal("0"),
            "TOTAL_BASE_IMP_IMP_CONSUMO": Decimal("11604.83"),
            "TOTAL_IMP_CONSUMO": Decimal("0"),
        }

        ValeryPrsWriterSynchronizer._normalize_header_totals(cursor, header)

        self.assertTrue(cursor.query.startswith('UPDATE "VENTAS" SET'))
        self.assertIn('"TOTAL_NETO_LINEAS" = ?', cursor.query)
        self.assertIn('"TOTAL_CANTIDAD_ITEMS" = ?', cursor.query)
        self.assertEqual(cursor.params[-1], 9852)
        self.assertEqual(cursor.params[2], Decimal("11604.83"))

    def test_next_prs_document_uses_highest_numeric_value_and_skips_collisions(self) -> None:
        class Cursor:
            def __init__(self) -> None:
                self.lookups = [(1,), None]
                self.executed = []

            def execute(self, query, params):
                self.executed.append((query, params))

            def fetchall(self):
                return [
                    ("0000000001",),
                    ("0000000052",),
                    ("",),
                    (None,),
                    ("BORRADOR",),
                    ("0000000053",),
                ]

            def fetchone(self):
                return self.lookups.pop(0)

        cursor = Cursor()

        document = ValeryPrsWriterSynchronizer._next_prs_document(cursor)

        self.assertEqual(document, "0000000055")
        self.assertEqual(cursor.executed[-2][1], ("PRS", "0000000054"))
        self.assertEqual(cursor.executed[-1][1], ("PRS", "0000000055"))
