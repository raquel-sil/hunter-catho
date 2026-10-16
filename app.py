import os
import json
from flask import Flask, request, jsonify, render_template_string
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai

app = Flask(__name__)

# --- Configuração de CORS para permitir requisições da extensão Chrome ---
@app.after_request
def aplicar_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

# --- Inicialização do Firebase Firestore ---
db = None
firebase_json = os.environ.get('FIREBASE_CONFIG_JSON')

if firebase_json:
    try:
        cred_dict = json.loads(firebase_json)
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase Firestore inicializado com sucesso.")
    except Exception as e:
        print(f"Erro ao inicializar Firebase: {e}")
else:
    print("AVISO: Variável FIREBASE_CONFIG_JSON não encontrada.")

# --- Configuração do Google Gemini ---
gemini_key = os.environ.get('GEMINI_API_KEY')
if gemini_key:
    try:
        genai.configure(api_key=gemini_key)
        print("Gemini AI configurado.")
    except Exception as e:
        print(f"Erro ao configurar Gemini: {e}")

# --- Rota Principal (Painel Web) ---
@app.route('/')
def dashboard():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <title>Catho Hunter - Painel</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f3f4f6; margin: 0; padding: 20px; }
            .container { max-width: 1000px; margin: 0 auto; background: white; padding: 24px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
            h1 { margin-top: 0; color: #111827; }
            table { width: 100%; border-collapse: collapse; margin-top: 16px; }
            th, td { padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: left; }
            th { background: #f9fafb; font-weight: 600; color: #374151; }
            .btn { background: #2563eb; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-size: 14px; }
            .btn:hover { background: #1d4ed8; }
            .badge { display: inline-block; padding: 2px 8px; border-radius: 9999px; font-size: 12px; font-weight: 500; background: #e5e7eb; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Start RH - Painel de Candidatos Catho</h1>
            <button class="btn" onclick="carregarCandidatos()">Atualizar Lista</button>
            <table>
                <thead>
                    <tr>
                        <th>Nome</th>
                        <th>Cargo</th>
                        <th>Local</th>
                        <th>Status IA</th>
                        <th>Data</th>
                    </tr>
                </thead>
                <tbody id="tabela-corpo">
                    <tr><td colspan="5">Carregando candidatos...</td></tr>
                </tbody>
            </table>
        </div>
        <script>
            async function carregarCandidatos() {
                const tbody = document.getElementById('tabela-corpo');
                try {
                    const res = await fetch('/api/listar_candidatos');
                    const data = await res.json();
                    tbody.innerHTML = '';
                    if (!data.contatos || data.contatos.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5">Nenhum candidato cadastrado ainda. Use a extensão para enviar.</td></tr>';
                        return;
                    }
                    data.contatos.forEach(c => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td><strong>${c.nome || '-'}</strong></td>
                            <td>${c.cargo || '-'}</td>
                            <td>${c.cidade || '-'}</td>
                            <td><span class="badge">${c.status_ia || 'Pendente'}</span></td>
                            <td>${c.data_cadastro ? new Date(c.data_cadastro).toLocaleDateString('pt-BR') : '-'}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                } catch (e) {
                    tbody.innerHTML = '<tr><td colspan="5" style="color:red;">Erro ao buscar candidatos.</td></tr>';
                }
            }
            window.onload = carregarCandidatos;
        </script>
    </body>
    </html>
    """)

# --- Rota de Listagem de Candidatos ---
@app.route('/api/listar_candidatos', methods=['GET'])
def listar_candidatos():
    if not db:
        return jsonify({"status": "error", "message": "Firebase não inicializado."}), 500
    try:
        docs = db.collection('candidatos').order_by('data_cadastro', direction=firestore.Query.DESCENDING).stream()
        candidatos = [doc.to_dict() for doc in docs]
        return jsonify({"status": "success", "contatos": candidatos}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Rota para Receber Candidatos da Extensão ---
@app.route('/api/receber_candidatos_extensao', methods=['POST', 'OPTIONS'])
def receber_candidatos_extensao():
    # Resposta rápida para requisições de teste CORS (preflight)
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    if not db:
        return jsonify({"status": "error", "message": "Firebase não inicializado no servidor."}), 500

    try:
        dados = request.get_json(force=True, silent=True)
        if not dados:
            return jsonify({"status": "error", "message": "Nenhum dado JSON recebido."}), 400

        # Aceita formato { "candidatos": [...] } ou lista pura [...]
        if isinstance(dados, dict):
            candidatos = dados.get('candidatos', [])
        elif isinstance(dados, list):
            candidatos = dados
        else:
            return jsonify({"status": "error", "message": "Estrutura JSON inválida."}), 400

        if not candidatos:
            return jsonify({"status": "error", "message": "A lista de candidatos está vazia."}), 400

        # Grava cada candidato no Cloud Firestore
        for c in candidatos:
            cand_id = str(c.get('id') or f"catho_{hash(c.get('nome', ''))}")
            db.collection('candidatos').document(cand_id).set(c, merge=True)

        return jsonify({
            "status": "success",
            "message": f"{len(candidatos)} candidatos salvos com sucesso no Firestore."
        }), 200

    except Exception as e:
        print(f"Erro no processamento da rota: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
