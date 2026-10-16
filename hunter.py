import hmac
import os
import csv
import io
import json
import hashlib
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai
from flask import Flask, Response, render_template_string, request, jsonify
from dotenv import load_dotenv

load_dotenv()

APP_USER = os.getenv("APP_USER", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "admin")
FIREBASE_CONFIG_JSON = os.getenv("FIREBASE_CONFIG_JSON", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

app = Flask(__name__)

# Configuração do Google Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Configuração do Firebase Cloud Firestore
db = None
if FIREBASE_CONFIG_JSON:
    try:
        cred_dict = json.loads(FIREBASE_CONFIG_JSON)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        print("Firebase Firestore conectado com sucesso!")
    except Exception as e:
        print("Erro na conexão com Firebase:", e)

def _pedir_login():
    return Response(
        "Acesso restrito.", 401, {"WWW-Authenticate": 'Basic realm="Start RH - Catho Hunter"'}
    )

@app.before_request
def exigir_login():
    if request.method == "OPTIONS" or request.endpoint in ["api_receber_candidatos_extensao", "api_listar_candidatos"]:
        return
    if not APP_USER or not APP_PASSWORD:
        return Response("Servidor sem credenciais configuradas.", 503)
    auth = request.authorization
    if not auth:
        return _pedir_login()
    user_ok = hmac.compare_digest(auth.username or "", APP_USER)
    pass_ok = hmac.compare_digest(auth.password or "", APP_PASSWORD)
    if not (user_ok and pass_ok):
        return _pedir_login()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Start RH - Triagem com IA</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen flex flex-col items-center p-6">
    <div class="max-w-7xl w-full bg-gray-800 rounded-xl shadow-2xl border border-gray-700 p-8 mt-4">
        
        <div class="flex items-center justify-between border-b border-gray-700 pb-6 mb-6">
            <div>
                <h1 class="text-2xl font-bold text-pink-500 flex items-center gap-2">
                    <i class="fa-solid fa-brain"></i> Triagem Inteligente de Candidatos
                </h1>
                <p class="text-sm text-gray-400 mt-1">Armazenamento em Firestore e processamento automatizado com IA.</p>
            </div>
            
            <div class="flex gap-3">
                <button onclick="carregarCandidatos()" class="bg-gray-700 hover:bg-gray-600 text-white font-bold py-2 px-3 rounded-lg transition text-xs flex items-center gap-2 border border-gray-600">
                    <i class="fa-solid fa-rotate"></i> Atualizar Tabela
                </button>
                <a href="/api/exportar_csv?apenas_aprovados=1" class="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-3 rounded-lg transition text-xs flex items-center gap-2 shadow-lg">
                    <i class="fa-solid fa-file-csv"></i> Exportar Aprovados
                </a>
                <a href="/api/exportar_csv" class="bg-gray-700 hover:bg-gray-600 text-gray-200 font-bold py-2 px-3 rounded-lg transition text-xs flex items-center gap-2 border border-gray-600">
                    <i class="fa-solid fa-download"></i> Exportar Todos
                </a>
            </div>
        </div>

        <div class="bg-gray-900/80 p-5 rounded-lg border border-pink-500/30 mb-6">
            <h3 class="text-sm font-semibold text-pink-400 flex items-center gap-2 mb-2">
                <i class="fa-solid fa-file-lines"></i> Job Description / Critérios da Vaga
            </h3>
            <textarea id="requisitosVaga" rows="3" class="w-full bg-gray-800 border border-gray-700 rounded-lg p-3 text-sm text-gray-200 focus:outline-none focus:border-pink-500 font-sans" placeholder="Cole aqui os requisitos essenciais da vaga (formação, experiência, conhecimentos técnicos, localidade)..."></textarea>
            
            <div class="flex justify-between items-center mt-3">
                <span class="text-xs text-gray-400">A IA compara o histórico dos candidatos com este Job Description e emite o veredito.</span>
                <button id="btnFiltrarIA" onclick="filtrarComIA()" class="bg-pink-600 hover:bg-pink-700 text-white font-bold py-2 px-5 rounded-lg transition text-xs shadow-md flex items-center gap-2">
                    <i class="fa-solid fa-wand-magic-sparkles"></i> Avaliar Candidatos com IA
                </button>
            </div>
        </div>

        <div id="resultadoContainer" class="mt-4">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-lg font-semibold text-gray-200">
                    <i class="fa-solid fa-users text-pink-500"></i> Banco de Talentos Sincronizado:
                </h2>
                <button onclick="limparPainel()" class="text-red-400 hover:text-red-300 text-xs font-semibold flex items-center gap-1 transition">
                    <i class="fa-solid fa-trash"></i> Esvaziar Base de Dados
                </button>
            </div>
            
            <div id="logList">
                <p class="text-gray-500 text-center py-8">Carregando candidatos...</p>
            </div>
        </div>
    </div>

    <script>
        async function carregarCandidatos() {
            try {
                const response = await fetch('/api/listar_candidatos');
                const data = await response.json();
                const logList = document.getElementById('logList');

                if (data.status === 'success') {
                    if (data.contatos.length === 0) {
                        logList.innerHTML = `<p class="text-gray-500 text-center py-8">Nenhum candidato capturado ainda. Capture perfis pela extensão no Chrome.</p>`;
                    } else {
                        let tableHtml = `
                            <div class="overflow-x-auto">
                                <table class="w-full text-left border-collapse border border-gray-700">
                                    <thead>
                                        <tr class="bg-gray-900 text-pink-400 border-b border-gray-700 text-xs uppercase font-mono">
                                            <th class="p-3">Candidato</th>
                                            <th class="p-3 text-center">Status IA</th>
                                            <th class="p-3 text-center">Score</th>
                                            <th class="p-3">Parecer Técnico</th>
                                            <th class="p-3 text-center">Ação</th>
                                        </tr>
                                    </thead>
                                    <tbody class="divide-y divide-gray-700 bg-gray-800/50">`;

                        data.contatos.forEach(c => {
                            let statusIA = c.status_ia || 'Pendente';
                            let corStatus = statusIA === 'Aprovado' ? 'text-green-400 bg-green-500/20' : 
                                            statusIA === 'Reprovado' ? 'text-red-400 bg-red-500/20' : 'text-gray-400 bg-gray-500/20';

                            tableHtml += `
                                <tr class="hover:bg-gray-800 transition text-xs">
                                    <td class="p-3 font-semibold text-gray-100">${c.nome}</td>
                                    <td class="p-3 text-center">
                                        <span class="px-2 py-1 rounded font-bold border border-current ${corStatus}">${statusIA}</span>
                                    </td>
                                    <td class="p-3 text-center font-mono font-bold text-pink-400 text-sm">${c.score_ia !== null ? c.score_ia + '%' : '-'}</td>
                                    <td class="p-3 text-gray-300 max-w-sm text-xs leading-relaxed" title="${c.resumo}">${c.justificativa_ia || 'Aguardando avaliação com o JD...'}</td>
                                    <td class="p-3 text-center">
                                        <a href="${c.link_cv}" target="_blank" class="inline-flex items-center gap-1 bg-pink-600/20 hover:bg-pink-600/40 text-pink-400 border border-pink-500/30 px-3 py-1.5 rounded-md text-xs transition font-semibold whitespace-nowrap">
                                            <i class="fa-solid fa-arrow-up-right-from-square"></i> Ver na Catho
                                        </a>
                                    </td>
                                </tr>`;
                        });
                        tableHtml += `</tbody></table></div>`;
                        logList.innerHTML = tableHtml;
                    }
                }
            } catch (err) {
                console.error('Erro ao listar candidatos:', err);
            }
        }

        async function filtrarComIA() {
            const requisitos = document.getElementById('requisitosVaga').value.trim();
            if (!requisitos) {
                alert("Insira os critérios ou Job Description antes de acionar a IA.");
                return;
            }
            const btn = document.getElementById('btnFiltrarIA');
            btn.disabled = true;
            btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Avaliando currículos...`;

            try {
                const response = await fetch('/api/filtrar_ia', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ requisitos: requisitos })
                });
                const resData = await response.json();
                if (resData.status === 'success') {
                    await carregarCandidatos();
                } else {
                    alert('Falha na triagem: ' + (resData.message || 'Erro desconhecido.'));
                }
            } catch (e) {
                alert('Erro na comunicação com o servidor.');
            } finally {
                btn.disabled = false;
                btn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Avaliar Candidatos com IA`;
            }
        }

        async function limparPainel() {
            if(confirm("Confirma a exclusão de todos os registros do Firestore?")) {
                await fetch('/api/limpar_candidatos', { method: 'POST' });
                carregarCandidatos();
            }
        }

        carregarCandidatos();
    </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route("/api/receber_candidatos_extensao", methods=["POST", "OPTIONS"])
def api_receber_candidatos_extensao():
    if request.method == "OPTIONS":
        resp = jsonify({"status": "ok"})
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    if not db:
        return jsonify({"status": "error", "message": "Firebase não inicializado."}), 500

    data = request.json or {}
    novos = data.get("contatos", [])
    
    for c in novos:
        c_id = hashlib.md5(c.get("link_cv", "").encode()).hexdigest()
        doc_ref = db.collection("candidatos").document(c_id)
        if not doc_ref.get().exists:
            doc_ref.set({
                "id": c_id,
                "nome": c.get("nome", ""),
                "cargo": c.get("cargo", ""),
                "resumo": c.get("resumo", ""),
                "competencias": c.get("competencias", ""),
                "link_cv": c.get("link_cv", ""),
                "score_ia": None,
                "justificativa_ia": "",
                "status_ia": "Pendente"
            })

    resp = jsonify({"status": "success"})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/api/listar_candidatos", methods=["GET"])
def api_listar_candidatos():
    if not db:
        return jsonify({"status": "success", "contatos": []})
    
    docs = db.collection("candidatos").stream()
    candidatos = [doc.to_dict() for doc in docs]
    candidatos.sort(key=lambda x: (1 if x.get("status_ia") == "Aprovado" else 0, x.get("score_ia") or 0), reverse=True)
    return jsonify({"status": "success", "contatos": candidatos})

@app.route("/api/filtrar_ia", methods=["POST"])
def api_filtrar_ia():
    if not db:
        return jsonify({"status": "error", "message": "Banco de dados não configurado."}), 500
    if not GEMINI_API_KEY:
        return jsonify({"status": "error", "message": "Chave GEMINI_API_KEY não configurada no Render."}), 500

    requisitos = (request.json or {}).get("requisitos", "")
    docs = list(db.collection("candidatos").where("status_ia", "==", "Pendente").stream())
    if not docs:
        return jsonify({"status": "error", "message": "Não há candidatos com status Pendente para avaliar."})

    candidatos_prompt = [
        {
            "id": doc.id,
            "nome": doc.to_dict().get("nome", ""),
            "cargo": doc.to_dict().get("cargo", ""),
            "resumo": doc.to_dict().get("resumo", "")
        }
        for doc in docs
    ]

    prompt = f"""Atue como Recrutador Técnico de RH especializado.
Avalie cada um dos candidatos abaixo em relação a este JOB DESCRIPTION:
\"\"\"{requisitos}\"\"\"

CANDIDATOS:
{json.dumps(candidatos_prompt, ensure_ascii=False)}

Gere uma lista de avaliações em formato JSON estruturado com os seguintes campos por candidato:
- "id": string id correspondente
- "aprovado": true se preenche os requisitos fundamentais, false caso contrário
- "score": número inteiro de 0 a 100 indicando a aderência
- "justificativa": frase curta (máximo 25 palavras) resumindo o motivo do score
"""

    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={"response_mime_type": "application/json"}
        )
        
        response = model.generate_content(prompt)
        conteudo = response.text.strip()
        avaliacoes = json.loads(conteudo)

        for aval in avaliacoes:
            status = "Aprovado" if aval.get("aprovado") else "Reprovado"
            db.collection("candidatos").document(aval["id"]).update({
                "status_ia": status,
                "score_ia": aval.get("score", 0),
                "justificativa_ia": aval.get("justificativa", "")
            })

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/limpar_candidatos", methods=["POST"])
def api_limpar_candidatos():
    if db:
        docs = db.collection("candidatos").stream()
        for doc in docs:
            db.collection("candidatos").document(doc.id).delete()
    return jsonify({"status": "success"})

@app.route("/api/exportar_csv", methods=["GET"])
def api_exportar_csv():
    if not db:
        return Response("Banco de dados indisponível.", 500)
    
    apenas_aprovados = request.args.get("apenas_aprovados") == "1"
    
    if apenas_aprovados:
        docs = db.collection("candidatos").where("status_ia", "==", "Aprovado").stream()
        nome_ficheiro = "candidatos_aprovados.csv"
    else:
        docs = db.collection("candidatos").stream()
        nome_ficheiro = "todos_candidatos.csv"
    
    si = io.StringIO()
    si.write('\ufeff')
    cw = csv.writer(si, delimiter=';')
    cw.writerow(["Nome", "Veredito IA", "Score IA", "Justificativa da IA", "Resumo", "Link do Curriculo"])
    
    for doc in docs:
        c = doc.to_dict()
        cw.writerow([
            c.get("nome", ""),
            c.get("status_ia", "Pendente"),
            f"{c.get('score_ia')}%" if c.get("score_ia") is not None else "-",
            c.get("justificativa_ia", ""),
            c.get("resumo", ""),
            c.get("link_cv", "")
        ])
        
    return Response(
        si.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={nome_ficheiro}"}
    )

if __name__ == "__main__":
    porta = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=porta, debug=False)