from flask import Flask, render_template, jsonify, request
import subprocess
app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/scan")
def scan():
     return render_template("scan.html")

@app.route('/api/generate_heatmap', methods=['POST'])
def generate_heatmap_api():

    data = request.get_json()
    heatmap_type = data.get('type')

    print(f"Otrzymano żądanie wygenerowania heatmapy typu: {heatmap_type}")

    try:
        if heatmap_type == 'resnet':

            result = subprocess.run(
                ['python', 'run_inference_resnet.py'], 
                capture_output=True, text=True, timeout=60, check=True
            )

            print("="*40)
            print(">>> LOGI Z PODPROCESU (run_inference_resnet.py) <<<")
            print(result.stdout)  # <--- To wypisze czas i liczbę kafelków!
            print("="*40)
            
            # Jeśli były jakieś błędy/ostrzeżenia, też je pokaż:
            if result.stderr:
                print(">>> BŁĘDY/OSTRZEŻENIA <<<")
                print(result.stderr)

            # Zwracamy ścieżkę do pliku, który ten skrypt właśnie stworzył
            return jsonify({
                "success": True, 
                "message": "Wygenerowano heatmapę ResNet.",
                "json_path": "/static/scans/breast_scan2_MODEL_heatmap.json"
            })
            
        elif heatmap_type == 'truth':
       
            result = subprocess.run(
                ['python', 'generate_truth_json.py'], 
                capture_output=True, text=True, timeout=60, check=True
            )

            print("="*40)
            print(">>> LOGI Z PODPROCESU (run_inference.py) <<<")
            print(result.stdout)  # <--- To wypisze czas i liczbę kafelków!
            print("="*40)
            
            # Jeśli były jakieś błędy/ostrzeżenia, też je pokaż:
            if result.stderr:
                print(">>> BŁĘDY/OSTRZEŻENIA <<<")
                print(result.stderr)


            return jsonify({
                "success": True, 
                "message": "Wygenerowano heatmapę Eksperta.",
                "json_path": "/static/scans/breast_scan2_TRUTH_heatmap.json"
            })
        
        elif heatmap_type == 'mobilenet':
            print("Uruchamiam skrypt MobileNet...")
 
            result = subprocess.run(
                ['python', 'run_inference_mobilenet.py'], 
                capture_output=True, text=True, timeout=300, check=True 
            )

            print("="*40)
            print(">>> LOGI Z PODPROCESU (run_inference_resnet.py) <<<")
            print(result.stdout)  # <--- To wypisze czas i liczbę kafelków!
            print("="*40)
            
            # Jeśli były jakieś błędy/ostrzeżenia, też je pokaż:
            if result.stderr:
                print(">>> BŁĘDY/OSTRZEŻENIA <<<")
                print(result.stderr)

                
            return jsonify({
                "success": True, 
                "message": "Wygenerowano heatmapę MobileNet.",
        
                "json_path": "/static/scans/breast_scan2_MODEL_MOBILENET_heatmap.json"
            })
        
        else:
            return jsonify({"success": False, "message": "Nieznany typ"}), 400

    except subprocess.TimeoutExpired:
        print("BŁĄD: Generowanie trwało zbyt długo (timeout)")
        return jsonify({"success": False, "message": "Błąd: Generowanie trwało zbyt długo (timeout)"}), 500
    except subprocess.CalledProcessError as e:
        print(f"BŁĄD: Skrypt Pythona zwrócił błąd: {e.stderr}")
        return jsonify({"success": False, "message": f"Błąd serwera: {e.stderr}"}), 500
    except Exception as e:
        print(f"BŁĄD: {e}")
        return jsonify({"success": False, "message": f"Błąd: {e}"}), 500
    
if __name__ == "__main__":
    app.run(debug=True)