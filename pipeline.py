"""Ejecuta cada tienda desde su carpeta y publica únicamente salidas nuevas.

Uso: python pipeline.py --list | --store kalea | --all
Los CSV de trabajo permanecen junto al scraper; los Excel finales van a finales/.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

import pandas as pd


ROOT = Path(__file__).resolve().parent
FINALES = ROOT / "finales"
LOGS = ROOT / "logs"

# script, CSV generados, subcarpeta de finales. Los scrapers XLSX escriben
# directamente en finales/ y se comprueban con una marca de tiempo.
STORES = {
    "badan": ("badan/scraping-badan.py", ["maestro_badan_optimizado.csv"], ""),
    "bodegaBE": ("bodegaBE/scraper-bodegabe.py", [], ""),
    "celicor": ("celicor/scrpr-celicor-cast.py", ["celicor_la_castellana.csv"], ""),
    "emporium": ("emporium/scraper-emporium.py", ["catalogo_emporium.csv"], ""),
    "farma-actual": ("farma-actual/scraping-actual.py", ["maestro_tu_farmacia_actual.csv"], "farma-actual"),
    "farmago": ("farmago/scraping-farmago.py", ["maestro_farmago.csv", "pharmago-faltantes.csv"], "farmago"),
    "farmatencion": ("farmatencion/scraper-farmatencion.py", [], ""),
    "gama": ("gama/scr-gama.py", ["catalogo_gama_con_imagenes.csv"], ""),
    "kalea": ("kalea-final/scraper-kalea.py", [], "kalea"),
    "licores-mundiales": ("licores-mundiales/scraper-licmun.py", ["licores_mundiales.csv"], ""),
    "locatel": ("locatel/scraping-locatel.py", ["prods_locatel.csv", "locatel-faltantes.csv"], "locatel"),
    "madison": ("madison (por matchear)/scrap-madisoncenter.py", ["maestro_madison.csv"], ""),
    "MiBodega": ("MiBodega/scraper-mibodega.py", [], ""),
    "plaza": ("plaza (falta precio base)/scraping-plazas.py", ["maestro_elplazas.csv"], ""),
    "rio-market": ("rio-market/scraper-rio.py", [], ""),
    "saas": ("saas/scraping-saas.py", ["prods_saas.csv", "saas-faltantes.csv"], "saas"),
    "superfreshmarket": ("superfreshmarket/scraping-superfreshmkt.py", ["maestro_super_fresh_market.csv"], ""),
    "tucentralonline": ("tucentralonline/scraper-centralmad.py", [], ""),
    "tuzonamarket": ("tuzonamarket/scraping-tuzonamarket.py", ["productos_tuzonamarket_completo.csv"], ""),
    "viva": ("viva/scraper-viva.py", [], ""),
}

OPTIONAL_CSV = {"farmago": {"pharmago-faltantes.csv"},
                "locatel": {"locatel-faltantes.csv"},
                "saas": {"saas-faltantes.csv"}}
NEEDS_BCV = {"farmago", "locatel", "farma-actual"}

XLSX = {
    "bodegaBE": ["bodegon_beplus_maestro.xlsx"],
    "farmatencion": ["catalogo_completo_farmatencion.xlsx"],
    "kalea": ["kalea_catalogo_completo.xlsx"] + [f"kalea_{sede}_{tipo}.xlsx" for sede in ("caracas", "carabobo") for tipo in ("estandar", "ecom", "faltantes")],
    "MiBodega": ["mibodega_maestro_total.xlsx"],
    "rio-market": ["riomarket_maestro_total.xlsx"],
    "tucentralonline": ["inventario_consolidado_tucentral.xlsx"],
    "viva": ["catalogo_viva.xlsx"],
}

SKIP = {"tantovital": "Precios erróneos: datos marcados como no utilizables."}

DATAPRECIO_STAGES = (
    ("scraping-dataprecio1.py", "catalogo_maestro_dataprecio_*.csv"),
    ("rescate-faltantes.py", "catalogo_rescate_dataprecio_*.csv"),
    ("rescate2.py", "catalogo_rescate_luvebras_p14_*.csv"),
)
DATAPRECIO_STORES = 17


def run_script(script: Path, timeout: int, run_id: str) -> tuple[int, Path]:
    log = LOGS / f"{run_id}_{script.parent.name}_{script.stem}.log"
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    with log.open("w", encoding="utf-8") as output:
        try:
            result = subprocess.run(
                [sys.executable, str(script)], cwd=script.parent, env=env,
                stdout=output, stderr=subprocess.STDOUT, timeout=timeout,
                check=False,
            )
            return result.returncode, log
        except subprocess.TimeoutExpired:
            output.write(f"\nTiempo límite excedido: {timeout}s\n")
            return 124, log


def publish_csv(csv_file: Path, output_dir: Path) -> tuple[Path, int]:
    frame = pd.read_csv(csv_file, dtype=str, encoding="utf-8-sig", low_memory=False)
    if frame.empty:
        raise ValueError(f"CSV vacío: {csv_file}")
    # Conservar identificadores como texto (ceros iniciales); tipar precios cuando
    # toda la columna no vacía representa números.
    for column in frame.columns:
        if "precio" not in column.lower() and "price" not in column.lower():
            continue
        values = frame[column].dropna().astype(str).str.strip()
        values = values[values.ne("")]
        if not values.empty:
            numbers = pd.to_numeric(values.str.replace(",", ".", regex=False), errors="coerce")
            if numbers.notna().all():
                frame[column] = pd.to_numeric(
                    frame[column].str.replace(",", ".", regex=False), errors="coerce"
                )
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{csv_file.stem}.xlsx"
    temporary = destination.with_name(destination.stem + ".tmp.xlsx")
    frame.to_excel(temporary, index=False)
    temporary.replace(destination)
    return destination, len(frame)


def run_store(name: str, timeout: int, run_id: str) -> dict:
    script_name, csv_names, subfolder = STORES[name]
    script = ROOT / script_name
    final_dir = FINALES / subfolder if subfolder else FINALES
    started = datetime.now(timezone.utc)
    if name in NEEDS_BCV and not os.environ.get("BCV_RATE"):
        return {"tienda": name, "estado": "pendiente", "detalle": "Falta BCV_RATE"}
    if name == "plaza" and not all(os.environ.get(x) for x in ("PLAZA_EMAIL", "PLAZA_PASSWORD")):
        return {"tienda": name, "estado": "pendiente", "detalle": "Faltan PLAZA_EMAIL y PLAZA_PASSWORD"}
    code, log = run_script(script, timeout, run_id)
    record = {"tienda": name, "script": script_name, "codigo": code,
              "log": str(log.relative_to(ROOT)), "archivos": [], "estado": "error"}
    if code != 0:
        return record
    if name == "farma-actual":
        code2, log2 = run_script(ROOT / "farma-actual/columna-precio-base-ref.py", timeout, run_id)
        record["log_posproceso"] = str(log2.relative_to(ROOT))
        if code2 != 0:
            record["detalle"] = "Falló el cálculo de precio base"
            return record
        csv_names = ["maestro_tu_farmacia_actual.csv", "maestro_tu_farmacia_actual_base.csv"]
    outputs = []
    try:
        for filename in csv_names:
            source = script.parent / filename
            if not source.exists() or datetime.fromtimestamp(source.stat().st_mtime, timezone.utc) < started:
                if filename in OPTIONAL_CSV.get(name, set()):
                    continue
                raise FileNotFoundError(f"No se generó CSV nuevo: {source}")
            dest, rows = publish_csv(source, final_dir)
            outputs.append({"ruta": str(dest.relative_to(ROOT)), "filas": rows})
        for filename in XLSX.get(name, []):
            target = final_dir / filename
            if not target.exists() or datetime.fromtimestamp(target.stat().st_mtime, timezone.utc) < started:
                raise FileNotFoundError(f"No se generó Excel nuevo: {target}")
            if pd.read_excel(target, nrows=1).empty:
                raise ValueError(f"Excel sin productos: {target}")
            outputs.append({"ruta": str(target.relative_to(ROOT)), "bytes": target.stat().st_size})
        if not outputs:
            raise FileNotFoundError("El script terminó sin producir archivos finales nuevos")
        record.update(estado="ok", archivos=outputs)
    except Exception as exc:
        record["detalle"] = str(exc)
    return record


def run_dataprecio(timeout: int, run_id: str) -> dict:
    directory = ROOT / "dataprecio-final"
    record = {"tienda": "dataprecio", "estado": "error", "etapas": [], "archivos": []}
    frames = []
    for filename, pattern in DATAPRECIO_STAGES:
        started = datetime.now(timezone.utc)
        code, log = run_script(directory / filename, timeout, run_id)
        stage = {"script": filename, "codigo": code, "log": str(log.relative_to(ROOT))}
        record["etapas"].append(stage)
        if code != 0:
            record["detalle"] = f"Falló {filename}"
            return record
        fresh = [path for path in directory.glob(pattern)
                 if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) >= started]
        if not fresh:
            record["detalle"] = f"{filename} no produjo CSV nuevo"
            return record
        selected = max(fresh, key=lambda path: path.stat().st_mtime)
        frame = pd.read_csv(selected, dtype=str, encoding="utf-8-sig", low_memory=False)
        if frame.empty:
            record["detalle"] = f"{filename} produjo CSV vacío"
            return record
        frames.append(frame)
        stage["filas"] = len(frame)
    combined = pd.concat(frames, ignore_index=True)
    combined.drop_duplicates(subset=["ID_Dataprecio", "Tienda"], keep="last", inplace=True)
    if combined["Tienda"].nunique() != DATAPRECIO_STORES:
        record["detalle"] = f"Solo hay {combined['Tienda'].nunique()} de {DATAPRECIO_STORES} tiendas; no se publica"
        return record
    source = directory / "prods_dataprecio.csv"
    temporary = directory / "prods_dataprecio.tmp.csv"
    combined.to_csv(temporary, index=False, encoding="utf-8")
    temporary.replace(source)
    started = datetime.now(timezone.utc)
    code, log = run_script(directory / "separador2.py", timeout, run_id)
    record["etapas"].append({"script": "separador2.py", "codigo": code,
                              "log": str(log.relative_to(ROOT))})
    if code != 0:
        record["detalle"] = "Falló el separador"
        return record
    outputs = [path for path in (FINALES / "dataprecio").glob("*.xlsx")
               if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) >= started]
    if len(outputs) != DATAPRECIO_STORES:
        record["detalle"] = f"El separador creó {len(outputs)} de {DATAPRECIO_STORES} archivos"
        return record
    record.update(estado="ok", archivos=[str(path.relative_to(ROOT)) for path in outputs],
                  filas=len(combined))
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--store", choices=sorted(set(STORES) | set(SKIP) | {"dataprecio"}))
    choice.add_argument("--all", action="store_true")
    choice.add_argument("--list", action="store_true")
    parser.add_argument("--exclude", nargs="*", default=[], choices=sorted(set(STORES) | set(SKIP) | {"dataprecio"}))
    parser.add_argument("--timeout", type=int, default=3600, help="segundos por tienda")
    args = parser.parse_args()
    if args.list:
        for name in sorted(set(STORES) | set(SKIP) | {"dataprecio"}):
            print(f"{name}: {'EXCLUIDA' if name in SKIP else '3 scrapers + separador' if name == 'dataprecio' else STORES[name][0]}")
        return 0
    FINALES.mkdir(exist_ok=True)
    LOGS.mkdir(exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    names = [args.store] if args.store else list(STORES) + ["dataprecio"]
    names = [name for name in names if name not in args.exclude]
    results = []
    for name in names:
        if name in SKIP:
            record = {"tienda": name, "estado": "excluida", "detalle": SKIP[name]}
        elif name == "dataprecio":
            print("Ejecutando dataprecio...", flush=True)
            record = run_dataprecio(args.timeout, run_id)
        else:
            print(f"Ejecutando {name}...", flush=True)
            record = run_store(name, args.timeout, run_id)
        results.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
        (LOGS / f"{run_id}_resumen.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return 1 if any(item["estado"] == "error" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
