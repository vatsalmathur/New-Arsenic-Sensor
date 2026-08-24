const BACKEND_API_URL = window.location.protocol === 'file:' || window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:8000/api/chat' 
    : '/api/chat';

function toggleChat() {
    const chatWindow = document.getElementById('chat-window');
    chatWindow.classList.toggle('open');
}

function handleChatKeyPress(event) {
    if (event.key === 'Enter') {
        sendChatMessage();
    }
}

async function sendChatMessage() {
    const inputElement = document.getElementById('chat-input-field');
    const messageText = inputElement.value.trim();
    
    if (!messageText) return;
    
    inputElement.value = '';
    addMsgToUI(messageText, 'user-msg');
    
    const loadingId = showLoading();
    
    try {
        const response = await fetch(BACKEND_API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: messageText })
        });
        
        if (!response.ok) {
            let errorMsg = 'API Error';
            try {
                const errData = await response.json();
                errorMsg = errData.detail || errorMsg;
            } catch (e) {}
            throw new Error(errorMsg);
        }
        
        const data = await response.json();
        removeElement(loadingId);
        addMsgToUI(data.reply, 'bot-msg');
        
    } catch (error) {
        console.error('Chat API Error:', error);
        removeElement(loadingId);
        addMsgToUI("Connection to AI brain failed: " + error.message, 'bot-msg');
    }
}

function addMsgToUI(text, typeClass) {
    const container = document.getElementById('chat-messages-container');
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${typeClass}`;
    msgDiv.innerHTML = text.replace(/\n/g, '<br>');
    container.appendChild(msgDiv);
    container.scrollTop = container.scrollHeight;
}

function showLoading() {
    const container = document.getElementById('chat-messages-container');
    const loadingDiv = document.createElement('div');
    const id = 'chat-loading-' + Date.now();
    loadingDiv.id = id;
    loadingDiv.className = 'chat-loading';
    loadingDiv.textContent = 'Agent is thinking...';
    container.appendChild(loadingDiv);
    container.scrollTop = container.scrollHeight;
    return id;
}

function removeElement(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}
