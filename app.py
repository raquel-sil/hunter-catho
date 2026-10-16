import os
import json
from functools import wraps
from flask import Flask, request, jsonify, render_template, render_template_string
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai

app = Flask(__name__)

# --- CORS para permitir requisições da extensão Chrome ---
@app.after_request
def aplicar_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, DELETE'
    return response

# --- Autenticação Básica opcional (usada se APP_PASSWORD estiver configurada) ---
APP_USER = os.environ.get('APP_USER', 'admin')
APP_PASSWORD = os.environ.get('APP_PASSWORD', '')

def check_auth(username, password):
    return username == APP_USER and password == APP_PASSWORD

def authenticate():
    return jsonify({"message": "Autenticacao requerida"}), 401, {'WWW-Authenticate': 'Basic realm="Login Required"'}

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not APP_PASSWORD:
            return f(*args, **kwargs)
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

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
        print("Firebase inicializado com sucesso.")
    except Exception as e:
        print(f"Erro ao inicializar Firebase: {e}")

# --- Configuração do Google Gemini ---
gemini_key = os.environ.get('GEMINI_API_KEY')
if gemini_key:
    try:
        genai.configure(api_key=gemini_key)
        print("Gemini configurado com sucesso.")
    except Exception as e:
        print(f"Erro ao inicializar Gemini: {e}")

# --- Dashboard HTML Fallback (caso templates/index.html não exista) ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Catho Hunter - Start RH</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f4f6f8; margin: 0; padding: 24px; color: #1f2937; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 32px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); }
        h1 { margin-top: 0; color: #111827; font-size: 24px; display: flex; align-items: center; justify-content: space-between; }
        .vaga-box { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 20px 0; }
        .vaga-box textarea { width: 100%; height: 70px; padding: 10px; border: 1px solid #d1d5db; border-radius: 6px; font-family: inherit; font-size: 14px; margin-top: 8px; }
        .actions-bar { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
        .btn { border: none; padding: 10px 18px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 500; transition: opacity 0.2s; }
        .btn:hover { opacity: 0.9; }
        .btn-primary { background: #2563eb; color: white; }
        .btn-ai { background: #7c3aed; color: white; }
        .btn-refresh { background: #4b5563; color: white; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 14px 12px; border-bottom: 1px solid #e5e7eb; text-align: left; font-size: 14px; }
        th { background: #f9fafb; font-weight: 600; color: #4b5563; }
        .badge { display: inline-block; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: 600; }
        .badge-pendente { background: #fef3c7; color: #92400e; }
        .badge-aprovado { background: #d1fae5; color: #065f46; }
        .badge-reprovado { background: #fee2e2; color: #991b1b; }
        .status-msg { margin-top: 12px; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>
            Start RH • Catho Hunter
            <span style="font-size: 14px; font-weight: normal; color: #6b7280;">Triagem Inteligente</span>
        </h1>

        <div class="vaga-box">
            <label for="requisitos" style="font-weight: 600;">Requisitos da Vaga (para avaliacao da IA):</label>
            <textarea id="requisitos" placeholder="Ex: Experiencia minima de 2 anos em atendimento, superior completo, residir em SP..."></textarea>
        </div>

        <div class="actions-bar">
            <button class="btn btn-refresh" onclick="carregarCandidatos()">Atualizar Lista</button>
            <button class="btn btn-ai" id="btnIA" onclick="avaliarComIA()">Avaliar Candidatos com IA</button>
        </div>

        <div id="statusProcessamento" class="status-msg"></div>

        <table>
            <thead>
                <tr>
                    <th>Nome</th>
                    <th>Cargo / Resumo</th>
                    <th>Cidade</th>
                    <th>Status IA</th>
                    <th>Parecer IA</th>
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
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:#6b7280; padding:32px;">Nenhum candidato recebido. Abra a Catho e envie pela extensao.</td></tr>';
                    return;
                }
                data.contatos.forEach(c => {
                    const tr = document.createElement('tr');
                    let badgeClass = 'badge-pendente';
                    if (c.status_ia === 'Aprovado') badgeClass = 'badge-aprovado';
                    if (c.status_ia === 'Reprovado') badgeClass = 'badge-reprovado';

                    tr.innerHTML = `
                        <td><strong>${c.nome || '-'}</strong></td>
                        <td>
                            <div>${c.cargo || '-'}</div>
                            <small style="color: #6b7280;">${(c.resumo || '').substring(0, 100)}...</small>
                        </td>
                        <td>${c.cidade || '-'}</td>
                        <td><span class="badge ${badgeClass}">${c.status_ia || 'Pendente'}</span></td>
                        <td><small>${c.parecer_ia || '-'}</small></td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (e) {
                tbody.innerHTML = '<tr><td colspan="5" style="color:red;">Erro ao buscar candidatos.</td></tr>';
            }
        }

        async function avaliarComIA() {
            const requisitos = document.getElementById('requisitos').value.trim();
            const statusEl = document.getElementById('statusProcessamento');
            const btn = document.getElementById('btnIA');

            if (!requisitos) {
                alert('Preencha os requisitos da vaga antes de executar a avaliacao.');
                return;
            }

            btn.disabled = true;
            statusEl.style.color = '#7c3aed';
            statusEl.textContent = 'Processando triagem com Gemini IA... aguarde alguns segundos.';

            try {
                const res = await fetch('/api/avaliar_ia', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ requisitos: requisitos })
                });
                const resultado = await res.json();
                if (res.ok) {
                    statusEl.style.color = '#059669';
                    statusEl.textContent = resultado.message || 'Avaliacao concluida com sucesso!';
                    carregarCandidatos();
                } else {
                    throw new Error(resultado.message || 'Falha ao processar.');
                }
            } catch (err) {
                statusEl.style.color = '#dc2626';
                statusEl.textContent = 'Erro na triagem: ' + err.message;
            } finally {
                btn.disabled = false;
            }
        }

        window.onload = carregarCandidatos;
    </script>
</body>
</html>
"""

# --- Rota Principal (Painel Web) ---
@app.route('/')
@requires_auth
def index():
    if os.path.exists(os.path.join(app.root_path, 'templates', 'index.html')):
        return render_template('index.html')
    return render_template_string(DASHBOARD_HTML)

# --- Rota para Listagem de Candidatos ---
@app.route('/api/listar_candidatos', methods=['GET'])
def listar_candidatos():
    if not db:
        return jsonify({"status": "error", "message": "Firebase nao inicializado."}), 500
    try:
        docs = db.collection('candidatos').order_by('data_cadastro', direction=firestore.Query.DESCENDING).stream()
        candidatos = [doc.to_dict() for doc in docs]
        return jsonify({"status": "success", "contatos": candidatos}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Rota para Receber Candidatos da Extensão ---
@app.route('/api/receber_candidatos_extensao', methods=['POST', 'OPTIONS'])
def receber_candidatos_extensao():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    if not db:
        return jsonify({"status": "error", "message": "Firebase nao conectado."}), 500

    try:
        dados = request.get_json(force=True, silent=True)
        if not dados:
            return jsonify({"status": "error", "message": "Nenhum dado recebido."}), 400

        if isinstance(dados, dict):
            candidatos = dados.get('candidatos', [])
        elif isinstance(dados, list):
            candidatos = dados
        else:
            return jsonify({"status": "error", "message": "Formato de dados invalido."}), 400

        if not candidatos:
            return jsonify({"status": "error", "message": "Lista de candidatos vazia."}), 400

        for c in candidatos:
            cand_id = str(c.get('id') or c.get('nome') or f"catho_{len(candidatos)}")
            db.collection('candidatos').document(cand_id).set(c, merge=True)

        return jsonify({
            "status": "success",
            "message": f"{len(candidatos)} candidatos salvos com sucesso."
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Rota para Triagem com IA Gemini ---
@app.route('/api/avaliar_ia', methods=['POST'])
def avaliar_ia():
    if not db:
        return jsonify({"status": "error", "message": "Firebase nao inicializado."}), 500
    if not gemini_key:
        return jsonify({"status": "error", "message": "GEMINI_API_KEY nao configurada na Vercel."}), 500

    try:
        payload = request.get_json(force=True, silent=True) or {}
        requisitos = payload.get('requisitos', '')

        docs = db.collection('candidatos').where('status_ia', '==', 'Pendente').stream()
        candidatos_pendentes = [(doc.id, doc.to_dict()) for doc in docs]

        if not candidatos_pendentes:
            return jsonify({"status": "success", "message": "Nenhum candidato pendente para avaliacao."}), 200

        model = genai.GenerativeModel('gemini-1.5-flash')

        avaliados = 0
        for doc_id, cand in candidatos_pendentes:
            prompt = f"""
            Voce e um analista de Recrutamento e Selecao da Start RH.
            Avalie o perfil abaixo frente aos requisitos da vaga.

            REQUISITOS DA VAGA:
            {requisitos}

            CANDIDATO:
            Nome: {cand.get('nome', '')}
            Cargo: {cand.get('cargo', '')}
            Cidade: {cand.get('cidade', '')}
            Resumo: {cand.get('resumo', '')}

            Responda EXCLUSIVAMENTE em formato JSON com duas chaves:
            "status": "Aprovado" ou "Reprovado",
            "parecer": "justificativa em ate 2 frases curtas"
            """

            try:
                resposta = model.generate_content(prompt)
                texto = resposta.text.replace('```json', '').replace('```', '').strip()
                dados_ia = json.loads(texto)

                db.collection('candidatos').document(doc_id).update({
                    'status_ia': dados_ia.get('status', 'Avaliado'),
                    'parecer_ia': dados_ia.get('parecer', '')
                })
                avaliados += 1
            except Exception:
                continue

        return jsonify({
            "status": "success",
            "message": f"{avaliados} candidato(s) avaliado(s) pela IA com sucesso."
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
