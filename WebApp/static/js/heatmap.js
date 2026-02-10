// static/js/scan.js (Wersja 3.0 - Wydajna, Kolorowa i z Pewnością)

document.addEventListener('DOMContentLoaded', (event) => {
    
    // --- 1. KONFIGURACJA ---
    const DZI_PATH = "/static/scans/breast_scan2.dzi";
    const HEATMAP_JSON_PATH = "/static/scans/breast_scan2_heatmap.json";
    
    const TARGET_LEVEL = 16;
    const BATCH_SIZE = 500; // Ile nakładek rysować na raz

    // --- NOWA KONFIGURACJA ---
    // Jaką pewność musi mieć model (np. 10%), abyśmy w ogóle coś narysowali?
    // (0.1 oznacza, że ignorujemy predykcje z zakresu 0.4 - 0.6)
    const MIN_CONFIDENCE_THRESHOLD = 0.1; 
    
    // Jak bardzo przezroczysta ma być nakładka przy 100% pewności?
    // (0.5 = 50% przezroczystości)
    const MAX_OPACITY = 0.5; 
    
    // --- 2. INICJALIZACJA OPENSEADRAGON ---
    var viewer = OpenSeadragon({
        id: "openseadragon-viewer",
        prefixUrl: "https://cdnjs.cloudflare.com/ajax/libs/openseadragon/4.1.1/images/",
        tileSources: DZI_PATH
    });

    // --- 3. LOGIKA HEATMAPY ---
    async function drawHeatmap() {
        console.log("Skan otwarty. Ładuję heatmapę...");
        
        let heatmapData;
        try {
            const response = await fetch(HEATMAP_JSON_PATH);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            heatmapData = await response.json();
        } catch (e) {
            console.error("Nie udało się załadować pliku JSON z heatmapą:", e);
            return;
        }

        console.log(`Załadowano ${Object.keys(heatmapData).length} kafelków heatmapy. Rozpoczynam rysowanie...`);

        const entries = Object.entries(heatmapData);
        let i = 0;
        let drawnCount = 0; // Licznik narysowanych kafelków

        function processBatch() {
            for (let j = 0; j < BATCH_SIZE && i < entries.length; j++, i++) {
                const [tileKey, probability] = entries[i]; // probability = szansa na 'tumor'
                
                const parts = tileKey.split('_');
                const level = parseInt(parts[0]);
                const col = parseInt(parts[1]);
                const row = parseInt(parts[2]);

                if (level !== TARGET_LEVEL) continue;

                // --- NOWA LOGIKA KOLORÓW I PEWNOŚCI ---
                let r, g, b, opacity;

                if (probability > 0.5) {
                    // Predykcja: TUMOR (Czerwony)
                    r = 255; g = 0; b = 0;
                    // Skalujemy pewność (0.5 -> 1.0) na przezroczystość (0.0 -> MAX_OPACITY)
                    const confidence = (probability - 0.5) * 2;
                    opacity = confidence * MAX_OPACITY;
                } else {
                    // Predykcja: HEALTHY (Zielony)
                    r = 0; g = 255; b = 0;
                    // Skalujemy pewność (0.5 -> 0.0) na przezroczystość (0.0 -> MAX_OPACITY)
                    const confidence = (0.5 - probability) * 2;
                    opacity = confidence * MAX_OPACITY;
                }
                
                // --- OPTYMALIZACJA ---
                // Jeśli kafelek ma bardzo niską pewność (blisko 0.5),
                // nie rysujemy go w ogóle, aby oszczędzić wydajność.
                if (opacity < MIN_CONFIDENCE_THRESHOLD * MAX_OPACITY) {
                    continue; // Pomiń ten kafelek
                }
                // --- KONIEC OPTYMALIZACJI ---

                const rect = viewer.source.getTileBounds(level, col, row);
                const overlay = document.createElement("div");
                overlay.style.backgroundColor = `rgba(${r}, ${g}, ${b}, ${opacity})`;
                
                viewer.addOverlay({
                    element: overlay,
                    location: rect
                });
                drawnCount++;
            }

            // Zaplanuj następną paczkę
            if (i < entries.length) {
                setTimeout(processBatch, 0); 
            } else {
                console.log(`Heatmapa narysowana. Narysowano ${drawnCount} kafelków (z ${entries.length} dostępnych).`);
            }
        }
        processBatch(); // Rozpocznij
    }

    viewer.addHandler("open", drawHeatmap);
});