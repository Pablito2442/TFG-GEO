import pdal
import json
import time
import os

# RUTAS DE ENTRADA Y SALIDA
LAS_ENTRADA = "data/01_raw/PNOA_2024_AND_460-4063_H30_NPC01.laz"            # Archivo original con clasificación automática (sin limpieza ni reclasificación)
GPKG_INVERNADEROS = "data/00_manual_reclasification/entrenamiento.gpkg"     # Poligonos de invernaderos (tamaño real, sin buffer)
GPKG_LIMPIEZA = "data/00_manual_reclasification/zonas_buffer.gpkg"          # Buffer de limpieza inmediaciones de los invernaderos
LAS_SALIDA = "data/00_manual_reclasification/ground_truth_limpio_y_clasificado.laz"     # Archivo de salida con la reclasificación

# DEFINICIÓN DEL PIPELINE PDAL
def build_pipeline():
    """Construye el pipeline de PDAL como una lista de diccionarios (etapas)."""
    
    pipeline = [
        # --- FASE 0: LECTURA ---
        {
            "type": "readers.las",
            "filename": LAS_ENTRADA
        },
        
        # --- FASE 1: FILTRADO DE RUIDO ---
        # Eliminamos puntos que son errores del sensor o ruido conocido (Clases 7 y 12)
        {
            "type": "filters.range",
            "limits": "Classification![12:12], Classification![7:7]"
        },

        # --- FASE 2: ANÁLISIS GEOMÉTRICO (PREPARACIÓN PARA LIMPIEZA) ---
        # Calculamos cómo de "plano" es el entorno de cada punto (Planarity)
        {
            "type": "filters.covariancefeatures",
            "knn": 20,
            "feature_set": "Planarity"
        },
        # Suavizamos las clasificaciones aisladas observando a los 50 vecinos más cercanos
        {
            "type": "filters.neighborclassifier",
            "domain": "Classification[1:1]", 
            "k": 50
        },

        # --- FASE 3: RECLASIFICACIÓN Y LIMPIEZA DEL SUELO ---
        # 3.1. Usamos 'UserUserData' como variable temporal (bandera)
        {
            "type": "filters.ferry",
            "dimensions": "=>UserUserData"
        },
        # 3.2. Marcamos los puntos que caen dentro de los polígonos de limpieza
        {
            "type": "filters.overlay",
            "dimension": "UserUserData",
            "datasource": GPKG_LIMPIEZA,
            "layer": "zonas_buffer", 
            "column": "clase"
        },
        # 3.3. REGLA LÓGICA: Si el punto está en zona de limpieza (UserData > 0)
        # Y estaba clasificado como Vegetación/Edificio (4 o 6) Y es muy plano (> 0.15)
        # ENTONCES lo convertimos a Suelo (Clase 2).
        {
            "type": "filters.assign",
            "value": "Classification = 2 WHERE UserUserData > 0 && (Classification == 4 || Classification == 6) && Planarity > 0.15"
        },
        # 3.4. Reseteamos la variable temporal para no arrastrar basura
        {
            "type": "filters.assign",
            "value": "UserUserData = 0"
        },

        # --- FASE 4: SEGMENTACIÓN DE INVERNADEROS (INSTANCIAS Y SEMÁNTICA) ---
        # 4.1. Utilizamos la dimensión 'PointSourceId' poniéndola a 0
        {
            "type": "filters.assign",
            "value": "PointSourceId = 0"
        },
        # 4.2. SEGMENTACIÓN DE INSTANCIAS: Utilizamos el ID único ('uid') de cada polígono en los puntos
        {
            "type": "filters.overlay",
            "dimension": "PointSourceId", 
            "datasource": GPKG_INVERNADEROS,
            "layer": "zonas", 
            "column": "uid"
        },
        # 4.3. SEGMENTACIÓN SEMÁNTICA: Si tiene un ID de invernadero (>0), lo pasamos a la Clase 32
        {
            "type": "filters.assign",
            "value": "Classification = 32 WHERE PointSourceId > 0"
        },
        
        # --- FASE 5: ESCRITURA Y GUARDADO ---
        # Guardamos en formato 8 para asegurar que se conservan los colores RGB e Infrarrojo
        {
            "type": "writers.las",
            "filename": LAS_SALIDA,
            "major_version": 1,
            "minor_version": 4, 
            "dataformat_id": 8,
            "compression": "true"
        }
    ]
    
    return {"pipeline": pipeline}

# BLOQUE DE EJECUCIÓN PRINCIPAL
if __name__ == "__main__":
    # Comprobación de seguridad: verificar que los inputs existen
    if not os.path.exists(LAS_ENTRADA):
        print(f"ERROR: No se encuentra el archivo de entrada en {LAS_ENTRADA}")
        exit(1)
        
    start_time = time.time()
    
    try:
        print("1. Cargando configuración JSON...")
        pipeline_json = build_pipeline()
        
        print("2. Ejecutando motor PDAL (Cálculo Geometría -> Limpieza -> Segmentación)...")
        pipeline = pdal.Pipeline(json.dumps(pipeline_json))
        puntos_procesados = pipeline.execute()
        
        tiempo_total = time.time() - start_time
        
        print("\nPROCESO FINALIZADO CON ÉXITO")
        print(f"Tiempo de ejecución: {tiempo_total:.2f} segundos")
        print(f"Archivo guardado en: {LAS_SALIDA}")
        
    except RuntimeError as e:
        print("\nERROR GRAVE EN EL MOTOR PDAL:")
        print(str(e))