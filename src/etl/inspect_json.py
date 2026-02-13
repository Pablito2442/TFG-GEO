import json
import os
import glob
import pandas as pd
from datetime import datetime

# Configuracion de directorios
JSON_FOLDER = "data/02_intermediate/metadata_json/"

def inspect_json_metadata(folder_path):
    # Buscar archivos .json
    files = glob.glob(os.path.join(folder_path, "*.json"))
    
    if not files:
        print(f"No se encontraron archivos JSON en: {folder_path}")
        print("   (Ejecuta primero el script de extracción con barra de progreso)")
        return

    print(f"Auditando proyecto desde {len(files)} ficheros de metadatos...")
    
    summary_data = []
    total_points = 0
    total_area = 0

    for filepath in files:
        filename = os.path.basename(filepath)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Declaracion de acceso  a la estrucutura del json por secciones
            meta = data.get("metadata", {})
            reader = meta.get("readers.las", {})            # metadata -> readers.las (Cabecera)
            stats_block = meta.get("filters.stats", {})     # metadata -> filters.stats (Estadísticas)
            
            # Extraccion de datos basicos
            count = reader.get("count", 0)                  # Numero de puntos
            total_points += count
        
            year = reader.get("creation_year", 0)           # Año de Recopilacion de datos
            
            # CRS (Sistema de Coordenadas)
            crs_name = reader.get("srs", {}).get("json", {}).get("name", "Desconocido")
            if len(crs_name) > 25: crs_name = crs_name[:25] + "..."

            # --- 3. EXTRACCIÓN GEOMÉTRICA (BBox & Densidad)
            bbox = stats_block.get("bbox", {}).get("native", {}).get("bbox", {})
            minx, maxx = bbox.get("minx", 0), bbox.get("maxx", 0)       # Limites Oeste y Este
            miny, maxy = bbox.get("miny", 0), bbox.get("maxy", 0)       # Limites Sur y Norte
            
            area = (maxx - minx) * (maxy - miny)
            if area > 0:
                density = count / area
                total_area += area
            else:
                density = 0

            # Extraccion de estadisticas
            stats_list = stats_block.get("statistic", [])
            
            # Variables temporales para buscar en la lista
            nir_max = 0
            cls_min, cls_max = 0, 0
            rgb_max = 0
            
            for stat in stats_list:
                name = stat.get("name")
                if name == "Infrared":
                    nir_max = int(stat.get("maximum", 0))
                elif name == "Classification":
                    cls_min = int(stat.get("minimum", 0))
                    cls_max = int(stat.get("maximum", 0))
                elif name == "Red":
                    rgb_max = int(stat.get("maximum", 0))
                elif name == "NumberOfReturns":
                    max_returns = int(stat.get("maximum", 0))

            # Interpretacion de los datos
            nir_status = f" Sí ({nir_max})" if nir_max > 0 else " NO"       # Presencia de infrarojos
            rgb_status = " Sí" if rgb_max > 0 else " NO"                    # Presencia de valores RGB
            
            classes_range = f"{cls_min}-{cls_max}"                          # Sistemas de clasificacion

            
            # Almacenamiento de los datos para visualizacion
            summary_data.append({
                "Archivo": filename.replace(".json", ""),
                "Año Publ": year,
                "Pts (M)": round(count / 1e6, 2),
                "Densidad": round(density, 2),
                "Clases": classes_range,
                "RGB": rgb_status,
                "NIR (Max)": nir_status,
                "Rebotes": max_returns,
                "Sistema de coordenadas": crs_name
            })

        except Exception as e:
            print(f"Error leyendo {filename}: {e}")

    # Representacion de informacion en formato tabla
    df = pd.DataFrame(summary_data)
    
    if not df.empty:
        # 1. Imprimir en consola (para validación rápida)
        markdown_table = df.to_markdown(index=False)
        print(markdown_table)
        
        # 2. Guardar en archivo Markdown (para documentación)
        output_md_path = os.path.join(os.path.dirname(folder_path), "audit_report.md")
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write("# Auditoría de Calidad de Datos LiDAR\n\n")
            f.write(f"- **Fecha de generación:** {now}\n")
            f.write(f"- **Total Archivos:** {len(files)}\n")
            f.write(f"- **Total Puntos:** {total_points:,}\n")
            f.write(f"- **Área Total:** {total_area/10000:.2f} Hectáreas\n\n")
            f.write("## Tabla Detallada por Archivos\n")
            f.write(markdown_table)
            f.write("\n")
        
        print(f"\nReporte guardado en: {output_md_path}")

if __name__ == "__main__":
    inspect_json_metadata(JSON_FOLDER)
