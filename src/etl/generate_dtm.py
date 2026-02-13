import pdal
import json
import os
import glob
import time
import concurrent.futures
import multiprocessing

# ==========================================
# CONFIGURACIÓN GENERAL
# ==========================================
INPUT_FOLDER = "data/01_raw/"
OUTPUT_FOLDER = "data/03_processed/mdt/"
RESOLUTION = 1.0  # 1 metro/píxel

# PARÁMETROS SMRF
SMRF_WINDOW = 25
SMRF_SLOPE = 0.2
SMRF_THRESHOLD = 0.5

# ==========================================
# FUNCIÓN WORKER (Ejecutada por cada núcleo)
# ==========================================
def process_single_file(filepath, output_dir):
    """
    Función aislada que procesa un único archivo .laz.
    Devuelve una tupla: (nombre_archivo, tiempo_tardado, error_si_hubo)
    """
    filename = os.path.basename(filepath)
    filename_no_ext = os.path.splitext(filename)[0]
    output_filename = f"{filename_no_ext}_MDT.tif"
    output_path = os.path.join(output_dir, output_filename)

    # Definición del Pipeline
    pipeline_json = {
        "pipeline": [
            {
                "type": "readers.las",
                "filename": filepath
            },
            # 1. Filtro Z
            {
                "type": "filters.range",
                "limits": "Z[-50:4000]"
            },
            # 2. Filtro SOR (Ruido)
            {
                "type": "filters.outlier",
                "method": "statistical",
                "mean_k": 8,
                "multiplier": 2.5
            },
            # 3. SMRF (Reclasificación)
            {
                "type": "filters.smrf",
                "window": SMRF_WINDOW,
                "slope": SMRF_SLOPE,
                "threshold": SMRF_THRESHOLD,
                "scalar": 1.25
            },
            # 4. Filtro Semántico (Solo Suelo)
            {
                "type": "filters.range",
                "limits": "Classification[2:2]"
            },
            # 5. Rasterización
            {
                "type": "writers.gdal",
                "filename": output_path,
                "resolution": 1.0, 
                "output_type": "mean",  
                "gdalopts": "COMPRESS=DEFLATE", 
                "nodata": -9999 
            }
        ]
    }

    start_t = time.time()
    try:
        # Ejecutamos PDAL
        pipeline = pdal.Pipeline(json.dumps(pipeline_json))
        
        # --- CORRECCIÓN: Eliminamos la línea 'pipeline.loglevel = 0' ---
        # Si necesitas silenciarlo, usa pipeline.loglevel = 2 (Error) o déjalo por defecto.
        # pipeline.loglevel = 2 
        
        pipeline.execute()
        
        elapsed = time.time() - start_t
        return (filename, elapsed, None) # Éxito

    except Exception as e:
        return (filename, 0, str(e)) # Error capturado

# ==========================================
# FUNCIÓN PRINCIPAL (Orquestador)
# ==========================================
def generate_dtm_parallel(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    files = glob.glob(os.path.join(input_dir, "*.laz")) + \
            glob.glob(os.path.join(input_dir, "*.las"))
    
    total_files = len(files)
    
    if not files:
        print(f"⚠️ No hay archivos en {input_dir}")
        return

    # Detectamos núcleos disponibles y dejamos 1 libre para el SO
    max_workers = max(1, multiprocessing.cpu_count() - 1)
    
    print(f"🚀 INICIANDO PROCESAMIENTO PARALELO")
    print(f"cpu_cores: {multiprocessing.cpu_count()} | workers_activos: {max_workers}")
    print(f"📂 Archivos: {total_files}")
    print(f"⚙️  Configuración SMRF: Win={SMRF_WINDOW}m | Slope={SMRF_SLOPE}")
    print("-" * 100)
    print(f"{'ARCHIVO':<40} | {'TIEMPO':<10} | {'ESTADO'}")
    print("-" * 100)

    start_global = time.time()

    # Usamos ProcessPoolExecutor para paralelismo real
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Enviamos todas las tareas al pool
        # future_to_file es un diccionario para rastrear qué tarea es cuál
        future_to_file = {executor.submit(process_single_file, f, output_dir): f for f in files}
        
        completed_count = 0
        
        # as_completed nos devuelve los resultados conforme van terminando (sin orden específico)
        for future in concurrent.futures.as_completed(future_to_file):
            filename, elapsed, error = future.result()
            completed_count += 1
            
            # --- BARRA DE PROGRESO ---
            percent = (completed_count / total_files) * 100
            bar_length = 15
            filled = int(bar_length * completed_count // total_files)
            bar = '█' * filled + '░' * (bar_length - filled)
            
            if error:
                status_msg = f"❌ ERROR: {error}"
                print(f"\r{filename[:37]+'...':<40} | {0.0:<9.1f}s | {status_msg}")
            else:
                status_msg = f"✅ OK ({completed_count}/{total_files})"
                # Usamos \r para actualizar la línea de estado general, 
                # pero imprimimos líneas nuevas para cada archivo completado para ver el log.
                print(f"{filename[:40]:<40} | {elapsed:<9.1f}s | ✅ Listo")

            # Pequeña info de progreso general en la última línea
            print(f"\r[Progreso General: {bar} {percent:.1f}%] Procesando...", end="", flush=True)

    total_time = time.time() - start_global
    print(f"\n\n" + "-" * 100)
    print(f"🏁 COMPLETADO. Tiempo total: {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"📂 Resultados en: {output_dir}")

if __name__ == "__main__":
    # Importante para multiprocessing en Windows
    generate_dtm_parallel(INPUT_FOLDER, OUTPUT_FOLDER)