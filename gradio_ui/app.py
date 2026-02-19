import gradio as gr
import requests
import os

# Il servizio target a cui Gradio invierà le immagini
SERVICE_URL = os.environ.get("SERVICE_URL", "http://trashnet_service_default:8000")

def classify_image(image_path):
    if image_path is None:
        return "Nessuna immagine fornita"
        
    try:
        with open(image_path, "rb") as f:
            files = {"file": f}
            response = requests.post(f"{SERVICE_URL}/inference", files=files)
            
        if response.status_code == 200:
            data = response.json()
            return f"PREDIZIONE: {data.get('result', 'Sconosciuto').upper()}\nConfidenza: {data.get('confidence', 0.0):.4f}\nLatenza: {data.get('latency_ms', 0)} ms"
        else:
            return f"Errore dal server: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Errore di connessione: {str(e)}\nSei sicuro che {SERVICE_URL} sia online?"

with gr.Blocks(theme=gr.themes.Glass()) as demo:
    gr.Markdown("# <center>♻️ TrashNet Explorer (Dockerized Gradio)</center>")
    gr.Markdown("<center>Seleziona un'immagine e clicca Analizza per inviarla al servizio CV isolato.</center>")
    
    with gr.Row():
        with gr.Column(scale=2):
            img_input = gr.Image(type="filepath", label="Immagine in input")
        with gr.Column(scale=1):
            output_text = gr.Textbox(label="Status e Risultati", lines=4)
            submit_btn = gr.Button("Analizza Rifiuto", variant="primary")
            
    submit_btn.click(fn=classify_image, inputs=img_input, outputs=output_text)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
