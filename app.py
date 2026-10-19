import hmac
import os
import csv
import io
from flask import Flask, Response, render_template_string, request, jsonify
from dotenv import load_dotenv

load_dotenv()

APP_USER = os.getenv("APP_USER", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "admin")

app = Flask(__name__)

# Armazena temporariamente os candidatos recebidos da extensão
candidatos_capturados = []

def _pedir_login():
    return Response(
        "Acesso restrito.", 401, {"WWW-Authenticate": 'Basic realm="Start RH - Catho Hunter"'}
    )

@app.before_request
def exigir_login():
    # Liberta a verificação do navegador (OPTIONS) e o recebimento de dados sem pedir senha
    if request.method == "OPTIONS" or request.endpoint == "api_receber_candidatos_extensao":
        return
    if not APP_USER or not APP_PASSWORD:
        return Response("Servidor sem APP_USER/APP_PASSWORD configurados.", 503)
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
    <title>Start RH - Painel Catho Hunter</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen flex flex-col items-center p-6">
    <div class="max-w-5xl w-full bg-gray-800 rounded-xl shadow-2xl border border-gray-700 p-8 mt-6">
        
        <div class="flex items-center justify-between border-b border-gray-700 pb-6 mb-6">
            <div>
                <h1 class="text-2xl font-bold text-pink-500 flex items-center gap-2">
                    <i class="fa-solid fa-puzzle-piece"></i> Painel Catho Hunter
                </h1>
                <p class="text-sm text-gray-400 mt-1">Sincronização em tempo real de candidatos via Extensão do Navegador.</p>
            </div>
            
            <div class="flex gap-3">
                <button onclick="carregarCandidatos()" class="bg-gray-700 hover:bg-gray-600 text-white font-bold py-2 px-4 rounded-lg transition text-xs flex items-center gap-2 border border-gray-600">
                    <i class="fa-solid fa-rotate"></i> Atualizar Lista
                </button>
                <a href="/api/exportar_csv" class="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded-lg transition text-xs flex items-center gap-2 shadow-lg">
                    <i class="fa-solid fa-file-csv"></i> Exportar CSV
                </a>
            </div>
        </div>

        <div class="bg-gray-900/60 p-4 rounded-lg border border-gray-700 mb-6 text-xs text-gray-300">
            <p class="font-semibold text-pink-400 mb-1"><i class="fa-solid fa-info-circle"></i> Como utilizar:</p>
            <ol class="list-decimal list-inside space-y-1">
                <li>Abra o site da Catho Empresas no seu navegador logado.</li>
                <li>Faça a pesquisa de currículos que desejar.</li>
                <li>Clique no ícone da extensão <b>Start RH - Catho Hunter</b> e marque os perfis que lhe interessam.</li>
                <li>Clique em "Enviar Selecionados" e eles aparecerão na tabela abaixo.</li>
                <li>Por fim, clique em "Exportar CSV" para descarregar a lista.</li>
            </ol>
        </div>

        <div id="resultadoContainer" class="mt-4">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-lg font-semibold text-gray-200 flex items-center gap-2">
                    <i class="fa-solid fa-users text-pink-500"></i> Candidatos Sincronizados:
                </h2>
                <div class="flex items-center gap-4">
                    <span id="totalBadge" class="bg-pink-500/10 text-pink-400 text-xs px-3 py-1 rounded-full border border-pink-500/20 font-mono">0 Candidato(s)</span>
                    <button onclick="limparPainel()" class="text-red-400 hover:text-red-300 text-xs font-semibold flex items-center gap-1 transition">
                        <i class="fa-solid fa-trash"></i> Limpar Painel
                    </button>
                </div>
            </div>
            
            <div id="logList" class="space-y-3 font-sans text-sm">
                <p class="text-gray-500 text-center py-8">Nenhum candidato capturado ainda. Realize a captura pela extensão na página da Catho.</p>
            </div>
        </div>
    </div>

    <script>
        async function carregarCandidatos() {
            try {
                const response = await fetch('/api/listar_candidatos');
                const data = await response.json();
                const logList = document.getElementById('logList');
                const totalBadge = document.getElementById('totalBadge');

                if (data.status === 'success') {
                    totalBadge.innerText = `${data.contatos.length} Candidato(s)`;

                    if (data.contatos.length === 0) {
                        logList.innerHTML = `<p class="text-gray-500 text-center py-8">Nenhum candidato capturado ainda. Realize a captura pela extensão na página da Catho.</p>`;
                    } else {
                        let tableHtml = `
                            <div class="overflow-x-auto">
                                <table class="w-full text-left border-collapse border border-gray-700">
                                    <thead>
                                        <tr class="bg-gray-900 text-pink-400 border-b border-gray-700 text-xs uppercase font-mono">
                                            <th class="p-3">Nome</th>
                                            <th class="p-3">Cargo Visível</th>
                                            <th class="p-3 text-center">Ação</th>
                                        </tr>
                                    </thead>
                                    <tbody class="divide-y divide-gray-700 bg-gray-800/50">`;

                        data.contatos.forEach(c => {
                            tableHtml += `
                                <tr class="hover:bg-gray-800 transition">
                                    <td class="p-3 font-semibold text-gray-100">${c.nome}</td>
                                    <td class="p-3 text-gray-300">${c.cargo}</td>
                                    <td class="p-3 text-center">
                                        <a href="${c.link_cv}" target="_blank" class="inline-flex items-center gap-1 bg-pink-600/20 hover:bg-pink-600/40 text-pink-400 border border-pink-500/30 px-3 py-1 rounded-md text-xs transition">
                                            <i class="fa-solid fa-arrow-up-right-from-square"></i> Ver Perfil
                                        </a>
                                    </td>
                                </tr>`;
                        });

                        tableHtml += `</tbody></table></div>`;
                        logList.innerHTML = tableHtml;
                    }
                }
            } catch (err) {
                console.error('Erro ao atualizar lista:', err);
            }
        }

        async function limparPainel() {
            if(confirm("Tem a certeza que deseja limpar todos os candidatos do painel?")) {
                await fetch('/api/limpar_candidatos', { method: 'POST' });
                carregarCandidatos();
            }
        }

        setInterval(carregarCandidatos, 3000);
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
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return resp

    global candidatos_capturados
    data = request.json or {}
    novos = data.get("contatos", [])
    
    links_existentes = {c.get("link_cv") for c in candidatos_capturados}
    for c in novos:
        if c.get("link_cv") not in links_existentes:
            candidatos_capturados.append(c)
            links_existentes.add(c.get("link_cv"))

    resp = jsonify({"status": "success", "total": len(candidatos_capturados)})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/api/listar_candidatos", methods=["GET"])
def api_listar_candidatos():
    return jsonify({"status": "success", "contatos": candidatos_capturados})

@app.route("/api/limpar_candidatos", methods=["POST"])
def api_limpar_candidatos():
    global candidatos_capturados
    candidatos_capturados = []
    return jsonify({"status": "success", "message": "Painel limpo."})

@app.route("/api/exportar_csv", methods=["GET"])
def api_exportar_csv():
    global candidatos_capturados
    si = io.StringIO()
    
    # Adicionamos o BOM (Byte Order Mark) para que o Excel em Português leia os acentos corretamente
    si.write('\ufeff')
    
    # Usamos o separador de ponto e vírgula, que é o padrão no Excel para regiões de língua portuguesa
    cw = csv.writer(si, delimiter=';')
    cw.writerow(["Nome", "Cargo Visivel", "Resumo das Experiencias", "Competencias", "Link do Curriculo"])
    
    for c in candidatos_capturados:
        cw.writerow([
            c.get("nome", ""),
            c.get("cargo", ""),
            c.get("resumo", "Não especificado"),
            c.get("competencias", "Não especificadas"),
            c.get("link_cv", "")
        ])
        
    return Response(
        si.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=candidatos_catho.csv"}
    )

if __name__ == "__main__":
    porta = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=porta, debug=False)
