import os
import json
from functools import wraps
from flask import Flask, request, jsonify, render_template, render_template_string
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai

app = Flask(__name__)

# --- Configuração de CORS (requisições da extensão Chrome) ---
@app.after_request
def aplicar_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, DELETE'
    return response

# --- Autenticação Básica Opcional ---
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

# --- Inicialização do Firebase Firestore com Diagnóstico ---
db = None
firebase_erro = "Variavel FIREBASE_CONFIG_JSON ausente na Vercel"
firebase_json = os.environ.get('FIREBASE_CONFIG_JSON')

if firebase_json:
    try:
        cred_dict = json.loads(firebase_json)
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        firebase_erro = None
        print("Firebase inicializado com sucesso.")
    except Exception as e:
        firebase_erro = f"Erro na chave: {str(e)}"
        print(f"Erro ao inicializar Firebase: {e}")

# --- Configuração do Google Gemini ---
gemini_key = os.environ.get('GEMINI_API_KEY')
if gemini_key:
    try:
        genai.configure(api_key=gemini_key)
        print("Gemini AI configurado com sucesso.")
    except Exception as e:
        print(f"Erro ao configurar Gemini: {e}")

# --- Dashboard HTML no padrão Dark Theme da Extensão ---
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Start RH - Catho Hunter</title>
    <style>
        * { box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            background-color: #111827; 
            color: #f3f4f6; 
            margin: 0; 
            padding: 24px; 
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
            background-color: #1f2937; 
            border: 1px solid #374151; 
            padding: 28px; 
            border-radius: 10px; 
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5); 
        }
        .header { 
            display: flex; 
            align-items: center; 
            justify-content: space-between; 
            border-bottom: 1px solid #374151; 
            padding-bottom: 16px; 
            margin-bottom: 20px; 
        }
        h1 { 
            margin: 0; 
            color: #ec4899; 
            font-size: 22px; 
            font-weight: 700; 
            display: flex; 
            align-items: center; 
            gap: 8px; 
        }
        .subtitle { 
            font-size: 13px; 
            color: #9ca3af; 
            margin: 4px 0 0 0; 
        }
        .vaga-box { 
            background-color: #111827; 
            border: 1px solid #374151; 
            border-radius: 8px; 
            padding: 16px; 
            margin-bottom: 20px; 
        }
        .vaga-box label { 
            font-weight: 600; 
            font-size: 13px; 
            color: #f3f4f6; 
            display: block; 
            margin-bottom: 6px; 
        }
        .vaga-box textarea { 
            width: 100%; 
            height: 75px; 
            padding: 10px 12px; 
            border: 1px solid #374151; 
            border-radius: 6px; 
            background-color: #1f2937; 
            color: #f3f4f6; 
            font-family: inherit; 
            font-size: 13px; 
            outline: none; 
            transition: border-color 0.2s; 
        }
        .vaga-box textarea:focus { 
            border-color: #ec4899; 
        }
        .actions-bar { 
            display: flex; 
            gap: 12px; 
            margin-bottom: 16px; 
            flex-wrap: wrap; 
        }
        .btn { 
            border: none; 
            padding: 10px 18px; 
            border-radius: 6px; 
            cursor: pointer; 
            font-size: 13px; 
            font-weight: bold; 
            transition: background-color 0.2s, opacity 0.2s; 
            display: inline-flex; 
            align-items: center; 
            gap: 6px; 
        }
        .btn:hover { 
            opacity: 0.9; 
        }
        .btn-refresh { 
            background-color: #374151; 
            color: #f3f4f6; 
        }
        .btn-refresh:hover { 
            background-color: #4b5563; 
        }
        .btn-ai { 
            background-color: #ec4899; 
            color: #ffffff; 
        }
        .btn-ai:hover { 
            background-color: #db2777; 
        }
        .status-msg { 
            margin-bottom: 14px; 
            font-size: 13px; 
            font-weight: 500; 
        }
        .table-responsive { 
            overflow-x: auto; 
            border-radius: 6px; 
            border: 1px solid #374151; 
        }
        table { 
            width: 100%; 
            border-collapse: collapse; 
            background-color: #111827; 
        }
        th, td { 
            padding: 12px 16px; 
            border-bottom: 1px solid #374151; 
            text-align: left; 
            font-size: 13px; 
        }
        th { 
            background-color: #182234; 
            font-weight: 600; 
            color: #9ca3af; 
            text-transform: uppercase; 
            font-size: 11px; 
            letter-spacing: 0.05em; 
        }
        tr:last-child td { 
            border-bottom: none; 
        }
        tr:hover td { 
            background-color: #1a2233; 
        }
        .cand-nome { 
            font-weight: bold; 
            color: #f3f4f6; 
            font-size: 14px; 
        }
        .cand-cargo { 
            color: #9ca3af; 
            font-size: 12px; 
            margin-top: 2px; 
        }
        .cand-resumo { 
            color: #6b7280; 
            font-size: 11px; 
            margin-top: 4px; 
            line-height: 1.4; 
        }
        .badge { 
            display: inline-block; 
            padding: 3px 9px; 
            border-radius: 9999px; 
            font-size: 11px; 
            font-weight: 600; 
        }
        .badge-pendente { 
            background-color: rgba(245, 158, 11, 0.15); 
            color: #fbbf24; 
            border: 1px solid rgba(245, 158, 11, 0.3); 
        }
        .badge-aprovado { 
            background-color: rgba(16, 185, 129, 0.15); 
            color: #34d399; 
            border: 1px solid rgba(16, 185, 129, 0.3); 
        }
        .badge-reprovado { 
            background-color: rgba(239, 68, 68, 0.15); 
            color: #f87171; 
            border: 1px solid rgba(239, 68, 68, 0.3); 
        }
        .parecer-text { 
            color: #d1d5db; 
            font-size: 12px; 
            line-height: 1.4; 
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>Start RH • Catho Hunter</h1>
                <p class="subtitle">Triagem automatizada de candidatos com Google Gemini</p>
            </div>
        </div>

        <div class="vaga-box">
            <label for="requisitos">Critérios da Vaga (para avaliação da IA):</label>
            <textarea id="requisitos" placeholder="Ex: Técnico em Eletromecânica com sólida experiência em manutenção preventiva/corretiva, residir na região de Parauapebas, disponibilidade imediata..."></textarea>
        </div>

        <div class="actions-bar">
            <button class="btn btn-refresh" onclick="carregarCandidatos()">🔄 Atualizar Lista</button>
            <button class="btn btn-ai" id="btnIA" onclick="avaliarComIA()">✨ Avaliar Candidatos com IA</button>
        </div>

        <div id="statusProcessamento" class="status-msg"></div>

        <div class="table-responsive">
            <table>
                <thead>
                    <tr>
                        <th style="width: 25%;">Candidato</th>
                        <th style="width: 20%;">Localização</th>
                        <th style="width: 15%;">Status IA</th>
                        <th style="width: 40%;">Parecer da IA</th>
                    </tr>
                </thead>
                <tbody id="tabela-corpo">
                    <tr><td colspan="4" style="text-align:center; padding:24px; color:#9ca3af;">Carregando dados...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        async function carregarCandidatos() {
            const tbody = document.getElementById('tabela-corpo');
            try {
                const res = await fetch('/api/listar_candidatos');
                const data = await res.json();
                tbody.innerHTML = '';
                
                if (!data.contatos || data.contatos.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#9ca3af; padding:36px;">Nenhum candidato recebido. Abra a listagem da Catho e envie usando a extensão.</td></tr>';
                    return;
                }

                data.contatos.forEach(c => {
                    const tr = document.createElement('tr');
                    let badgeClass = 'badge-pendente';
                    if (c.status_ia === 'Aprovado') badgeClass = 'badge-aprovado';
                    if (c.status_ia === 'Reprovado') badgeClass = 'badge-reprovado';

                    tr.innerHTML = `
                        <td>
                            <div class="cand-nome">${c.nome || 'Não informado'}</div>
                            <div class="cand-cargo">${c.cargo || '-'}</div>
                            <div class="cand-resumo">${(c.resumo || '').substring(0, 110)}...</div>
                        </td>
                        <td style="color:#9ca3af;">${c.cidade || 'Brasil'}</td>
                        <td><span class="badge ${badgeClass}">${c.status_ia || 'Pendente'}</span></td>
                        <td><div class="parecer-text">${c.parecer_ia || 'Aguardando avaliação com IA...'}</div></td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (e) {
                tbody.innerHTML = '<tr><td colspan="4" style="color:#f87171; text-align:center; padding:20px;">Erro ao carregar candidatos da base de dados.</td></tr>';
            }
        }

        async function avaliarComIA() {
            const requisitos = document.getElementById('requisitos').value.trim();
            const statusEl = document.getElementById('statusProcessamento');
            const btn = document.getElementById('btnIA');

            if (!requisitos) {
                alert('Informe os critérios da vaga antes de executar a triagem.');
                return;
            }

            btn.disabled = true;
            statusEl.style.color = '#ec4899';
            statusEl.textContent = 'Avaliando perfis com o Google Gemini... aguarde alguns instantes.';

            try {
                const res = await fetch('/api/avaliar_ia', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ requisitos: requisitos })
                });
                const resultado = await res.json();
                if (res.ok) {
                    statusEl.style.color = '#34d399';
                    statusEl.textContent = resultado.message || 'Avaliação concluída!';
                    carregarCandidatos();
                } else {
                    throw new Error(resultado.message || 'Falha ao processar.');
                }
            } catch (err) {
                statusEl.style.color = '#f87171';
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

# --- Rota Principal (Dashboard) ---
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
        return jsonify({"status": "error", "message": f"Firebase nao conectado: {firebase_erro}"}), 500
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
        return jsonify({"status": "error", "message": f"Firebase nao conectado: {firebase_erro}"}), 500

    try:
        dados = request.get_json(force=True, silent=True)
        if not dados:
            return jsonify({"status": "error", "message": "Nenhum dado JSON recebido."}), 400

        if isinstance(dados, dict):
            candidatos = dados.get('candidatos', [])
        elif isinstance(dados, list):
            candidatos = dados
        else:
            return jsonify({"status": "error", "message": "Estrutura JSON incompativel."}), 400

        if not candidatos:
            return jsonify({"status": "error", "message": "A lista de candidatos enviada esta vazia."}), 400

        for c in candidatos:
            cand_id = str(c.get('id') or c.get('nome') or f"catho_{len(candidatos)}")
            db.collection('candidatos').document(cand_id).set(c, merge=True)

        return jsonify({
            "status": "success",
            "message": f"{len(candidatos)} candidatos salvos com sucesso no Firestore."
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Rota para Triagem de IA via Google Gemini ---
@app.route('/api/avaliar_ia', methods=['POST'])
def avaliar_ia():
    if not db:
        return jsonify({"status": "error", "message": f"Firebase nao conectado: {firebase_erro}"}), 500
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
            "parecer": "justificativa sucinta em ate 2 frases"
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
