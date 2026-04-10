"""
core/pipeline/executor.py
Executes a Pipeline against a live PostGIS database.

Setiap node menghasilkan sql_subquery yang diwariskan ke node berikutnya.
Geoprocess node membuat TEMP TABLE dari subquery tersebut dalam SATU koneksi
psycopg2 yang sama, sehingga:
  1. Filter WHERE dari Query node benar-benar dipakai PostGIS
  2. TEMP TABLE bisa diakses oleh DDL CREATE TABLE AS berikutnya (same session)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import geopandas as gpd

from core.pipeline.model import Pipeline
from core.domain.value_objects import GeoprocessSpec
from core.geoprocessing.factory import GeoprocessFactory
from utils.logger import get_logger

logger = get_logger("spaque.pipeline.executor")


@dataclass
class StepResult:
    node_id:      str
    success:      bool
    message:      str
    gdf:          Optional[gpd.GeoDataFrame] = None
    sql:          str = ""
    row_count:    int = 0
    sql_subquery: str = ""


@dataclass
class PipelineResult:
    success:       bool
    message:       str
    steps:         List[StepResult] = field(default_factory=list)
    final_gdf:     Optional[gpd.GeoDataFrame] = None
    output_table:  str = ""
    output_schema: str = "public"

    @property
    def errors(self) -> List[str]:
        return [s.message for s in self.steps if not s.success]


class PipelineExecutor:

    def __init__(self, repo, progress_callback: Optional[Callable[[str], None]] = None):
        self._repo        = repo
        self._cb          = progress_callback or (lambda msg: None)
        self._run_id:     str = ""
        self._run_conn    = None
        self._temp_tables: List[str] = []

    def run(self, pipeline: Pipeline) -> PipelineResult:
        self._run_id      = uuid.uuid4().hex[:8]
        self._temp_tables = []
        self._run_conn    = None

        errors = pipeline.validate()
        if errors:
            return PipelineResult(False, "\n".join(errors))

        try:
            order = pipeline.topological_order()
        except ValueError as exc:
            return PipelineResult(False, str(exc))

        try:
            self._open_run_conn()
        except Exception as exc:
            return PipelineResult(False, f"Gagal buka koneksi pipeline: {exc}")

        steps: List[StepResult] = []
        ctx:   Dict[str, StepResult] = {}

        try:
            for node in order:
                self._cb(f"⏳ Menjalankan node: {node.label}")
                result = self._dispatch(node, ctx, pipeline)
                steps.append(result)
                if not result.success:
                    return PipelineResult(
                        False,
                        f"Pipeline berhenti di node '{node.label}': {result.message}",
                        steps=steps,
                    )
                ctx[node.node_id] = result
        finally:
            self._drop_temp_tables()
            self._close_run_conn()

        output_nodes = [n for n in order if n.node_type == "output"]
        final        = ctx.get(output_nodes[-1].node_id) if output_nodes else None
        out_tbl      = output_nodes[-1].params.get("output_table", "") if output_nodes else ""
        out_sch      = output_nodes[-1].params.get("output_schema", "public") if output_nodes else "public"

        self._cb("✅ Pipeline selesai dijalankan")
        return PipelineResult(
            success=True,
            message=f"Pipeline '{pipeline.name}' berhasil — {len(steps)} langkah",
            steps=steps,
            final_gdf=final.gdf if final else None,
            output_table=out_tbl,
            output_schema=out_sch,
        )

    def _dispatch(self, node, ctx, pipeline):
        try:
            if node.node_type == "source":
                return self._run_source(node)
            if node.node_type == "query":
                return self._run_query(node, ctx, pipeline)
            if node.node_type == "geoprocess":
                return self._run_geoprocess(node, ctx, pipeline)
            if node.node_type == "output":
                return self._run_output(node, ctx, pipeline)
            return StepResult(node.node_id, False, f"Tipe node tidak dikenal: {node.node_type}")
        except Exception as exc:
            logger.error("Node %s error: %s", node.node_id, exc)
            return StepResult(node.node_id, False, str(exc))

    def _run_source(self, node):
        schema = node.params.get("schema", "public")
        table  = node.params.get("table", "")
        limit  = int(node.params.get("limit", 5000))
        if not table:
            return StepResult(node.node_id, False, "Tabel belum dipilih")

        sql_sub  = f'SELECT * FROM "{schema}"."{table}"'
        sql_prev = f'{sql_sub} LIMIT {limit}'

        try:
            gdf, _, rows = self._repo.execute_sql(sql_prev)
            count = len(rows)
            logger.info("Source node: %s.%s → %d rows (preview)", schema, table, count)
            return StepResult(
                node_id=node.node_id, success=True,
                message=f"Loaded {count:,} fitur dari {schema}.{table} (preview)",
                gdf=gdf, sql=sql_sub, sql_subquery=sql_sub, row_count=count,
            )
        except Exception as exc:
            return StepResult(node.node_id, False, str(exc))

    def _run_query(self, node, ctx, pipeline):
        preds = pipeline.predecessors(node.node_id)
        if not preds:
            return StepResult(node.node_id, False, "Query node tidak punya input")

        pred = ctx.get(preds[0].node_id)
        if not pred or not pred.sql_subquery:
            return StepResult(node.node_id, False,
                              "Query node: tidak ada SQL dari node sebelumnya")

        schema = node.params.get("schema", "")
        table  = node.params.get("table", "")
        if not table:
            src = self._find_source_ancestor(preds[0], pipeline)
            if src:
                schema = src.params.get("schema", "public")
                table  = src.params.get("table", "")

        where_raw = node.params.get("where_raw", "").strip()
        order_col = node.params.get("order_col", "").strip() or None
        order_dir = node.params.get("order_dir", "ASC")
        limit_val = node.params.get("limit", 0)

        inner = pred.sql_subquery
        parts = [f"SELECT * FROM ({inner}) AS _qsrc"]
        if where_raw:
            parts.append(f"WHERE {where_raw}")
        if order_col:
            parts.append(f'ORDER BY "{order_col}" {order_dir}')
        if limit_val and int(limit_val) > 0:
            parts.append(f"LIMIT {int(limit_val)}")
        sql_sub = "\n".join(parts)

        try:
            gdf, _, rows = self._repo.execute_sql(sql_sub)
            count = len(rows)
            logger.info("Query node: %s.%s → %d rows", schema, table, count)
            return StepResult(
                node_id=node.node_id, success=True,
                message=f"Query filter: {count:,} fitur dari {schema}.{table}",
                gdf=gdf, sql=sql_sub, sql_subquery=sql_sub, row_count=count,
            )
        except Exception as exc:
            return StepResult(node.node_id, False, f"Query gagal: {exc}\nSQL: {sql_sub}")

    def _run_geoprocess(self, node, ctx, pipeline):
        preds = pipeline.predecessors(node.node_id)
        if not preds:
            return StepResult(node.node_id, False, "Geoprocess node tidak punya input")

        p          = node.params
        operation  = p.get("operation", "")
        out_table  = p.get("output_table", f"pipe_{operation.lower().replace(' ', '_')}")
        out_schema = p.get("output_schema", "public")

        if not operation:
            return StepResult(node.node_id, False, "Operasi belum dipilih")
        if not out_table:
            return StepResult(node.node_id, False, "Nama tabel output belum diisi")

        op_obj = GeoprocessFactory.get(operation)
        if not op_obj:
            return StepResult(node.node_id, False, f"Operasi tidak dikenal: {operation}")

        # ── Resolve input/overlay dari params, bukan dari urutan preds ────────
        # User sudah set input_table dan overlay_table di form properti node.
        # Kita cocokkan dengan predecessor mana yang tabelnya sesuai.
        inp_table_param = p.get("input_table", "").strip()
        ov_table_param  = p.get("overlay_table", "").strip()
        inp_geom        = p.get("input_geom", "geom")
        ov_geom         = p.get("overlay_geom", "geom")

        def _table_of(step_result, pipeline_node) -> str:
            """Ambil nama tabel yang dihasilkan/diquery oleh sebuah node."""
            if pipeline_node.node_type == "source":
                return pipeline_node.params.get("table", "")
            if pipeline_node.node_type == "query":
                return pipeline_node.params.get("table", "")
            if pipeline_node.node_type == "geoprocess":
                return pipeline_node.params.get("output_table", "")
            return ""

        # Cari predecessor yang tabelnya cocok dengan input_table param
        inp_pred = None
        ov_pred  = None
        for pred_node in preds:
            tbl = _table_of(ctx.get(pred_node.node_id), pred_node)
            if tbl == inp_table_param and inp_pred is None:
                inp_pred = ctx.get(pred_node.node_id)
            elif tbl == ov_table_param and ov_pred is None:
                ov_pred = ctx.get(pred_node.node_id)

        # Fallback: kalau tidak ketemu match, pakai urutan preds
        if inp_pred is None:
            inp_pred = ctx.get(preds[0].node_id)
        if ov_pred is None and len(preds) >= 2:
            ov_pred = ctx.get(preds[1].node_id)

        if not inp_pred:
            return StepResult(node.node_id, False, "Tidak ada hasil dari node input")

        # ── INPUT temp table ──────────────────────────────────────────────────
        inp_temp = f"_p{self._run_id}_{node.node_id[:6]}_i"
        ok, err = self._create_temp_table(inp_temp, inp_pred.sql_subquery)
        if not ok:
            return StepResult(node.node_id, False, f"Gagal membuat temp table input: {err}")
        logger.info("Geoprocess '%s': inp_temp='%s' tabel='%s' (%d rows)",
                    operation, inp_temp, inp_table_param, inp_pred.row_count)

        # ── OVERLAY temp table ────────────────────────────────────────────────
        ov_temp       = None
        ov_raw_schema = None
        ov_raw_table  = None

        if op_obj.requires_overlay:
            if ov_pred and ov_pred.sql_subquery:
                ov_temp = f"_p{self._run_id}_{node.node_id[:6]}_o"
                ok, err = self._create_temp_table(ov_temp, ov_pred.sql_subquery)
                if not ok:
                    return StepResult(node.node_id, False,
                                      f"Gagal membuat temp table overlay: {err}")
                logger.info("Geoprocess '%s': ov_temp='%s' tabel='%s' (%d rows)",
                            operation, ov_temp, ov_table_param, ov_pred.row_count)
            else:
                # Tidak ada node terhubung — pakai raw table dari params
                ov_raw_schema = p.get("overlay_schema") or None
                ov_raw_table  = ov_table_param or None
                if not ov_raw_table:
                    return StepResult(node.node_id, False,
                                      f"Operasi '{operation}' memerlukan layer overlay.")

        # ── Build SQL ─────────────────────────────────────────────────────────
        spec = GeoprocessSpec(
            operation=operation,
            input_schema="public",
            input_table=inp_temp,
            input_geom=inp_geom,
            output_table=out_table,
            output_schema=out_schema,
            overlay_schema=ov_raw_schema or "public",
            overlay_table=ov_temp or ov_raw_table or "",
            overlay_geom=ov_geom,
            distance=float(p.get("distance", 100)),
            tolerance=float(p.get("tolerance", 0.001)),
            segments=int(p.get("segments", 16)),
            target_srid=int(p.get("target_srid", 4326)),
            dissolve_field=p.get("dissolve_field") or None,
            value_col=p.get("value_col") or None,
            group_col=p.get("group_col") or None,
            k_neighbors=int(p.get("k_neighbors", 1)),
            spatial_predicate=p.get("spatial_predicate", "ST_Intersects"),
            join_type=p.get("join_type", "INNER"),
            area_unit=p.get("area_unit", "ha"),
            dissolve=bool(p.get("dissolve", False)),
            preserve_topology=bool(p.get("preserve_topology", True)),
        )

        raw_sql   = op_obj.build_sql(spec)
        final_sql = raw_sql.replace(f'"public"."{inp_temp}"', f'"{inp_temp}"')
        if ov_temp:
            final_sql = final_sql.replace(f'"public"."{ov_temp}"', f'"{ov_temp}"')

        logger.info("Geoprocess '%s': inp='%s' ov='%s' → %s.%s",
                    operation, inp_temp, ov_temp or ov_raw_table, out_schema, out_table)

        ok, msg, count = self._create_output_table(final_sql, out_schema, out_table)
        if not ok:
            return StepResult(node.node_id, False, msg, sql=final_sql)

        load_sql = f'SELECT * FROM "{out_schema}"."{out_table}"'
        gdf, _, _ = self._repo.execute_sql(load_sql)
        self._repo.invalidate_cache()

        logger.info("Geoprocess '%s' done: %d rows → %s.%s",
                    operation, count, out_schema, out_table)
        return StepResult(
            node_id=node.node_id, success=True, message=msg,
            gdf=gdf, sql=final_sql, sql_subquery=load_sql, row_count=count,
        )

    def _run_output(self, node, ctx, pipeline):
        preds = pipeline.predecessors(node.node_id)
        if not preds:
            return StepResult(node.node_id, False, "Output node tidak punya input")

        pred       = ctx.get(preds[0].node_id)
        out_table  = node.params.get("output_table", "pipeline_output")
        out_schema = node.params.get("output_schema", "public")

        # Tentukan tabel aktual yang sudah ada di DB dari predecessor
        # Jika predecessor adalah Geoprocess, tabelnya sudah dibuat dengan nama
        # output_table geoprocess — gunakan itu, bukan buat tabel baru.
        pred_node     = preds[0]
        pred_out_tbl  = None
        pred_out_sch  = None

        if pred_node.node_type == "geoprocess":
            pred_out_tbl = pred_node.params.get("output_table", "")
            pred_out_sch = pred_node.params.get("output_schema", "public")

        actual_table  = pred_out_tbl or out_table
        actual_schema = pred_out_sch or out_schema

        # Kalau nama output node berbeda dari tabel geoprocess, rename tabel
        if pred_out_tbl and pred_out_tbl != out_table:
            target_new = f'"{out_schema}"."{out_table}"'
            target_old = f'"{pred_out_sch}"."{pred_out_tbl}"'
            try:
                self._exec(f"DROP TABLE IF EXISTS {target_new}")
                self._exec(
                    f"ALTER TABLE {target_old} RENAME TO \"{out_table}\""
                )
                self._run_conn.commit()
                actual_table  = out_table
                actual_schema = out_schema
                logger.info("Output node: renamed '%s' → '%s'", pred_out_tbl, out_table)
            except Exception as exc:
                # Rename gagal — pakai nama geoprocess saja
                logger.warning("Output rename failed: %s — pakai '%s'", exc, pred_out_tbl)
                self._run_conn.rollback()

        gdf   = pred.gdf if pred else None
        count = pred.row_count if pred else 0

        logger.info("Output node: %s.%s (%d rows)", actual_schema, actual_table, count)
        return StepResult(
            node_id=node.node_id, success=True,
            message=f"Output siap: {count:,} fitur di {actual_schema}.{actual_table}",
            gdf=gdf, row_count=count,
            sql_subquery=f'SELECT * FROM "{actual_schema}"."{actual_table}"',
        )

    # ── Connection helpers ────────────────────────────────────────────────────

    def _open_run_conn(self):
        self._run_conn = self._repo._postgis._make_write_connection()
        logger.debug("Pipeline run connection opened (run_id=%s)", self._run_id)

    def _close_run_conn(self):
        if not self._run_conn:
            return
        try:
            self._run_conn.close()
        except Exception:
            pass
        self._run_conn = None

    def _exec(self, sql, params=None):
        cur = self._run_conn.cursor()
        try:
            cur.execute(sql, params)
        finally:
            cur.close()

    def _fetchone(self, sql, params=None):
        cur = self._run_conn.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchone()
        finally:
            cur.close()

    def _fetchall(self, sql, params=None):
        cur = self._run_conn.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            cur.close()

    def _create_temp_table(self, name: str, sql: str) -> Tuple[bool, str]:
        try:
            self._exec(f'DROP TABLE IF EXISTS "{name}"')
            self._exec(f'CREATE TEMP TABLE "{name}" AS ({sql})')
            self._run_conn.commit()
            self._temp_tables.append(name)
            logger.debug("Temp table '%s' created", name)
            return True, ""
        except Exception as exc:
            try:
                self._run_conn.rollback()
            except Exception:
                pass
            return False, str(exc)

    def _create_output_table(self, sql: str,
                              schema: str, table: str) -> Tuple[bool, str, int]:
        target = f'"{schema}"."{table}"'
        try:
            self._exec(f"DROP TABLE IF EXISTS {target}")
            self._exec(f"CREATE TABLE {target} AS ({sql})")

            rows = self._fetchall("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                  AND udt_name = 'geometry'
                ORDER BY ordinal_position
            """, (schema, table))
            geom_cols = [r[0] for r in rows]

            if len(geom_cols) > 1:
                result_geom   = next((c for c in geom_cols if c != 'geom'), geom_cols[-1])
                original_geom = next((c for c in geom_cols if c != result_geom), geom_cols[0])
                self._exec(f'ALTER TABLE {target} DROP COLUMN IF EXISTS "{original_geom}"')
                if result_geom != 'geom':
                    self._exec(f'ALTER TABLE {target} RENAME COLUMN "{result_geom}" TO "geom"')
                logger.debug("Geom normalized: dropped '%s', renamed '%s'→'geom'",
                             original_geom, result_geom)

            self._exec(
                f'ALTER TABLE {target} ADD COLUMN IF NOT EXISTS _gid SERIAL PRIMARY KEY')

            row   = self._fetchone(f"SELECT COUNT(*) FROM {target}")
            count = row[0] if row else 0
            self._run_conn.commit()
            msg = f"Tabel '{table}' berhasil dibuat dengan {count:,} fitur"
            logger.info(msg)
            return True, msg, count

        except Exception as exc:
            try:
                self._run_conn.rollback()
            except Exception:
                pass
            logger.error("create_output_table failed: %s", exc)
            return False, str(exc), 0

    def _drop_temp_tables(self):
        if not self._run_conn or not self._temp_tables:
            return
        try:
            for tbl in self._temp_tables:
                try:
                    self._exec(f'DROP TABLE IF EXISTS "{tbl}"')
                except Exception:
                    pass
            self._run_conn.commit()
        except Exception as exc:
            logger.warning("Drop temp tables failed: %s", exc)
        self._temp_tables.clear()

    def _find_source_ancestor(self, node, pipeline):
        if node.node_type == "source":
            return node
        for pred in pipeline.predecessors(node.node_id):
            found = self._find_source_ancestor(pred, pipeline)
            if found:
                return found
        return None
