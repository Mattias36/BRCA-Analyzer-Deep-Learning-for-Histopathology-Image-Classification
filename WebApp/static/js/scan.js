// static/js/scan.js (Wersja 8.0 - Dynamiczne Generowanie)

document.addEventListener('DOMContentLoaded', (event) => {
    
    // --- 1. KONFIGURACJA ---
    const DZI_PATH = "/static/scans/breast_scan2.dzi";
    const TARGET_LEVEL = 16;
    const BATCH_SIZE = 500;
    const MIN_CONFIDENCE_THRESHOLD = 0.1; 
    const MAX_OPACITY = 0.5; 

    let viewer;
    let currentOverlays = []; 
    const tooltipEl = document.getElementById('heatmap-tooltip');
    const loadingSpinner = document.getElementById('loading-spinner');
    const viewerElement = document.getElementById('openseadragon-viewer');


    // --- NOWA LOGIKA: Przechowywanie załadowanych danych ---
    // Przechowujemy tu dane, aby nie generować ich ponownie
    const loadedHeatmaps = {
        'model-resnet': null,
        'model-mobilenet': null,
        'truth': null
    };
    
    // Przechowujemy dynamicznie tworzone radio buttony
    let controlsContainer = null;

    // --- 2. INICJALIZACJA APLIKACJI ---
    function initApp() {
        viewer = OpenSeadragon({
            id: "openseadragon-viewer",
            prefixUrl: "https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.1/images/",
            tileSources: DZI_PATH,
            showNavigator: true
        });

        // Podłącz przyciski "Generuj"
        document.getElementById("btn-gen-resnet").addEventListener('click', () => handleGenerateClick('model-resnet'));
        document.getElementById("btn-gen-mobilenet").addEventListener('click', () => handleGenerateClick('model-mobilenet'));
        document.getElementById("btn-gen-truth").addEventListener('click', () => handleGenerateClick('truth'));
        
        // Stwórz kontener na radio buttony (ale na razie go nie dodawaj)
        createOsdControls();
    }

    // --- 3. LOGIKA GENEROWANIA (AJAX/API) ---
    async function handleGenerateClick(type) {
        
        // Jeśli już to wygenerowaliśmy, po prostu to pokaż
        if (loadedHeatmaps[type]) {
            console.log(`Dane dla ${type} już istnieją. Pokazuję.`);
            // Znajdź odpowiedni radio button i go zaznacz
            document.querySelector(`input[value="${type}"]`).checked = true;
            drawHeatmap(type);
            return;
        }

        // Pokaż spinner
        loadingSpinner.style.display = 'block';

        console.log(`Wysyłam żądanie wygenerowania dla: ${type}`);
        let apiType = type;
        // Mapuj nasze wewnętrzne ID na typy, które rozumie API
        if (type === 'model-resnet') apiType = 'resnet';
        if (type === 'model-mobilenet') apiType = 'mobilenet';

        try {
            // Wyślij żądanie POST do serwera Flask
            const response = await fetch('/api/generate_heatmap', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type: apiType })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || `Błąd serwera: ${response.status}`);
            }

            const result = await response.json();
            console.log("Serwer odpowiedział:", result.message);

            // Teraz, gdy mamy ścieżkę do pliku, wczytaj go
            const dataResponse = await fetch(result.json_path);
            loadedHeatmaps[type] = await dataResponse.json();

            // Dodaj nowy przycisk radio i narysuj heatmapę
            addRadioButtonToControls(type);
            drawHeatmap(type);

        } catch (error) {
            console.error("Błąd podczas generowania:", error);
            alert(`Wystąpił błąd: ${error.message}`);
        } finally {
            // Ukryj spinner
            loadingSpinner.style.display = 'none';
        }
    }

    // --- 4. DYNAMICZNE TWORZENIE KONTROLEK OSD ---
    
    // Tworzy PUSTY kontener
    function createOsdControls() {
        controlsContainer = document.createElement("div");
        controlsContainer.className = "heatmap-controls-overlay";
        // Domyślnie dodajemy "Ukryj"
        controlsContainer.appendChild(createRadioButton("radio-none-overlay", "none", "Hide", false));
    }
    
    // Dodaje NOWY przycisk do kontenera
    function addRadioButtonToControls(type) {
        let label = "";
        if (type === 'model-resnet') label = "Prediction (ResNet)";
        if (type === 'truth') label = "Real adnotations";
        if (type === 'model-mobilenet') label = "Prediction  (MobileNet)";
        
        const radioId = `radio-${type}-overlay`;
        
        // Nie dodawaj, jeśli już istnieje
        if (document.getElementById(radioId)) {
            document.getElementById(radioId).checked = true; // Po prostu zaznacz
            return;
        }

        const newRadio = createRadioButton(radioId, type, label, true);
        
        // Dodaj na początek listy (przed "Ukryj")
        controlsContainer.prepend(newRadio);
        
        // Jeśli to pierwszy przycisk, dodaj cały kontener do OSD
        if (controlsContainer.childElementCount === 2) { // (bo "Ukryj" już tam jest)
             viewer.addControl(controlsContainer, {
                anchor: OpenSeadragon.ControlAnchor.NONE
             });
        }
    }
    
    // Funkcja pomocnicza do tworzenia przycisków
    function createRadioButton(id, value, label, checked = false) {
        const radioLabel = document.createElement("label");
        const radio = document.createElement("input");
        radio.type = "radio";
        radio.id = id;
        radio.name = "heatmap-toggle-overlay";
        radio.value = value;
        radio.checked = checked;
        
        radio.addEventListener('change', () => drawHeatmap(value));
        
        radioLabel.appendChild(radio);
        radioLabel.appendChild(document.createTextNode(" " + label));
        return radioLabel;
    }


    // --- 5. FUNKCJA DO RYSOWANIA (taka jak w Wersji 6.0) ---
    function drawHeatmap(dataType) {
        console.log(`Rysuję heatmapę dla: ${dataType}`);
        currentOverlays.forEach(overlayElement => viewer.removeOverlay(overlayElement));
        currentOverlays = [];

        if (dataType === 'none') {
            return; 
        }
        
        const data = loadedHeatmaps[dataType];
        if (!data) {
            console.warn(`Brak danych dla ${dataType}. Nic do narysowania.`);
            return;
        }
        
        // Reszta tej funkcji jest DOKŁADNIE TAKA SAMA jak w Wersji 6.0
        // (pętla 'processBatch', logika tooltipa, itd.)
        // ... (skopiuj tutaj resztę funkcji drawHeatmap z Wersji 6.0) ...
        // ...
        const entries = Object.entries(data);
        let i = 0;
        function processBatch() {
             for (let j = 0; j < BATCH_SIZE && i < entries.length; j++, i++) {
                const [tileKey, probability] = entries[i];
                const parts = tileKey.split('_');
                const level = parseInt(parts[0]);
                const col = parseInt(parts[1]);
                const row = parseInt(parts[2]);
                if (level !== TARGET_LEVEL) continue;
                let r, g, b, opacity, confidence, className;
                if (probability > 0.5) { // TUMOR
                    r = 255; g = 0; b = 0;
                    className = 'Tumor';
                    confidence = (probability - 0.5) * 2;
                    opacity = confidence * MAX_OPACITY;
                } else { // HEALTHY
                    r = 0; g = 255; b = 0;
                    className = 'Healthy';
                    confidence = (0.5 - probability) * 2;
                    opacity = confidence * MAX_OPACITY;
                }
                if (dataType.startsWith('model-') && opacity < MIN_CONFIDENCE_THRESHOLD * MAX_OPACITY) {
                    continue; 
                }
                const rect = viewer.source.getTileBounds(level, col, row);
                const overlayEl = document.createElement("div");
                overlayEl.style.backgroundColor = `rgba(${r}, ${g}, ${b}, ${opacity})`;
                let tooltipText = "";
                if (dataType.startsWith('model-')) {
                    const confidencePercent = (confidence * 100).toFixed(1);
                    tooltipText = `Predcition: ${className}<br>Confidence: ${confidencePercent}%`;
                } else {
                    tooltipText = `Actual: ${className}`;
                }
                overlayEl.addEventListener('mouseover', (e) => {
                    tooltipEl.innerHTML = tooltipText; 
                    tooltipEl.style.display = 'block';
                });
                overlayEl.addEventListener('mousemove', (e) => {
                    tooltipEl.innerHTML = tooltipText;
                    tooltipEl.style.display = 'block';
                
                    const rect = viewerElement.getBoundingClientRect();
                    const tooltipWidth  = tooltipEl.offsetWidth;
                    const tooltipHeight = tooltipEl.offsetHeight;
                
                    // Pozycje RELATYWNIE do kontenera viewer-a
                    let x = e.clientX - rect.left + 15;
                    let y = e.clientY - rect.top  + 15;
                
                    // Clamp w poziomie (żeby nie wychodził poza viewer)
                    if (x + tooltipWidth > rect.width - 10) {
                        x = rect.width - tooltipWidth - 10;
                    }
                    if (x < 10) x = 10;
                
                    // Clamp w pionie
                    if (y + tooltipHeight > rect.height - 10) {
                        y = rect.height - tooltipHeight - 10;
                    }
                    if (y < 10) y = 10;
                
                    tooltipEl.style.left = x + "px";
                    tooltipEl.style.top  = y + "px";
                });
                
                

                overlayEl.addEventListener('mouseout', (e) => {
                    tooltipEl.style.display = 'none';
                });
                viewer.addOverlay({
                    element: overlayEl,
                    location: rect
                });
                currentOverlays.push(overlayEl); 
            }
            if (i < entries.length) {
                setTimeout(processBatch, 0); 
            } else {
                console.log(`Rysowanie zakończone. Narysowano ${currentOverlays.length} kafelków.`);
            }
        }
        processBatch();
    }

    // --- 6. URUCHOM APLIKACJĘ ---
    initApp();
});