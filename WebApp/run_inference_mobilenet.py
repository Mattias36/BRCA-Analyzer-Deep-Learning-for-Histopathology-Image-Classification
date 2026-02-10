import openslide
from openslide.deepzoom import DeepZoomGenerator
import os
import sys
import numpy as np
from PIL import Image
import time
import json
import re
import xml.etree.ElementTree as ET
from shapely.geometry import Point, Polygon

import torch
import torch.nn as nn
from torchvision import models, transforms
import torch.nn.functional as F

from normalize_HnE import norm_HnE 


# ====================================================================
#  1. KONFIGURACJA
# ====================================================================

# --- ZMIANA: Podaj nazwę pliku z wagami MobileNet ---
PATH_TO_MODEL = r"MobileNet_weights\final_best_model_epoch_9.pth"

PATH_TO_SCAN = "99817.svs"
PATH_TO_XML = "99817.session.xml"

# --- ZMIANA: Nowa nazwa pliku wyjściowego ---
OUTPUT_JSON_PATH = "static/scans/breast_scan2_MODEL_MOBILENET_heatmap.json"

TILE_SIZE = 256
TARGET_LEVEL = 16 
INPUT_SIZE = 224
MAX_MEAN_THRESHOLD = 215
MIN_STD_THRESHOLD = 20

# ====================================================================
#  2. FUNKCJE POMOCNICZE (Bez zmian)
# ====================================================================
# (Skopiowane parsowanie XML i filtr tkanki)

CELLULARITY_REGEX = re.compile(r"(cellula.*:|tb-)\s*(\d+)")

def get_label_from_description(desc: str) -> str:
    if not desc: return "ignore"
    desc = desc.lower()
    match = CELLULARITY_REGEX.search(desc)
    if match:
        try:
            cellularity = int(match.group(2))
            if cellularity == 0: return "healthy"
            elif cellularity > 0: return "tumor"
        except Exception: pass
    if "healthy" in desc or "normal epithelial" in desc: return "healthy"
    if "malignant" in desc or "idc" in desc: return "tumor"
    return "ignore"

def parse_xml_annotations(xml_path: str) -> list:
    polygons = []
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        for graphic in root.findall(".//graphic"):
            description = graphic.get("description")
            mapped_label = get_label_from_description(description)
            if mapped_label == "ignore": continue
            coordinates = []
            for coord in graphic.findall(".//point"):
                x = float(coord.text.split(',')[0])
                y = float(coord.text.split(',')[1])
                coordinates.append((x, y))
            if len(coordinates) >= 3:
                polygons.append(Polygon(coordinates))
    except Exception as e:
        print(f"Błąd XML: {e}")
    return polygons

def has_tissue(tile_image: Image.Image) -> bool:
    try:
        tile_np = np.array(tile_image.convert('L'))
        mean_val = np.mean(tile_np)
        std_val = np.std(tile_np)
        if mean_val < MAX_MEAN_THRESHOLD and std_val > MIN_STD_THRESHOLD:
            return True
        return False
    except Exception: return False

# ====================================================================
#  3. DEFINICJA MODELU (SPECYFICZNA DLA MOBILENET)
# ====================================================================

def load_our_model(model_path, device):
    """Ładuje model MobileNetV2."""
    
    print("Ładowanie architektury MobileNetV2...")
    # 1. Ładujemy pusty MobileNetV2
    model = models.mobilenet_v2(weights=None)
    
    # 2. Modyfikujemy ostatnią warstwę (klasyfikator)
    # W MobileNetV2 ostatnia warstwa to 'classifier', który jest sekwencją.
    # Ostatni element tej sekwencji (indeks 1) to warstwa liniowa.
    
    # Pobieramy liczbę wejść do ostatniej warstwy
    num_ftrs = model.classifier[1].in_features
    
    # Podmieniamy klasyfikator na nasz (taki sam jak w treningu)
    # Zakładam, że w treningu też użyłeś Dropout + Linear
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.5),
        nn.Linear(num_ftrs, 2) # 2 klasy: healthy, tumor
    )
    
    # 3. Wczytujemy wagi
    try:
        model.load_state_dict(torch.load(model_path, map_location=device))
        print(f"Pomyślnie wczytano wagi MobileNet z: {model_path}")
    except Exception as e:
        print(f"BŁĄD KRYTYCZNY: Nie można wczytać wag MobileNet. Błąd: {e}")
        exit()
    
    model = model.to(device)
    model.eval()
    return model

val_transform = transforms.Compose([
    transforms.Resize(INPUT_SIZE + 32),
    transforms.CenterCrop(INPUT_SIZE),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

# ====================================================================
#  4. GŁÓWNA LOGIKA (Taka sama jak w ResNet)
# ====================================================================

def run_inference():
    print("Rozpoczynam inferencję MobileNet (tylko w regionach XML)...")
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Używam urządzenia: {device}")

    model = load_our_model(PATH_TO_MODEL, device)
    polygons = parse_xml_annotations(PATH_TO_XML)
    
    if not polygons:
        print("Brak poligonów w XML.")
        return

    try:
        slide = openslide.open_slide(PATH_TO_SCAN)
        tiles_gen = DeepZoomGenerator(slide, tile_size=TILE_SIZE, overlap=0, limit_bounds=False)
    except Exception as e:
        print(f"Błąd SVS: {e}")
        return

    cols, rows = tiles_gen.level_tiles[TARGET_LEVEL]
    heatmap_data = {}
    tiles_processed = 0
    start_time = time.time()
    
    with torch.no_grad():
        for row in range(rows):
            for col in range(cols):
                
                # --- Filtr XML ---
                level_0_coords = tiles_gen.get_tile_coordinates(TARGET_LEVEL, (col, row))[0]
                tile_center = Point(level_0_coords[0] + (TILE_SIZE//2), level_0_coords[1] + (TILE_SIZE//2))
                
                in_roi = False
                for poly in polygons:
                    if tile_center.within(poly):
                        in_roi = True
                        break
                if not in_roi: continue

                # --- Pobranie kafelka ---
                tile_name = f"{TARGET_LEVEL}_{col}_{row}"
                try:
                    tile_pil = tiles_gen.get_tile(TARGET_LEVEL, (col, row))
                except: continue

                # --- Filtr Tkanki ---
                if not has_tissue(tile_pil): continue
                
                tiles_processed += 1

                # --- Normalizacja ---
                try:
                    tile_np = np.array(tile_pil.convert('RGB'))
                    norm_img_np, _, _ = norm_HnE(tile_np)
                    tile_pil = Image.fromarray(norm_img_np)
                except: continue

                # --- Predykcja ---
                tile_tensor = val_transform(tile_pil).unsqueeze(0).to(device)
                outputs = model(tile_tensor)
                probs = F.softmax(outputs, dim=1)
                tumor_prob = probs[0][1].item()
                
                heatmap_data[tile_name] = round(tumor_prob, 4)

            if (row + 1) % 100 == 0:
                print(f"...przetworzono wiersz {row+1}/{rows}")
    
    end_time = time.time()
    total_time_seconds = end_time - start_time
    print(f"\nAnaliza zakończona w {total_time_seconds:.2f} sekund.")
    if tiles_processed > 0:
        avg_time_per_tile_ms = (total_time_seconds * 1000) / tiles_processed
        print(f"Średni czas na 1 kafelek: {avg_time_per_tile_ms:.2f} ms")
    else:
        print("Nie przetworzono żadnych kafelków.")
    print(f"Przeanalizowano i zapisano wyniki dla {tiles_processed} kafelków (wewnątrz regionów).")
    # Zapis
    try:
        os.makedirs(os.path.dirname(OUTPUT_JSON_PATH), exist_ok=True)
        with open(OUTPUT_JSON_PATH, 'w') as f:
            json.dump(heatmap_data, f)
        print(f"Zapisano heatmapę MobileNet: {OUTPUT_JSON_PATH}")
    except Exception as e:
        print(f"Błąd zapisu JSON: {e}")

if __name__ == "__main__":
    run_inference()