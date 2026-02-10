import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import numpy as np
import cv2
import os

# Biblioteka Grad-CAM
from pytorch_grad_cam import GradCAM
from pytorch_grad_cam.utils.image import show_cam_on_image
from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget

# ================= KONFIGURACJA =================
# Ścieżka do modelu 
MODEL_PATH = r"MobileNet_weights\final_best_model_epoch_9.pth"

# Ścieżka do obrazka, 
IMAGE_PATH = r"static\images_xai\test_files_mobilenet\test_tumor.png" 

# Gdzie zapisać wynik
OUTPUT_PATH = r"static\images_xai\xai_results_mobilenet\xai_result_test_mb.png"
# ================================================

def load_model_for_xai(path):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # 1. Inicjalizacja czystego MobileNetV2
    model = models.mobilenet_v2(weights=None)
    
    # 2. Przebudowa głowicy (TAK SAMO JAK W TRENINGU)
    # MobileNet ma 'classifier', a nie 'fc'. 
    # classifier[1] to warstwa Linear.
    in_features = model.classifier[1].in_features
    
    model.classifier = nn.Sequential(
        nn.Dropout(p=0.5),
        nn.Linear(in_features, 2)  # [Healthy, Tumor]
    )
    
    # 3. Ładowanie wag
    try:
        # strict=False pozwoli zignorować ewentualne śmieci, 

        checkpoint = torch.load(path, map_location=device, weights_only=False) # Dodano weights_only=False dla kompatybilności
        model.load_state_dict(checkpoint)
        print(f"Model MobileNet wczytany z: {path}")
    except Exception as e:
        print(f"BŁĄD krytyczny ładowania modelu: {e}")
        print("Sprawdź, czy na pewno podajesz plik .pth od MobileNeta, a nie od ResNeta!")
        exit()
        
    model.eval()
    model.to(device)
    return model, device

def run_gradcam():
    # 1. Przygotowanie obrazu
    if not os.path.exists(IMAGE_PATH):
        print(f"BŁĄD: Nie znaleziono pliku: {IMAGE_PATH}")
        return

    img_pil = Image.open(IMAGE_PATH).convert('RGB')
    img_pil = img_pil.resize((224, 224))
    
    preprocess = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    
    input_tensor = preprocess(img_pil).unsqueeze(0)

    # 2. Ładowanie modelu
    model, device = load_model_for_xai(MODEL_PATH)
    input_tensor = input_tensor.to(device)

    # 3. Konfiguracja Grad-CAM dla MobileNetV2
    # Ostatnia warstwa konwolucyjna to ostatni element bloku 'features'
    target_layers = [model.features[-1]]
    
    cam = GradCAM(model=model, target_layers=target_layers)

    # 4. Generowanie (Klasa 1 = Tumor)
    # Upewnij się, że w treningu Tumor miał indeks 1. Zazwyczaj tak jest (alfabetycznie: Healthy=0, Tumor=1)
    grayscale_cam = cam(input_tensor=input_tensor, targets=[ClassifierOutputTarget(1)])
    grayscale_cam = grayscale_cam[0, :]

    # 5. Wizualizacja
    rgb_img = np.float32(img_pil) / 255
    visualization = show_cam_on_image(rgb_img, grayscale_cam, use_rgb=True)

    # 6. Zapis
    Image.fromarray(visualization).save(OUTPUT_PATH)
    print(f"Sukces! Wynik zapisano jako: {OUTPUT_PATH}")

if __name__ == "__main__":
    run_gradcam()