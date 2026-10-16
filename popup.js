let candidatosDetectados = [];
const status = document.getElementById('status');
const listaContainer = document.getElementById('listaContainer');
const candidatosLista = document.getElementById('candidatosLista');
const btnLerTela = document.getElementById('btnLerTela');
const btnEnviar = document.getElementById('btnEnviarSelecionados');

btnLerTela.addEventListener('click', async () => {
    status.innerText = "A ler candidatos da tela...";
    candidatosLista.innerHTML = "";
    listaContainer.style.display = "none";

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab || !tab.url.includes("catho.com.br")) {
        status.innerText = "Erro: Abra a página de busca da Catho primeiro.";
        return;
    }

    chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: extrairCandidatosDaPagina
    }, (results) => {
        if (results && results[0] && results[0].result && results[0].result.length > 0) {
            candidatosDetectados = results[0].result;
            status.innerText = `${candidatosDetectados.length} candidato(s) encontrados.`;
            renderizarLista(candidatosDetectados);
            listaContainer.style.display = "flex";
        } else {
            status.innerText = "Nenhum candidato encontrado nesta página.";
        }
    });
});

function renderizarLista(itens) {
    candidatosLista.innerHTML = "";
    itens.forEach((c, index) => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'candidato-item';
        itemDiv.innerHTML = `
            <input type="checkbox" id="cand_${index}" data-index="${index}">
            <label for="cand_${index}" class="candidato-info" style="cursor: pointer;">
                <span class="candidato-nome">${c.nome}</span>
                <span class="candidato-cargo">${c.cargo}</span>
            </label>
        `;
        candidatosLista.appendChild(itemDiv);
    });
}

document.getElementById('btnMarcarTodos').addEventListener('click', () => {
    document.querySelectorAll('#candidatosLista input[type="checkbox"]').forEach(cb => cb.checked = true);
});
document.getElementById('btnDesmarcarTodos').addEventListener('click', () => {
    document.querySelectorAll('#candidatosLista input[type="checkbox"]').forEach(cb => cb.checked = false);
});

btnEnviar.addEventListener('click', async () => {
    const checkboxes = document.querySelectorAll('#candidatosLista input[type="checkbox"]:checked');
    const selecionados = Array.from(checkboxes).map(cb => candidatosDetectados[parseInt(cb.getAttribute('data-index'), 10)]);

    if (selecionados.length === 0) {
        status.innerText = "Selecione pelo menos 1 candidato antes de enviar.";
        return;
    }

    status.innerText = `Enviando ${selecionados.length} ao servidor...`;
    const API_URL = 'https://catho-extension.onrender.com/api/receber_candidatos_extensao';

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contatos: selecionados })
        });
        if (response.ok) {
            status.innerText = `Sucesso! ${selecionados.length} candidatos enviados ao painel.`;
        } else {
            status.innerText = `Falha ao enviar (Erro ${response.status}).`;
        }
    } catch (e) {
        status.innerText = "Servidor inacessível no Render.";
    }
});

function extrairCandidatosDaPagina() {
    const lista = [];
    const cards = document.querySelectorAll('article, [class*="ResumeCard"], [class*="curriculo"], [class*="Card"]');

    cards.forEach(card => {
        const nomeEl = card.querySelector('h2, h3, [class*="name"], [class*="nome"]');
        if (!nomeEl || !nomeEl.innerText.trim()) return;
        const nome = nomeEl.innerText.trim();
        const linkEl = card.querySelector('a[href*="curriculo"]') || card.querySelector('a');
        const link_cv = linkEl ? linkEl.href : window.location.href;

        const todasLinhas = card.innerText.split('\n').map(l => l.trim()).filter(l => l.length > 0);
        const termosIgnorar = ['visualizar currículo', 'ver currículo', 'salvar', 'descartar', 'compartilhar', 'adicionar à vaga', 'mensagem', 'whatsapp', 'ver telefone', 'ações', 'imprimir', 'ver mais'];
        const linhasUteis = todasLinhas.filter(l => {
            const lMin = l.toLowerCase();
            if (l === nome) return false;
            return !termosIgnorar.some(termo => lMin === termo || lMin.startsWith('ver mais'));
        });

        let cargo = 'Não informado';
        const cargoEl = card.querySelector('h3, h4');
        if (cargoEl && cargoEl !== nomeEl && cargoEl.innerText.trim().length > 0) {
            cargo = cargoEl.innerText.trim();
        } else {
            const possivelCargo = linhasUteis.find(l => !l.toLowerCase().includes('anos') && !l.toLowerCase().includes('rio de janeiro') && !l.toLowerCase().includes('são paulo') && l.length < 70);
            if (possivelCargo) cargo = possivelCargo;
        }

        const tagEls = Array.from(card.querySelectorAll('[class*="tag"], [class*="chip"], [class*="badge"], [data-testid*="skill"]'))
            .map(t => t.innerText.trim())
            .filter(t => t.length > 0 && t.length < 40 && !termosIgnorar.includes(t.toLowerCase()));
        const competencias = tagEls.length > 0 ? [...new Set(tagEls)].join(', ') : 'Incluído no resumo';
        const resumo = linhasUteis.length > 0 ? linhasUteis.join(' | ') : 'Sem detalhes adicionais no cartão.';

        lista.push({ nome, cargo, resumo, competencias, link_cv });
    });
    return lista;
}