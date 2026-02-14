import pdal
import json
import os
import glob
import time
import concurrent.futures
import multiprocessing

# ==========================================
# 1. CONFIGURACIÓN EXPERTA (TFG PARAMETERS)
# ==========================================
INPUT_FOLDER = "data/01_raw/"
OUTPUT_FOLDER = "data/03_processed/mdt_final/"
RESOLUTION = 1.0  # 1 metro/pixel para el raster

# --- PARÁMETROS ESPECTRALES (EL FILTRO "ANTI-INVERNADERO") ---
# Calibración basada en tus datos PNOA 2024 (16-bit):
# El plástico y la chapa reflejan masivamente NIR y RGB.
# La vegetación refleja NIR pero absorbe Rojo.
# El suelo tiene valores medios.
NIR_THRESHOLD = 35000      # Umbral de Infrarrojo (Saturan cerca de 60k)
RGB_THRESHOLD = 20000      # Umbral de luz visible
# Regla: Si (NIR > 42k) Y (Rojo > 32k) -> ES PLÁSTICO O METAL.

# --- PARÁMETROS GEOMÉTRICOS (SMRF) ---
# Window: Debe ser mayor que el edificio más grande (Invernadero/Nave).
# Si es muy pequeño, el algoritmo creerá que el techo plano es suelo.
SMRF_WINDOW = 55.0         
SMRF_SLOPE = 0.15          # Pendiente tolerada (0.15 = 15%)
SMRF_THRESHOLD = 0.50      # Tolerancia vertical (0.5m)
SMRF_SCALAR = 1.25

def process_single_file(filepath, output_dir):
    filename = os.path.basename(filepath)
    filename_no_ext = os.path.splitext(filename)[0]
    output_filename = f"{filename_no_ext}_MDT_FUSION.tif"
    output_path = os.path.join(output_dir, output_filename)

    # Construcción del Pipeline PDAL
    pipeline_json = {
        "pipeline": [
            # 1. LECTURA
            {
                "type": "readers.las",
                "filename": filepath
            },
            
            # 2. LIMPIEZA BÁSICA (RUIDO Z)
            # Elimina errores del sensor muy altos o muy bajos
            {
                "type": "filters.range",
                "limits": "Z[-50:3000]"
            },

            # 3. CLASIFICACIÓN ESPECTRAL (LA "RECETA" DEL TFG)
            # Marcamos como Clase 6 (Buildings) todo lo que cumpla la firma espectral
            # de un invernadero o nave industrial.
            # Sintaxis: Asignar Class=6 DONDE (Infrared > X AND Red > Y)
            {
                "type": "filters.expression",
                "expression": f"!(Infrared > {NIR_THRESHOLD} && Red > {RGB_THRESHOLD})"
            },

            # 4. FILTRO DE SUELO (SMRF) CON "IGNORE"
            # Aquí ocurre la magia: Calculamos el suelo, pero le decimos explícitamente
            # que IGNORE (ignore="Classification[6:6]") los puntos que acabamos de marcar
            # como plástico. Así, el algoritmo "ve" agujeros donde hay naves y busca el suelo real.
            {
                "type": "filters.smrf",
                "window": SMRF_WINDOW,
                "slope": SMRF_SLOPE,
                "threshold": SMRF_THRESHOLD,
                "scalar": SMRF_SCALAR,
                "ignore": "Classification[6:6]" 
            },

            # 5. FILTRADO FINAL
            # Nos quedamos SOLO con la Clase 2 (Suelo) calculada por SMRF
            {
                "type": "filters.range",
                "limits": "Classification[2:2]"
            },

            # 6. ESCRITURA DEL RASTER (MDT)
            # Usamos "min" o "idw". "min" es agresivo para asegurar que cogemos el punto más bajo 
            # (tierra) y no vegetación baja que se haya escapado.
            {
                "type": "writers.gdal",
                "filename": output_path,
                "resolution": RESOLUTION,
                "output_type": "min", # Toma el valor Z mínimo en cada celda de 1x1m
                "gdalopts": "COMPRESS=DEFLATE",
                "nodata": -9999
            }
        ]
    }

    start_t = time.time()
    try:
        # Ejecución del pipeline
        pipeline = pdal.Pipeline(json.dumps(pipeline_json))
        pipeline.execute()
        return (filename, time.time() - start_t, None)

    except Exception as e:
        return (filename, 0, str(e))

# ==========================================
# ORQUESTADOR (PARALELISMO)
# ==========================================
def generate_dtm_production(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    # Buscar .laz y .las
    files = glob.glob(os.path.join(input_dir, "*.laz")) + glob.glob(os.path.join(input_dir, "*.las"))
    
    if not files:
        print(f"⚠️ No hay archivos en {input_dir}")
        return

    # Usamos CPU - 1 para no bloquear el sistema
    max_workers = max(1, multiprocessing.cpu_count() - 1)
    
    print("="*80)
    print(f"🚀 INICIANDO PROCESAMIENTO LIDAR PNOA (FUSIÓN ESPECTRAL + GEOMÉTRICA)")
    print(f"🔹 Archivos: {len(files)}")
    print(f"🔹 Hilos CPU: {max_workers}")
    print(f"🔹 Estrategia: SMRF (Win={SMRF_WINDOW}m) con exclusión de NIR (>{NIR_THRESHOLD})")
    print("="*80)

    start_global = time.time()
    total_files = len(files)

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(process_single_file, f, output_dir): f for f in files}
        completed_count = 0
        
        for future in concurrent.futures.as_completed(future_to_file):
            filename, elapsed, error = future.result()
            completed_count += 1
            
            percent = (completed_count / total_files) * 100
            bar_len = 30
            filled_len = int(bar_len * completed_count // total_files)
            bar = '█' * filled_len + '░' * (bar_len - filled_len)
            
            if error:
                print(f"\n❌ ERROR en {filename}: {error}")
            else:
                # Log limpio en una sola línea que se actualiza
                print(f"\r[{bar}] {percent:.1f}% | Procesado: {filename} ({elapsed:.1f}s)", end="", flush=True)

    print(f"\n\n✅ PROCESO FINALIZADO en {time.time() - start_global:.1f}s")
    print(f"📂 MDTs generados en: {os.path.abspath(output_dir)}")

if __name__ == "__main__":
    generate_dtm_production(INPUT_FOLDER, OUTPUT_FOLDER)
    