import pdal
import json
import os
import glob
import time
import sys

# Configuracion de directorios
INPUT_FOLDER = "data/01_raw/"
OUTPUT_FOLDER = "data/03_processed/mdt/"
RESOLUTION = 1.0  # 1 metro/píxel (Estándar PNOA para MDT)

def generate_dtm_batch(input_dir, output_dir):
    # Crear carpeta de salida
    os.makedirs(output_dir, exist_ok=True)
    
    files = glob.glob(os.path.join(input_dir, "*.laz")) + \
            glob.glob(os.path.join(input_dir, "*.las"))
    
    total_files = len(files)
    
    if not files:
        print(f"No hay archivos en {input_dir}")
        return

    print(f"Generando MDT (Modelo Digital del Terreno) para {total_files} archivos...")
    print(f"   Configuración: Filtro Clase 2 (Suelo) | Resolución: {RESOLUTION}m | Salida: GeoTIFF")
    
    print("-" * 80)
    print(f"{'ARCHIVO GENERADO':<41} |  {'ESTADO'}")
    print("-" * 80)

    for i, filepath in enumerate(files, 1):
        filename = os.path.basename(filepath)
        filename_no_ext = os.path.splitext(filename)[0]
        output_filename = f"{filename_no_ext}_MDT.tif"
        output_path = os.path.join(output_dir, output_filename)

        # Barra de progreso
        percent = (i / total_files) * 100
        bar_length = 20
        filled_length = int(bar_length * i // total_files)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        msg_progress = f"\r{filename:<41} |  {bar} {percent:5.1f}% ({i}/{total_files})"
        print(msg_progress, end="", flush=True)

        # PIPELINE DE PROCESAMIENTO
        pipeline_json = {
            "pipeline": [
                {
                    "type": "readers.las",
                    "filename": filepath
                },
                {
                    # Filtro para recopilacion de puntos con clase 2 (Suelo)
                    "type": "filters.range",
                    "limits": "Classification[2:2]"
                },
                {
                    # Estructura de ficheros raster (GeoTIFF)
                    "type": "writers.gdal",
                    "filename": output_path,
                    "resolution": RESOLUTION, 
                    "output_type": "mean",              # Promedio de alturas en cada celda de 1x1m
                    "gdalopts": "COMPRESS=DEFLATE",     # Compresión para que ocupen poco
                    "nodata": -9999                     # Valor para zonas sin datos
                }
            ]
        }

        try:
            start_t = time.time()
            
            # Ejecucion de la pipeline
            pipeline = pdal.Pipeline(json.dumps(pipeline_json))
            pipeline.execute()
            
            elapsed = time.time() - start_t

            print(f"\r{output_filename:<41} |  Guardado Correctamente ({elapsed:.1f}s){' '*13}") 

        except RuntimeError as e:
            print(f"\r{filename:<41} |  Error PDAL: {e}{' '*20}")
        except Exception as e:
            print(f"\r{filename:<41} |  Error Python: {e}{' '*20}")

    print("-" * 80)
    print(f"\nProceso completado. Los GeoTIFF están en: {output_dir}")

if __name__ == "__main__":
    generate_dtm_batch(INPUT_FOLDER, OUTPUT_FOLDER)