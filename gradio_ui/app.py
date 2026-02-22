"""
Interfaccia Gradio per testare rapidamente l'inferenza del servizio CV.

Permette di caricare un'immagine (da file o webcam) e inviarla all'endpoint
POST /inference del servizio CV configurato tramite la variabile d'ambiente
SERVICE_URL. Mostra il risultato, la confidence e la latenza.

In Gradio 5+, il componente gr.Image con type="filepath" mostra automaticamente
sia il pulsante upload che l'icona webcam nell'interfaccia.
"""

import gradio as gr
import requests
import os

# URL del servizio CV a cui inviare le immagini.
# In Docker Compose si usa il nome del servizio come hostname.
SERVICE_URL = os.environ.get("SERVICE_URL", "http://trashnet_service_default:8000")


def classify_image(image_path):
    """
    Invia l'immagine al servizio CV e restituisce il risultato formattato.

    Legge il file dal path locale, lo manda come multipart/form-data
    all'endpoint /inference del servizio target e formatta la risposta.
    """
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


# Interfaccia Gradio con tema Glass
with gr.Blocks(theme=gr.themes.Glass()) as demo:
    gr.Markdown("# <center>TrashNet Explorer (Dockerized Gradio)</center>")
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
