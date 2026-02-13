import pdal
import json
import os
import glob

# Configuracion de directorios
INPUT_FOLDER = "data/01_raw/"
OUTPUT_FOLDER = "data/02_intermediate/metadata_json/"

def extract_full_info(input_dir, output_dir):
    # Crear carpeta de salida si no existe
    os.makedirs(output_dir, exist_ok=True)

    # Buscar archivos .laz y .las
    files = glob.glob(os.path.join(input_dir, "*.laz")) + \
            glob.glob(os.path.join(input_dir, "*.las"))
    
    total_files = len(files)
    
    if not files:
        print(f"No se encontraron archivos en {input_dir}")
        return

    print(f"Extrayendo INFORMACIÓN COMPLETA (Metadata + Estadísticas) de {total_files} archivos de {INPUT_FOLDER}")
    print("   Nota: Esto leerá todos los puntos, tardará unos segundos por archivo.")
    
    # Cabecera de la tabla formateada
    print("-" * 80)
    print(f"{'ARCHIVO PROCESADO':<40} |  {'PROGRESO DEL LOTE'}")
    print("-" * 80)

    # Usamos enumerate para saber en qué número de archivo vamos (i)
    for i, filepath in enumerate(files, 1):
        filename = os.path.basename(filepath)
        json_name = f"{os.path.splitext(filename)[0]}.json"
        output_path = os.path.join(output_dir, json_name)

        # Mostrar barra de progreso (Dinamica)
        # Calculamos el porcentaje
        percent = (i / total_files) * 100
        bar_length = 20
        filled_length = int(bar_length * i // total_files)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        # Imprimimos usando \r al principio y end='' al final utilizando flush=True.
        msg_progress = f"\r{filename:<40} |  {bar} {percent:5.1f}% ({i}/{total_files})"
        print(msg_progress, end="", flush=True)

        # PIPELINE CON LA INFORMACION COMPLETA
        pipeline_json = {
            "pipeline": [
                {
                    "type": "readers.las",
                    "filename": filepath
                    # Lectura de toda la informacion de pdal info.
                },
                {
                    "type": "filters.stats"
                    # Añadimos stats sin especificar dimensiones.
                    # Esto calcula estadísticas de todo lo que encuentre.
                }
            ]
        }

        try:
            # Ejecutamos el pipeline
            pipeline = pdal.Pipeline(json.dumps(pipeline_json))
            pipeline.execute()
            
            # Obtener los metadatos completos
            # pipeline.metadata contiene ahora la cabecera Y las estadísticas
            full_metadata = pipeline.metadata
            
            # Guardar el JSON completo en disco
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(full_metadata, f, indent=4)

            # Mostrar mensaje final (Estático)
            # Una vez terminado, volvemos al inicio de la línea con \r y escribimos el mensaje de éxito.
            print(f"\r{filename:<40} |  Guardado Correctamente{' '*13}") 

        except Exception as e:
            # Si falla, mostramos el error y pasamos a la siguiente línea
            print(f"\r{filename:<40} |  Error: {e}{' '*28}")

    print("-" * 80)
    print(f"\nProceso terminado. Los JSON con toda la info están en: {output_dir}")

if __name__ == "__main__":
    extract_full_info(INPUT_FOLDER, OUTPUT_FOLDER)