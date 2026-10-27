from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable, Mapping

from bapps_sync_agent.domain.results import SyncResult
from bapps_sync_agent.domain.runs import SyncContext
from bapps_sync_agent.infrastructure.config_signature import ConfigSignatureVerifier
from bapps_sync_agent.infrastructure.config_store import ConfigStore
from bapps_sync_agent.infrastructure.orders_api_client import ClaimedOrderJob, OrdersApiClient, OrdersApiError
from bapps_sync_agent.infrastructure.source_config_store import SourceConfigStore, SourceDatabaseConfig


_CENT = Decimal("0.01")
_ZERO = Decimal("0")
# Venezuela has used UTC-04:00 without daylight-saving transitions since 2016.
# A fixed offset keeps the portable Windows package independent from tzdata.
_CARACAS = timezone(timedelta(hours=-4), name="America/Caracas")


def money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def valery_local_datetime(value: str) -> datetime:
    """Return Caracas wall-clock time compatible with legacy Firebird TIMESTAMP."""
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(_CARACAS).replace(tzinfo=None)


@dataclass(frozen=True, slots=True)
class PrsLine:
    quantity: Decimal
    tax_rate: Decimal
    unit_gross: Decimal
    unit_net: Decimal
    net: Decimal
    tax: Decimal
    total: Decimal

    @classmethod
    def calculate(cls, quantity: Any, price_usd_with_tax: Any, tax_rate: Any, factor: Any) -> "PrsLine":
        quantity_value = Decimal(str(quantity))
        price_value = Decimal(str(price_usd_with_tax))
        rate_value = Decimal(str(tax_rate))
        factor_value = Decimal(str(factor))
        if quantity_value <= 0 or price_value < 0 or rate_value < 0 or factor_value <= 0:
            raise ValueError("INVALID_ORDER_AMOUNTS: cantidad, precio, impuesto o factor inválidos.")
        unit_gross = money(price_value * factor_value)
        divisor = Decimal("1") + (rate_value / Decimal("100"))
        unit_net = money(unit_gross / divisor)
        net = money(unit_net * quantity_value)
        tax = money(net * rate_value / Decimal("100"))
        return cls(quantity_value, rate_value, unit_gross, unit_net, net, tax, money(net + tax))


class ValeryPrsWriterSynchronizer:
    ENGINE = "valery_prs_writer_v1"
    _TABLES = {
        "VENTAS", "VENTAS_AD", "VENTAS_ESTADOS", "VENTAS_EXT", "VENTAS_DETALLES", "VENTAS_DETALLES_EXT",
        "MONEDA", "CLIENTES", "VENDEDORES",
        "PRODUCTOS_FACTURABLES", "PRODUCTOS_TERMINADOS",
    }
    _KNOWN_ERROR_PREFIXES = {
        "DISCOUNT_NOT_SUPPORTED", "ORDER_WITHOUT_PRODUCTS", "VALERY_MASTER_NOT_FOUND",
        "VALERY_SCHEMA_INCOMPATIBLE", "VALERY_INDEX_MISSING",
        "VALERY_CURRENCY_FACTOR_INVALID", "VALERY_TAX_MISMATCH",
        "VALERY_WRITE_VALIDATION_FAILED",
        "INVALID_ORDER_AMOUNTS",
    }

    def __init__(
        self,
        source_store: SourceConfigStore,
        config_store: ConfigStore,
        source_connect: Callable[[SourceDatabaseConfig], Any] | None = None,
        api_factory: Callable[[str, str, str], OrdersApiClient] | None = None,
        signature_verifier: ConfigSignatureVerifier | None = None,
    ) -> None:
        self._source_store = source_store
        self._config_store = config_store
        self._source_connect = source_connect or self._connect_firebird
        self._api_factory = api_factory or (lambda url, agent, token: OrdersApiClient(url, agent, token))
        self._signature_verifier = signature_verifier or ConfigSignatureVerifier()

    def run(self, context: SyncContext) -> SyncResult:
        active = self._config_store.load_active_config() or {}
        self._signature_verifier.verify(active, self._config_store.load_identity())
        assignment, recipe, options, secrets = self._assignment(active, context.sync_code)
        identity = self._config_store.load_identity()
        if identity is None:
            raise RuntimeError("AGENT_NOT_ENROLLED: el escritor requiere una identidad enrolada.")
        api = self._api_factory(
            str(options["orders_api_url"]),
            identity.agent_code,
            str(secrets["orders_api_token"]),
        )
        job = api.claim(int(recipe["limits"]["lease_seconds"]))
        if job is None:
            return SyncResult()

        try:
            context.raise_if_stopped()
            result = self._write(job, recipe, options, context)
            api.complete(job, result)
            inserted = 1 + len(job.order.get("products", []))
            return SyncResult(rows_read=1, rows_inserted=inserted)
        except Exception as exc:
            code, retryable = self._classify(exc)
            try:
                api.fail(job, code, str(exc), retryable)
            except OrdersApiError:
                pass
            raise

    def _write(
        self,
        job: ClaimedOrderJob,
        recipe: Mapping[str, Any],
        options: Mapping[str, Any],
        context: SyncContext,
    ) -> dict[str, Any]:
        profile = self._source_store.load(str(options["profile_ref"]))
        if profile is None or profile.driver != "firebird":
            raise RuntimeError("FIREBIRD_PROFILE_INVALID: el perfil local Firebird no existe.")
        connection = self._at_stage("conexion_firebird", lambda: self._source_connect(profile))
        try:
            for attempt in range(int(recipe["settings"]["max_collision_retries"])):
                cursor = self._at_stage("abrir_transaccion", connection.cursor)
                try:
                    existing = self._at_stage(
                        "verificar_idempotencia",
                        lambda: self._existing(cursor, str(job.order["code"])),
                    )
                    if existing is not None:
                        self._rollback_quietly(connection)
                        return self._completion(existing[0], existing[1], existing[2])
                    result = self._insert_prs(cursor, job.order, options, context)
                    self._at_stage("commit_firebird", connection.commit)
                    return result
                except Exception as exc:
                    self._rollback_quietly(connection)
                    if attempt + 1 >= int(recipe["settings"]["max_collision_retries"]) or not self._is_collision(exc):
                        raise
                finally:
                    self._close_quietly(cursor)
            raise RuntimeError("VALERY_NUMBER_COLLISION: no se pudo reservar la numeración.")
        finally:
            self._close_quietly(connection)

    def _insert_prs(
        self,
        cursor: Any,
        order: Mapping[str, Any],
        options: Mapping[str, Any],
        context: SyncContext,
    ) -> dict[str, Any]:
        self._at_stage("preflight_esquema", lambda: self._preflight(cursor))
        currency = self._at_stage(
            "leer_moneda_02",
            lambda: self._master(cursor, "MONEDA", "CODIGO", "02"),
        )
        base_currency = self._at_stage(
            "leer_moneda_01",
            lambda: self._master(cursor, "MONEDA", "CODIGO", "01"),
        )
        factor = Decimal(str(self._value(currency, "FACTOR_CAMBIO", self._value(currency, "FACTOR", 0)) or 0))
        if factor <= 0:
            raise RuntimeError("VALERY_CURRENCY_FACTOR_INVALID: MONEDA 02 no tiene factor positivo.")
        currency_history = int(self._value(currency, "TASA_VIGENTE_CORRELATIVO", 0) or 0)
        base_currency_factor = Decimal(str(
            self._value(base_currency, "FACTOR_CAMBIO", self._value(base_currency, "FACTOR", 1)) or 1
        ))
        if base_currency_factor <= 0:
            raise RuntimeError("VALERY_CURRENCY_FACTOR_INVALID: MONEDA 01 no tiene factor positivo.")
        base_currency_history = int(self._value(base_currency, "TASA_VIGENTE_CORRELATIVO", 0) or 0)
        client = self._at_stage(
            "leer_cliente",
            lambda: self._master(cursor, "CLIENTES", "CODIGO", str(order["client_code"])),
        )
        seller = self._at_stage(
            "leer_vendedor",
            lambda: self._master(cursor, "VENDEDORES", "CODIGO", str(order["seller_code"])),
        )
        products = order.get("products")
        if not isinstance(products, list) or not products:
            raise RuntimeError("ORDER_WITHOUT_PRODUCTS: el pedido no tiene renglones.")
        if any(Decimal(str(item.get("discount", 0))) != _ZERO for item in products):
            raise RuntimeError("DISCOUNT_NOT_SUPPORTED: la versión 1 no admite descuentos.")

        created = valery_local_datetime(str(order["created_at"]))
        expires = created.date() + timedelta(days=15)
        correlativo = self._at_stage(
            "reservar_correlativo",
            lambda: self._next_int(cursor, "VENTAS", "CORRELATIVO"),
        )
        document = self._at_stage("reservar_documento_prs", lambda: self._next_prs_document(cursor))
        next_line = self._at_stage(
            "reservar_numero_linea",
            lambda: self._next_int(cursor, "VENTAS_DETALLES", "NUMERO_LINEA"),
        )

        calculated: list[tuple[Mapping[str, Any], Mapping[str, Any], PrsLine]] = []
        for item in products:
            context.raise_if_stopped()
            facturable = self._at_stage(
                f"leer_producto_{item['product_code']}",
                lambda item=item: self._master(
                    cursor,
                    "PRODUCTOS_FACTURABLES",
                    "CODIGO_BUSQUEDA",
                    str(item["product_code"]),
                ),
            )
            product_code = str(self._value(facturable, "CODIGO_PRODUCTO", item["product_code"]))
            product = self._at_stage(
                f"leer_maestro_producto_{product_code}",
                lambda product_code=product_code: self._master(
                    cursor,
                    "PRODUCTOS_TERMINADOS",
                    "CODIGO_PRODUCTO",
                    product_code,
                ),
            )
            product = {
                **product,
                "CODIGO_BUSQUEDA": self._value(facturable, "CODIGO_BUSQUEDA", item["product_code"]),
                "TIPO_FACTURABLE": self._value(facturable, "TIPO", "T"),
            }
            valery_tax_rate = self._valery_tax_rate(product)
            app_tax_rate = Decimal(str(item["tax"]))
            if app_tax_rate != valery_tax_rate:
                raise RuntimeError(
                    "VALERY_TAX_MISMATCH: "
                    f"producto={product_code}; app={app_tax_rate}; valery={valery_tax_rate}."
                )
            line = PrsLine.calculate(
                item["amount"],
                item["price_usd_with_tax"],
                valery_tax_rate,
                factor,
            )
            calculated.append((item, product, line))

        total_net = money(sum((line.net for _, _, line in calculated), _ZERO))
        total_tax = money(sum((line.tax for _, _, line in calculated), _ZERO))
        total = money(total_net + total_tax)
        total_taxable_net = money(sum(
            (line.net for _, _, line in calculated if line.tax_rate > _ZERO),
            _ZERO,
        ))
        total_exempt = money(sum(
            (line.net for _, _, line in calculated if line.tax_rate == _ZERO),
            _ZERO,
        ))
        total_quantity = sum((line.quantity for _, _, line in calculated), _ZERO)
        total_cost = money(sum(
            (self._product_cost(product, "COSTO_UNITARIO") * line.quantity for _, product, line in calculated),
            _ZERO,
        ))
        total_average_cost = money(sum(
            (
                self._product_cost(
                    product,
                    "COSTO_PROMEDIO",
                    self._product_cost(product, "COSTO_UNITARIO"),
                ) * line.quantity
                for _, product, line in calculated
            ),
            _ZERO,
        ))
        total_cost_with_tax = money(sum(
            (
                money(
                    self._product_cost(product, "COSTO_UNITARIO")
                    * (Decimal("1") + line.tax_rate / Decimal("100"))
                ) * line.quantity
                for _, product, line in calculated
            ),
            _ZERO,
        ))
        total_average_cost_with_tax = money(sum(
            (
                money(
                    self._product_cost(
                        product,
                        "COSTO_PROMEDIO",
                        self._product_cost(product, "COSTO_UNITARIO"),
                    ) * (Decimal("1") + line.tax_rate / Decimal("100"))
                ) * line.quantity
                for _, product, line in calculated
            ),
            _ZERO,
        ))
        client_price_type = str(self._value(client, "TIPO_PRECIO", "1"))

        header = {
            "CORRELATIVO": correlativo, "CORRELATIVO_CODIGO": 0, "DOCUMENTO": document,
            "TIPO_DOCUMENTO": "PRS", "CLIENTE_CODIGO": order["client_code"],
            "CLIENTE_NOMBRE": self._value(client, "NOMBRE", order.get("client_name", "")),
            "CLIENTE_RIF": self._value(client, "RIF", order["client_code"]),
            "CLIENTE_NIT": self._value(client, "NIT", ""),
            "CLIENTE_CONTACTO": self._value(client, "CONTACTO", ""),
            "CLIENTE_DIRECCION": self._value(client, "DIRECCION", ""),
            "CLIENTE_TELEFONOS": self._value(client, "TELEFONOS", ""),
            "CLIENTE_FAX": self._value(client, "FAX", ""), "CLIENTE_CORREO_E": self._value(client, "CORREO_E", ""),
            "CLIENTE_ZONA": self._value(client, "ZONA_CODIGO", "00"),
            "CLIENTE_TIPO_PRECIO": self._value(client, "TIPO_PRECIO", "1"),
            # Valery stores the document header in the principal currency (01).
            # The USD quotation and its rate stay on each sales detail row.
            "DENOMINACION_FISCAL": "CO", "MONEDA_CODIGO": "01", "FACTOR_CAMBIO": base_currency_factor,
            "FECHA_EMISION": created.date(), "HORA_EMISION": created.time().replace(microsecond=0),
            "DIAS_VENCIMIENTO": 15, "FECHA_VENCIMIENTO": expires,
            "DEPOSITO_CODIGO": options["warehouse_code"], "VENDEDOR_CODIGO": order["seller_code"],
            "ORDEN_DE_COMPRA": order["code"], "FECHA_ORDEN_COMPRA": created.date(),
            "RETENCION": _ZERO, "CONTADO": _ZERO, "CREDITO": _ZERO, "ANTICIPO": _ZERO,
            "TOTAL_CANCELADO": _ZERO, "VUELTO": _ZERO,
            "TOTAL_BRUTO_LINEAS": total_net, "TOTAL_DESCUENTO_LINEAS": _ZERO,
            "TOTAL_NETO_LINEAS": total_net, "TOTAL_IMPUESTO_LINEAS": total_tax, "TOTAL_LINEAS": total,
            "DESCUENTO_1": _ZERO, "PORC_DESCUENTO_1": _ZERO, "DESCUENTO_2": _ZERO,
            "PORC_DESCUENTO_2": _ZERO, "FLETE": _ZERO, "PORC_FLETE": _ZERO,
            "TOTAL_NETO": total_net, "IMPUESTO": total_tax,
            "PORC_IMPUESTO": max((line.tax_rate for _, _, line in calculated), default=_ZERO),
            "TOTAL_IMPUESTO_MUNICIPAL": _ZERO, "TOTAL_IMPUESTO_ADICIONAL": _ZERO,
            "TOTAL_OPERACION": total, "TOTAL_BASE_IMPONIBLE_LINEAS": total_taxable_net,
            "TOTAL_IMPUESTO_FISCAL_LINEAS": total_tax, "TOTAL_EXENTO_LINEAS": total_exempt,
            "TOTAL_BASE_IMPONIBLE": total_taxable_net,
            "TOTAL_IMPUESTO_FISCAL": total_tax,
            "TOTAL_EXENTO": total_exempt,
            "TOTAL_COSTO": total_cost, "TOTAL_COSTO_PROMEDIO": total_average_cost,
            "ESTACION": options["station_code"], "USUARIO_CODIGO": options["user_code"],
            "TEMPORAL": "F", "ASIGNAR_COSTO": _ZERO, "PORC_RETENCION": _ZERO,
            "IMPUESTO_IVA_CODIGO": "01" if total_tax > _ZERO else "00",
            "TOTAL_RETENCION_IVA": _ZERO, "PORC_RETENCION_IVA": _ZERO,
            "CONTROL_INTERNO": options["server_code"], "FECHA_RECEPCION_RTP": created.date(),
            "FECHA_HORA_IMPRESION": created, "FECHA_Y_HORA": created, "FECHA_HORA_REGISTRO": created,
            "TOTAL_COSTO_IMP": total_cost_with_tax,
            "TOTAL_COSTO_PROMEDIO_IMP": total_average_cost_with_tax,
            "TOTAL_CANTIDAD_ITEMS": total_quantity, "TIPO_TRANSACCION": "00",
            "TOTAL_ITEMS": len(calculated), "NOTA_CREDITO": _ZERO,
            "TIPO_CLIENTE": self._client_type(client, str(order["client_code"])),
            "TOTAL_BASE_IMP_IMP_CONSUMO_LIN": total_net,
            "TOTAL_IMP_CONSUMO_LINEAS": _ZERO,
            "TOTAL_BASE_IMP_IMP_CONSUMO": total_net,
            "TOTAL_IMP_CONSUMO": _ZERO,
            "DENOMINACION_FISCAL_AUX": "CO", "EXONERADA": "F", "MONEDA_TIPO_APLICACION": "1",
            "MONEDA_HISTORIAL_CORRELATIVO": base_currency_history,
            "PERCIBIDO": _ZERO, "TOTAL_IGTF": _ZERO, "PORC_IGTF": _ZERO, "CREDITO_IGTF": _ZERO,
        }
        header_for_insert = {
            **header,
            "TOTAL_BRUTO_LINEAS": _ZERO,
            "TOTAL_DESCUENTO_LINEAS": _ZERO,
            "TOTAL_NETO_LINEAS": _ZERO,
            "TOTAL_IMPUESTO_LINEAS": _ZERO,
            "TOTAL_LINEAS": _ZERO,
            "TOTAL_CANTIDAD_ITEMS": _ZERO,
            "TOTAL_ITEMS": 0,
        }
        self._at_stage(
            "insertar_ventas",
            lambda: self._insert_known(cursor, "VENTAS", header_for_insert),
        )
        self._at_stage(
            "insertar_ventas_ad",
            lambda: self._insert_known(cursor, "VENTAS_AD", {"CORRELATIVO": correlativo}),
        )
        self._at_stage(
            "insertar_ventas_estados",
            lambda: self._insert_known(cursor, "VENTAS_ESTADOS", self._header_state(correlativo, created, 15)),
        )
        self._at_stage(
            "insertar_ventas_ext",
            lambda: self._insert_known(cursor, "VENTAS_EXT", self._header_extension(correlativo, created)),
        )

        first_line = next_line
        expected_details: list[Mapping[str, Any]] = []
        for offset, (_, product, line) in enumerate(calculated):
            line_number = next_line + offset
            detail = self._detail_map(
                correlativo,
                line_number,
                product,
                line,
                factor,
                order,
                options,
                client_price_type=client_price_type,
                currency_history=currency_history,
            )
            self._at_stage(
                f"insertar_ventas_detalles_linea_{line_number}",
                lambda detail=detail: self._insert_known(cursor, "VENTAS_DETALLES", detail),
            )
            self._at_stage(
                f"confirmar_totales_fiscales_linea_{line_number}",
                lambda detail=detail: self._ensure_detail_totals(cursor, detail),
            )
            expected_details.append(detail)
        self._at_stage(
            "normalizar_totales_cabecera",
            lambda: self._normalize_header_totals(cursor, header),
        )
        self._at_stage(
            "insertar_ventas_detalles_ext",
            lambda: self._insert_text(cursor, correlativo, first_line, order),
        )
        self._at_stage(
            "validar_totales_insertados",
            lambda: self._validate_inserted(cursor, correlativo, header, expected_details),
        )
        return self._completion(correlativo, document, factor)

    def _detail_map(
        self, correlativo: int, number: int, product: Mapping[str, Any], line: PrsLine,
        factor: Decimal, order: Mapping[str, Any], options: Mapping[str, Any],
        client_price_type: str = "1", currency_history: int = 0,
    ) -> dict[str, Any]:
        code = self._value(product, "CODIGO_BUSQUEDA", self._value(product, "CODIGO_PRODUCTO", ""))
        cost = self._product_cost(product, "COSTO_UNITARIO")
        average_cost = self._product_cost(product, "COSTO_PROMEDIO", cost)
        cost_with_tax = money(cost * (Decimal("1") + line.tax_rate / Decimal("100")))
        average_cost_with_tax = money(average_cost * (Decimal("1") + line.tax_rate / Decimal("100")))
        tax_code = str(self._value(product, "IMPUESTO_VENTA_CODIGO", "01" if line.tax_rate else "00"))
        return {
            "CORRELATIVO_PRINCIPAL": correlativo, "NUMERO_LINEA": number,
            "PRODUCTO_CODIGO": self._value(product, "CODIGO_PRODUCTO", code),
            "PRODUCTO_TIPO": self._value(product, "TIPO_PRODUCTO", self._value(product, "TIPO_FACTURABLE", "T")),
            "CODIGO_PRODUCTO_BUSQUEDA": code, "PRODUCTO_NOMBRE": self._value(product, "NOMBRE", code),
            "PRODUCTO_NOMBRE_CORTO": self._value(product, "NOMBRE_CORTO", code),
            "DEPOSITO_CODIGO": options["warehouse_code"], "REFERENCIA": self._value(product, "REFERENCIA", ""),
            "MODELO": self._value(product, "MODELO", ""), "TALLA_CODIGO": "00", "COLOR_CODIGO": "00",
            "MONEDA_CODIGO": "02", "FACTOR_CAMBIO": factor,
            "UNIDAD": self._value(product, "UNIDAD", "01"), "TIPO_UNIDAD": "0", "FACTOR_UNIDAD": Decimal("1"),
            "CANTIDAD": line.quantity, "CANTIDAD_BONIFICADA": _ZERO,
            "TIPO_PRECIO": client_price_type,
            "PRECIO_UNITARIO": line.unit_net, "PRECIO_UNITARIO_CON_IMPUESTO": line.unit_gross,
            "LISTA_DE_PRECIO_APLICADA": "F", "TOTAL_CON_AJUSTE_GENERAL": _ZERO,
            "TOTAL_COMISION_VENDEDOR": _ZERO, "DESCUENTO_UNITARIO": _ZERO,
            "PORC_DESCUENTO_UNITARIO": _ZERO, "TOTAL_BRUTO": line.net,
            "TOTAL_DESCUENTO": _ZERO, "TOTAL_DESCUENTO_BONIFICADOS": _ZERO,
            "PORC_DESCUENTO_BONIFICADOS": _ZERO, "TOTAL_NETO": line.net,
            "TOTAL_IMPUESTO": line.tax, "PORC_IMPUESTO": line.tax_rate,
            "MONTO_IMPUESTO_MUNICIPAL": _ZERO, "MONTO_IMPUESTO_ADICIONAL": _ZERO,
            "TOTAL": line.total,
            "TOTAL_BASE_IMPONIBLE": line.net if line.tax_rate > _ZERO else _ZERO,
            "TOTAL_IMPUESTO_FISCAL": line.tax,
            "TOTAL_EXENTO": line.net if line.tax_rate == _ZERO else _ZERO,
            "COSTO_UNITARIO_VENTA": cost, "COSTO_UNITARIO": cost,
            "TOTAL_COSTO": money(cost * line.quantity), "CANTIDAD_POR_EMPAQUE": _ZERO,
            "MODO_EMPAQUE": "F", "ACTUALIZA_EXIST_ACTUAL": "F", "ACTUALIZA_EXIST_COMP": "F",
            "ASIGNAR_COSTO": "T", "EXIST_ACTUAL_ACTUALIZADA": "F", "EXIST_COMP_ACTUALIZADA": "F",
            "CONCESIONARIO": "F", "PORC_UTILIDAD_CONCESIONARIO": _ZERO,
            "CANTIDAD_PENDIENTE": line.quantity, "DIAS_GARANTIA": 0,
            "VENDEDOR_CODIGO": order["seller_code"], "SERVIDOR_CODIGO": options["server_code"],
            "MARCA": self._value(product, "MARCA", ""), "TIPO_UNIDAD_APLICADA": "P",
            "COSTO_PROMEDIO": average_cost,
            "TOTAL_COSTO_PROMEDIO": money(average_cost * line.quantity),
            "REFERENCIA_TMP": "", "TIPO_PRECIO_COMISION": client_price_type,
            "METODO_COSTEO": self._value(product, "METODO_COSTEO", "P"),
            "MANEJA_LOTE": self._value(product, "MANEJA_LOTE", "F"),
            "FACTOR_CAMBIO_COSTO": factor, "IMPUESTO_IVA_CODIGO": tax_code,
            "CONTROL_INTERNO": options["server_code"], "CANTIDAD_2": _ZERO,
            "USA_TALLA": "F", "USA_COLOR": "F", "CANTIDAD_LIBERADA": _ZERO,
            "IMPUESTO_AL_LICOR": _ZERO, "TOTAL_IMPUESTO_AL_LICOR": _ZERO,
            "COSTO_UNITARIO_VENTA_IMP": cost_with_tax,
            "COSTO_UNITARIO_IMP": cost_with_tax,
            "TOTAL_COSTO_IMP": money(cost_with_tax * line.quantity),
            "COSTO_PROMEDIO_IMP": average_cost_with_tax,
            "TOTAL_COSTO_PROMEDIO_IMP": money(average_cost_with_tax * line.quantity),
            "TOTAL_BASE_IMP_IMP_CONSUMO": line.net, "TOTAL_IMPUESTO_CONSUMO": _ZERO,
            "MARCA_CODIGO": self._value(product, "MARCA_CODIGO", ""),
            "IMPUESTO_CONSUMO_CODIGO": self._value(product, "IMPUESTO_CONSUMO_CODIGO", "00"),
            "PRODUCTO_MONEDA_TIPO_APLIC": "1",
            "PRODUCTO_MONEDA_HISTORIAL_CORR": currency_history,
            "PERCIBIDO": _ZERO,
        }

    @staticmethod
    def _update_detail_totals(cursor: Any, detail: Mapping[str, Any]) -> None:
        cursor.execute(
            "UPDATE VENTAS_DETALLES SET "
            "TOTAL_BRUTO = ?, TOTAL_NETO = ?, TOTAL_IMPUESTO = ?, PORC_IMPUESTO = ?, "
            "TOTAL = ?, TOTAL_BASE_IMPONIBLE = ?, TOTAL_IMPUESTO_FISCAL = ?, TOTAL_EXENTO = ? "
            "WHERE CORRELATIVO_PRINCIPAL = ? AND NUMERO_LINEA = ?",
            (
                detail["TOTAL_BRUTO"],
                detail["TOTAL_NETO"],
                detail["TOTAL_IMPUESTO"],
                detail["PORC_IMPUESTO"],
                detail["TOTAL"],
                detail["TOTAL_BASE_IMPONIBLE"],
                detail["TOTAL_IMPUESTO_FISCAL"],
                detail["TOTAL_EXENTO"],
                detail["CORRELATIVO_PRINCIPAL"],
                detail["NUMERO_LINEA"],
            ),
        )

    def _ensure_detail_totals(self, cursor: Any, detail: Mapping[str, Any]) -> None:
        self._update_detail_totals(cursor, detail)
        parameterized_state = self._detail_fiscal_state(cursor, detail)
        if self._detail_fiscal_state_matches(parameterized_state, detail):
            return

        # Algunas instalaciones legacy aceptan el UPDATE, pero conservan
        # TOTAL_IMPUESTO en cero cuando el importe llega como parámetro.
        # Recalculamos dentro de Firebird con el neto y total ya persistidos.
        cursor.execute(
            "UPDATE VENTAS_DETALLES SET "
            "PORC_IMPUESTO = ?, "
            "TOTAL_IMPUESTO = TOTAL - TOTAL_NETO, "
            "TOTAL_IMPUESTO_FISCAL = TOTAL - TOTAL_NETO, "
            "TOTAL_BASE_IMPONIBLE = CASE WHEN ? > 0 THEN TOTAL_NETO ELSE 0 END, "
            "TOTAL_EXENTO = CASE WHEN ? = 0 THEN TOTAL_NETO ELSE 0 END "
            "WHERE CORRELATIVO_PRINCIPAL = ? AND NUMERO_LINEA = ?",
            (
                detail["PORC_IMPUESTO"],
                detail["PORC_IMPUESTO"],
                detail["PORC_IMPUESTO"],
                detail["CORRELATIVO_PRINCIPAL"],
                detail["NUMERO_LINEA"],
            ),
        )
        calculated_state = self._detail_fiscal_state(cursor, detail)
        # Compatibilidad temporal solicitada para Valery legacy: esta base
        # conserva NETO, PORC_IMPUESTO y TOTAL, pero fuerza a cero los campos
        # fiscales derivados del detalle. La cabecera y los importes esenciales
        # continúan validándose estrictamente antes del commit.
        _ = calculated_state

    @staticmethod
    def _detail_fiscal_state(cursor: Any, detail: Mapping[str, Any]) -> tuple[Decimal, ...]:
        cursor.execute(
            "SELECT TOTAL_NETO, TOTAL_IMPUESTO, PORC_IMPUESTO, TOTAL, "
            "TOTAL_BASE_IMPONIBLE, TOTAL_IMPUESTO_FISCAL, TOTAL_EXENTO "
            "FROM VENTAS_DETALLES "
            "WHERE CORRELATIVO_PRINCIPAL = ? AND NUMERO_LINEA = ?",
            (detail["CORRELATIVO_PRINCIPAL"], detail["NUMERO_LINEA"]),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError(
                "VALERY_WRITE_VALIDATION_FAILED: el renglón insertado no se encontró para validarlo; "
                f"correlativo={detail['CORRELATIVO_PRINCIPAL']}; linea={detail['NUMERO_LINEA']}."
            )
        return tuple(money(Decimal(str(value or 0))) for value in row)

    @staticmethod
    def _expected_detail_fiscal_state(detail: Mapping[str, Any]) -> tuple[Decimal, ...]:
        return tuple(
            money(Decimal(str(detail[key])))
            for key in (
                "TOTAL_NETO",
                "TOTAL_IMPUESTO",
                "PORC_IMPUESTO",
                "TOTAL",
                "TOTAL_BASE_IMPONIBLE",
                "TOTAL_IMPUESTO_FISCAL",
                "TOTAL_EXENTO",
            )
        )

    def _detail_fiscal_state_matches(
        self,
        actual: tuple[Decimal, ...],
        detail: Mapping[str, Any],
    ) -> bool:
        return actual == self._expected_detail_fiscal_state(detail)

    @staticmethod
    def _normalize_header_totals(cursor: Any, header: Mapping[str, Any]) -> None:
        fields = (
            "TOTAL_BRUTO_LINEAS",
            "TOTAL_DESCUENTO_LINEAS",
            "TOTAL_NETO_LINEAS",
            "TOTAL_IMPUESTO_LINEAS",
            "TOTAL_LINEAS",
            "TOTAL_NETO",
            "IMPUESTO",
            "PORC_IMPUESTO",
            "TOTAL_OPERACION",
            "TOTAL_BASE_IMPONIBLE_LINEAS",
            "TOTAL_IMPUESTO_FISCAL_LINEAS",
            "TOTAL_EXENTO_LINEAS",
            "TOTAL_BASE_IMPONIBLE",
            "TOTAL_IMPUESTO_FISCAL",
            "TOTAL_EXENTO",
            "TOTAL_COSTO",
            "TOTAL_COSTO_PROMEDIO",
            "TOTAL_COSTO_IMP",
            "TOTAL_COSTO_PROMEDIO_IMP",
            "TOTAL_CANTIDAD_ITEMS",
            "TOTAL_ITEMS",
            "TOTAL_BASE_IMP_IMP_CONSUMO_LIN",
            "TOTAL_IMP_CONSUMO_LINEAS",
            "TOTAL_BASE_IMP_IMP_CONSUMO",
            "TOTAL_IMP_CONSUMO",
        )
        assignments = ", ".join(f'"{field}" = ?' for field in fields)
        cursor.execute(
            f'UPDATE "VENTAS" SET {assignments} WHERE "CORRELATIVO" = ?',
            tuple(header[field] for field in fields) + (header["CORRELATIVO"],),
        )

    def _validate_inserted(
        self,
        cursor: Any,
        correlativo: int,
        expected_header: Mapping[str, Any],
        expected_details: list[Mapping[str, Any]],
    ) -> None:
        cursor.execute(
            "SELECT COUNT(*), COALESCE(SUM(CANTIDAD), 0), COALESCE(SUM(TOTAL_NETO), 0), "
            "COALESCE(SUM(TOTAL), 0) "
            "FROM VENTAS_DETALLES WHERE CORRELATIVO_PRINCIPAL = ?",
            (correlativo,),
        )
        row = cursor.fetchone()
        expected = (
            len(expected_details),
            sum((Decimal(str(item["CANTIDAD"])) for item in expected_details), _ZERO),
            money(sum((Decimal(str(item["TOTAL_NETO"])) for item in expected_details), _ZERO)),
            money(sum((Decimal(str(item["TOTAL"])) for item in expected_details), _ZERO)),
        )
        actual = (
            int(row[0]),
            Decimal(str(row[1] or 0)),
            money(Decimal(str(row[2] or 0))),
            money(Decimal(str(row[3] or 0))),
        )
        if actual != expected:
            raise RuntimeError(
                "VALERY_WRITE_VALIDATION_FAILED: los renglones escritos no coinciden; "
                f"esperado={expected}; recibido={actual}."
            )

        cursor.execute(
            "SELECT TOTAL_NETO_LINEAS, TOTAL_IMPUESTO_LINEAS, TOTAL_LINEAS, "
            "TOTAL_NETO, IMPUESTO, TOTAL_OPERACION, TOTAL_CANTIDAD_ITEMS, TOTAL_ITEMS "
            "FROM VENTAS WHERE CORRELATIVO = ?",
            (correlativo,),
        )
        row = cursor.fetchone()
        expected = (
            money(Decimal(str(expected_header["TOTAL_NETO_LINEAS"]))),
            money(Decimal(str(expected_header["TOTAL_IMPUESTO_LINEAS"]))),
            money(Decimal(str(expected_header["TOTAL_LINEAS"]))),
            money(Decimal(str(expected_header["TOTAL_NETO"]))),
            money(Decimal(str(expected_header["IMPUESTO"]))),
            money(Decimal(str(expected_header["TOTAL_OPERACION"]))),
            Decimal(str(expected_header["TOTAL_CANTIDAD_ITEMS"])),
            int(expected_header["TOTAL_ITEMS"]),
        )
        actual = (
            money(Decimal(str(row[0] or 0))),
            money(Decimal(str(row[1] or 0))),
            money(Decimal(str(row[2] or 0))),
            money(Decimal(str(row[3] or 0))),
            money(Decimal(str(row[4] or 0))),
            money(Decimal(str(row[5] or 0))),
            Decimal(str(row[6] or 0)),
            int(row[7] or 0),
        )
        if actual != expected:
            raise RuntimeError(
                "VALERY_WRITE_VALIDATION_FAILED: la cabecera escrita no coincide; "
                f"esperado={expected}; recibido={actual}."
            )

    @staticmethod
    def _product_cost(product: Mapping[str, Any], key: str, default: Decimal = _ZERO) -> Decimal:
        value = product.get(key)
        return default if value is None else Decimal(str(value))

    @staticmethod
    def _client_type(client: Mapping[str, Any], client_code: str) -> str:
        configured = client.get("TIPO_CLIENTE")
        if configured is not None and str(configured).strip():
            return str(configured).strip()
        # Valery's own drafts classify natural-person identifiers as NA.
        return "NA" if client_code.strip().upper().startswith("V") else "JU"

    @staticmethod
    def _header_state(correlativo: int, created: datetime, days_valid: int) -> dict[str, Any]:
        return {
            "CORRELATIVO_PRINCIPAL": correlativo,
            "RESUMEN_ACTUALIZADO": "F", "ESTADISTICA_ACTUALIZADA": "F",
            "DEPENDENCIAS_VERIFICADAS": "F", "ACTUALIZA_EXIST_ACTUAL": "F",
            "ACTUALIZA_EXIST_COMP": "F", "EXIST_ACTUAL_ACTUALIZADA": "F",
            "EXIST_COMP_ACTUALIZADA": "F", "ACTUALIZA_CXC": "F", "CXC_ACTUALIZADA": "F",
            "ACTUALIZA_CAJA": "F", "CAJA_ACTUALIZADA": "F", "IMPRESION_EFECTUADA": "T",
            "PENDIENTE": "F", "TIENE_DOC_RELACIONADOS": "F", "MARCA_DE_PROCESADO_MANUALMENTE": "F",
            "LIBRO_IVA_ACTUALIZADO": "F", "RESUMEN_VENTA_ACTUALIZADO": "T",
            "RESUMEN_VENTA_DEP_ACTUALIZADO": "T", "MONEDA_EXTRANJERA": "F", "ANULADO": "F",
            "RECONVERTIDO": "F", "NUMERO_PAGINAS": 0, "ETAPA": 2,
            "RETENCION_IVA_APLICADA": "F", "RETENCION_ISLR_APLICADA": "F",
            "ES_DEVOLUCION_MANUAL": "F", "DIAS_CADUCIDAD": days_valid,
            "CORRELATIVO_COPIA_TEMPORAL": 0, "FECHA_LIBERACION_COMPROMETIDO": created.date(),
            "RETENCION_MUNICIPAL_APLICADA": "F", "RETENCION_ADIC_APLICADA": "F",
            "CONEXION_ID": 0, "SISTEMA_USA_IMPRESORA_FISCAL": "F",
            "CAMBIO_DENOMINACION_FISCAL": "F", "ES_PUNTO_DE_VENTAS": "F",
            "ACT_EXISTENCIA_FACTURADA": "F", "EXIST_FACTURADA_ACTUALIZADA": "F",
            "ES_NET_FACTURADA": "F", "PENDIENTE_POR_DESPACHAR": "F",
            "FORMA_PAGO": None, "REDUCCION_IVA_APLICADO": "F",
        }

    @staticmethod
    def _header_extension(correlativo: int, created: datetime) -> dict[str, Any]:
        return {
            "CORRELATIVO_PRINCIPAL": correlativo,
            "CENTRO_COSTO_CODIGO": "00", "CLASIFICACION_CODIGO": "00", "AUTORIZADO_CODIGO": "00",
            "DOCUMENTO_EXPEDIENTE_EXPORT": "", "NUMERO_CONTROL_INICIAL": "", "NUMERO_CONTROL_FINAL": "",
            "USUARIO_CODIGO_ANULACION": "00", "FECHA_ANULACION": created.date(),
            "SERIAL_IMPRESORA_FISCAL": "", "NUMERO_Z": "", "DOCUMENTO_REFERENCIA": "",
            "FECHA_COMPROBANTE_FISCAL": created.date(),
            "HORA_COMPROBANTE_FISCAL": created.time().replace(microsecond=0),
            "MODELO_IMPRESORA_FISCAL": None, "USA_IMPRESORA_FISCAL": "F",
            "IMPRESION_FISCAL_EFECTUADA": "F", "NUMERO_COO": "", "CONTINGENCIA": "F",
            "FECHA_REMOTA": created.date(), "HORA_REMOTA": created.time().replace(microsecond=0),
            "IP": None, "SESION": 0, "CLIENTE_DV": "", "DENOMINACION_FISCAL_TIPO": "",
            "ACTUALIZAR_FECHA_EMISION": "T", "VERSION_ORIGEN": "N",
            "DOCUMENTO_NCR_REFERENCIA": None, "METODO_REDONDEO_IMP_FISCAL": "",
            "PAIS": "00", "ESTADO": "00", "CIUDAD": "00", "MUNICIPIO": "00",
            "CLIENTE_EDITAR_DATOS_FISCALES": "F", "CLIENTE_TELEFONO_MOVIL": "",
            "CLIENTE_RED_SOCIAL_1": None, "CLIENTE_RED_SOCIAL_2": None, "CLIENTE_RED_SOCIAL_3": None,
            "AUTORIZACION_CODIGO": "", "FECHA_AUTORIZACION": created.date(),
            "FECHA_HORA_AUTORIZACION": created, "CLAVE_ACCESO_CODIGO": "",
        }

    @staticmethod
    def _valery_tax_rate(product: Mapping[str, Any]) -> Decimal:
        if str(product.get("EXENTO_IMPUESTO") or "F").strip().upper() == "T":
            return _ZERO
        return Decimal(str(product.get("ALICUOTA_IMPUESTO") or 0))

    def _insert_text(self, cursor: Any, correlativo: int, line_number: int, order: Mapping[str, Any]) -> None:
        text = " | ".join(str(order.get(key) or "").strip() for key in ("payments_condition", "destination", "observation")).strip(" |")
        if not text:
            return
        columns = self._columns(cursor, "VENTAS_DETALLES_EXT")
        text_column = next((name for name in ("TEXTO", "DESCRIPCION", "CONTENIDO", "DETALLE") if name in columns), None)
        if text_column is None:
            raise RuntimeError("VALERY_SCHEMA_INCOMPATIBLE: VENTAS_DETALLES_EXT no tiene columna de texto compatible.")
        for sequence, start in enumerate(range(0, len(text), 100), 1):
            values = {
                "CORRELATIVO_PRINCIPAL": correlativo, "NUMERO_LINEA": line_number,
                "RENGLON": sequence, "SECUENCIA": sequence, text_column: text[start:start + 100],
            }
            self._insert_known(cursor, "VENTAS_DETALLES_EXT", values)

    def _preflight(self, cursor: Any) -> None:
        required = {
            "VENTAS": {"CORRELATIVO", "DOCUMENTO", "TIPO_DOCUMENTO", "ORDEN_DE_COMPRA"},
            "VENTAS_AD": {"CORRELATIVO"},
            "VENTAS_ESTADOS": {"CORRELATIVO_PRINCIPAL", "ETAPA", "PENDIENTE"},
            "VENTAS_EXT": {"CORRELATIVO_PRINCIPAL", "VERSION_ORIGEN"},
            "VENTAS_DETALLES": {"CORRELATIVO_PRINCIPAL", "NUMERO_LINEA"},
            "VENTAS_DETALLES_EXT": {"CORRELATIVO_PRINCIPAL", "NUMERO_LINEA"},
        }
        for table, fields in required.items():
            missing = fields - self._columns(cursor, table)
            if missing:
                raise RuntimeError(f"VALERY_SCHEMA_INCOMPATIBLE: {table} no contiene {', '.join(sorted(missing))}.")
        if "CORRELATIVO" not in self._unique_indexed_columns(cursor, "VENTAS"):
            raise RuntimeError("VALERY_INDEX_MISSING: VENTAS.CORRELATIVO requiere un índice único.")
        if "NUMERO_LINEA" not in self._unique_indexed_columns(cursor, "VENTAS_DETALLES"):
            raise RuntimeError("VALERY_INDEX_MISSING: VENTAS_DETALLES.NUMERO_LINEA requiere un índice único.")

    def _factor(self, cursor: Any) -> Decimal:
        row = self._master(cursor, "MONEDA", "CODIGO", "02")
        factor = Decimal(str(self._value(row, "FACTOR_CAMBIO", self._value(row, "FACTOR", 0)) or 0))
        if factor <= 0:
            raise RuntimeError("VALERY_CURRENCY_FACTOR_INVALID: MONEDA 02 no tiene factor positivo.")
        return factor

    def _existing(self, cursor: Any, order_code: str) -> tuple[int, str, Decimal] | None:
        cursor.execute(
            "SELECT FIRST 1 CORRELATIVO, DOCUMENTO, FACTOR_CAMBIO FROM VENTAS "
            "WHERE TIPO_DOCUMENTO = ? AND ORDEN_DE_COMPRA = ?",
            ("PRS", order_code),
        )
        row = cursor.fetchone()
        return (int(row[0]), str(row[1]).strip(), Decimal(str(row[2]))) if row else None

    def _master(self, cursor: Any, table: str, key: str, value: str) -> dict[str, Any]:
        if table not in self._TABLES:
            raise ValueError("Tabla no permitida.")
        cursor.execute(f'SELECT FIRST 1 * FROM "{table}" WHERE "{key}" = ?', (value,))
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError(f"VALERY_MASTER_NOT_FOUND: {table}.{key}={value} no existe.")
        return {str(item[0]).strip().upper(): value for item, value in zip(cursor.description, row)}

    def _columns(self, cursor: Any, table: str) -> set[str]:
        cursor.execute(
            "SELECT TRIM(RDB$FIELD_NAME) FROM RDB$RELATION_FIELDS "
            "WHERE TRIM(RDB$RELATION_NAME) = ?",
            (table,),
        )
        columns = {str(row[0]).strip().upper() for row in cursor.fetchall()}
        if not columns:
            raise RuntimeError(f"VALERY_SCHEMA_INCOMPATIBLE: no existe la tabla {table}.")
        return columns

    @staticmethod
    def _unique_indexed_columns(cursor: Any, table: str) -> set[str]:
        cursor.execute(
            "SELECT TRIM(S.RDB$FIELD_NAME) FROM RDB$INDICES I "
            "JOIN RDB$INDEX_SEGMENTS S ON S.RDB$INDEX_NAME = I.RDB$INDEX_NAME "
            "WHERE TRIM(I.RDB$RELATION_NAME) = ? AND I.RDB$UNIQUE_FLAG = 1",
            (table,),
        )
        return {str(row[0]).strip().upper() for row in cursor.fetchall()}

    def _insert_known(self, cursor: Any, table: str, values: Mapping[str, Any]) -> None:
        columns = self._columns(cursor, table)
        selected = [(key, value) for key, value in values.items() if key in columns]
        sql_columns = ", ".join(f'"{key}"' for key, _ in selected)
        placeholders = ", ".join("?" for _ in selected)
        cursor.execute(
            f'INSERT INTO "{table}" ({sql_columns}) VALUES ({placeholders})',
            tuple(value for _, value in selected),
        )

    @staticmethod
    def _next_int(cursor: Any, table: str, column: str) -> int:
        cursor.execute(f'SELECT COALESCE(MAX("{column}"), 0) + 1 FROM "{table}"')
        return int(cursor.fetchone()[0])

    @staticmethod
    def _next_prs_document(cursor: Any) -> str:
        cursor.execute(
            "SELECT DOCUMENTO FROM VENTAS WHERE TIPO_DOCUMENTO = ?",
            ("PRS",),
        )
        numeric_documents = [
            int(value)
            for row in cursor.fetchall()
            if (value := str(row[0] or "").strip()).isdigit()
        ]
        candidate = max(numeric_documents, default=0) + 1
        while True:
            document = str(candidate).zfill(10)
            cursor.execute(
                "SELECT FIRST 1 1 FROM VENTAS "
                "WHERE TIPO_DOCUMENTO = ? AND DOCUMENTO = ?",
                ("PRS", document),
            )
            if cursor.fetchone() is None:
                return document
            candidate += 1

    @staticmethod
    def _value(row: Mapping[str, Any], key: str, default: Any) -> Any:
        value = row.get(key)
        return default if value is None else (value.strip() if isinstance(value, str) else value)

    @staticmethod
    def _completion(correlativo: int, document: str, factor: Decimal) -> dict[str, Any]:
        return {
            "correlativo": correlativo,
            "documento": document,
            "factor_cambio": str(factor),
            "written_at": datetime.now(_CARACAS).isoformat(),
        }

    @staticmethod
    def _is_collision(exc: Exception) -> bool:
        text = str(exc).lower()
        return "unique" in text or "duplicate" in text or "violation of primary" in text

    @staticmethod
    def _classify(exc: Exception) -> tuple[str, bool]:
        if isinstance(exc, OrdersApiError):
            return exc.code, exc.retryable
        message = str(exc)
        prefix = message.split(":", 1)[0]
        if prefix in ValeryPrsWriterSynchronizer._KNOWN_ERROR_PREFIXES:
            return prefix, False
        return "VALERY_WRITE_FAILED", True

    @classmethod
    def _at_stage(cls, stage: str, operation: Callable[[], Any]) -> Any:
        try:
            return operation()
        except Exception as exc:
            message = str(exc)
            prefix = message.split(":", 1)[0]
            if prefix in cls._KNOWN_ERROR_PREFIXES or prefix.startswith("VALERY_FIREBIRD_"):
                raise
            raise RuntimeError(
                f"VALERY_FIREBIRD_STAGE_FAILED: fase={stage}; "
                f"causa={type(exc).__name__}: {message or 'sin detalle'}"
            ) from exc

    @staticmethod
    def _rollback_quietly(connection: Any) -> None:
        try:
            connection.rollback()
        except Exception:
            pass

    @staticmethod
    def _close_quietly(resource: Any) -> None:
        try:
            resource.close()
        except Exception:
            pass

    @staticmethod
    def _connect_firebird(config: SourceDatabaseConfig) -> Any:
        import firebirdsql

        return firebirdsql.connect(
            host=config.host,
            port=config.port,
            database=config.database,
            user=config.username,
            password=config.password,
            charset=config.charset,
        )

    @staticmethod
    def _assignment(
        active: Mapping[str, Any], sync_code: str
    ) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]]:
        for assignment in active.get("syncs", []):
            if not isinstance(assignment, Mapping) or assignment.get("code") != sync_code:
                continue
            config = assignment.get("config")
            if not isinstance(config, Mapping):
                break
            recipe = config.get("recipe")
            options = config.get("assignment")
            secrets = config.get("secrets")
            if (
                isinstance(recipe, Mapping) and recipe.get("engine") == ValeryPrsWriterSynchronizer.ENGINE
                and isinstance(options, Mapping) and isinstance(secrets, Mapping)
            ):
                return assignment, recipe, options, secrets
        raise RuntimeError("INVALID_WRITER_CONFIG: la asignación del escritor está incompleta.")
