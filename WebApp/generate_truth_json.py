import openslide
from openslide.deepzoom import DeepZoomGenerator
import os
import sys
import numpy as np
import xml.etree.ElementTree as ET
from shapely.geometry import Point, Polygon
import json
import time
import re

# ====================================================================
#  1. KONFIGURACJA (Dostosuj te ścieżki!)
# ====================================================================

# Ustaw ścieżkę do skanu SVS, który ma być bazą
PATH_TO_SCAN = "99817.svs" 

# Ustaw ścieżkę do pliku XML z adnotacjami
# Zakładam, że jest w tym samym folderze, ale możesz podać pełną ścieżkę
PATH_TO_XML = "99817.session.xml" # <-- WAŻNE: Podaj poprawną nazwę pliku XML

# Plik wyjściowy JSON (trafi do folderu static)
OUTPUT_JSON_PATH = "static/scans/breast_scan2_TRUTH_heatmap.json"

# Parametry siatki (muszą być takie same jak w 'run_inference.py')
TILE_SIZE = 256
TARGET_LEVEL = 16 # Poziom, na którym analizujemy

# ====================================================================
#  2. FUNKCJE PARSOWANIA XML (Z naszego skryptu treningowego)
# ====================================================================

# Regex do parsowania XML (sprawdzony)
CELLULARITY_REGEX = re.compile(r"(cellula.*:|tb-)\s*(\d+)")

def get_label_from_description(desc: str) -> str:
    """Interpretuje atrybut 'description' z pliku XML."""
    if not desc:
        return "ignore"
    desc = desc.lower()
    match = CELLULARITY_REGEX.search(desc)
    
    if match:
        try:
            cellularity = int(match.group(2))
            if cellularity == 0:
                return "healthy"
            elif cellularity > 0:
                return "tumor"
        except Exception:
            pass
    
    if "healthy" in desc or "normal epithelial" in desc:
        return "healthy"
    if "malignant" in desc or "idc" in desc or "dcis" in desc:
        return "tumor"
    return "ignore"

def parse_xml_annotations(xml_path: str) -> list:
    """Parsuje plik .xml Sedeen i zwraca listę poligonów z etykietami."""
    polygons = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for graphic in root.findall(".//graphic"):
            description = graphic.get("description")
            mapped_label = get_label_from_description(description)
            if mapped_label == "ignore":
                continue
            coordinates = []
            for coord in graphic.findall(".//point"):
                x = float(coord.text.split(',')[0])
                y = float(coord.text.split(',')[1])
                coordinates.append((x, y))
            if len(coordinates) >= 3:
                # Zapisujemy poligon i etykietę (0.0 lub 1.0)
                label_value = 1.0 if mapped_label == "tumor" else 0.0
                polygons.append((Polygon(coordinates), label_value))
    except Exception as e:
        print(f"Błąd podczas parsowania XML {xml_path}: {e}")
    return polygons

# ====================================================================
#  3. GŁÓWNA LOGIKA
# ====================================================================

def generate_truth_map():
    print(f"Rozpoczynam generowanie 'Mapy Prawdy' z pliku {PATH_TO_XML}...")
    
    # --- Krok 1: Wczytaj poligony z XML ---
    polygons = parse_xml_annotations(PATH_TO_XML)
    if not polygons:
        print("BŁĄD: Nie znaleziono żadnych poligonów 'healthy' lub 'tumor' w pliku XML.")
        return
    print(f"Znaleziono {len(polygons)} poligonów z adnotacjami.")

    # --- Krok 2: Wczytaj skan (tylko do pobrania siatki) ---
    try:
        slide = openslide.open_slide(PATH_TO_SCAN)
        tiles_gen = DeepZoomGenerator(slide, 
                                      tile_size=TILE_SIZE, 
                                      overlap=0, # Ważne: 0 overlapu
                                      limit_bounds=False)
    except Exception as e:
        print(f"BŁĄD: Nie udało się otworzyć pliku SVS: {PATH_TO_SCAN}. Błąd: {e}")
        return

    if TARGET_LEVEL > tiles_gen.level_count - 1:
        print(f"BŁĄD: Poziom {TARGET_LEVEL} nie istnieje. Najwyższy poziom to {tiles_gen.level_count - 1}.")
        return

    cols, rows = tiles_gen.level_tiles[TARGET_LEVEL]
    print(f"Przetwarzam siatkę {cols}x{rows} na poziomie {TARGET_LEVEL}...")

    # Słownik na wyniki
    truth_heatmap_data = {}
    tiles_found = 0
    start_time = time.time()

    # --- Krok 3: Pętla przez kafelki i sprawdzanie poligonów ---
    for row in range(rows):
        for col in range(cols):
            tile_name = f"{TARGET_LEVEL}_{col}_{row}"
            
            # Pobierz współrzędne środka kafelka
            level_0_coords = tiles_gen.get_tile_coordinates(TARGET_LEVEL, (col, row))[0]
            tile_center_point = Point(level_0_coords[0] + (TILE_SIZE // 2), 
                                      level_0_coords[1] + (TILE_SIZE // 2))
            
            # Sprawdź, czy środek kafelka jest w którymś z poligonów
            for polygon, label_value in polygons:
                if tile_center_point.within(polygon):
                    truth_heatmap_data[tile_name] = label_value
                    tiles_found += 1
                    break # Znaleźliśmy, przejdź do następnego kafelka
        
        if (row + 1) % 100 == 0:
            print(f"  ...przeskanowano wiersz {row+1}/{rows}.")

    end_time = time.time()
    print(f"\nAnaliza XML zakończona w {end_time - start_time:.2f} sekund.")
    print(f"Znaleziono {tiles_found} kafelków wewnątrz oznaczonych regionów.")

    # --- Krok 4: Zapisz JSON ---
    try:
        os.makedirs(os.path.dirname(OUTPUT_JSON_PATH), exist_ok=True)
        with open(OUTPUT_JSON_PATH, 'w') as f:
            json.dump(truth_heatmap_data, f)
        print(f"Pomyślnie zapisano mapę prawdy JSON w: {OUTPUT_JSON_PATH}")
    except Exception as e:
        print(f"BŁĄD: Nie udało się zapisać pliku JSON. Błąd: {e}")

if __name__ == "__main__":
    generate_truth_map()