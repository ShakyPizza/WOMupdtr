const { ipcRenderer } = require('electron');

async function fetchGroup() {
    const groupId = document.getElementById('groupId').value;
    if (!groupId) {
        alert('Please enter a group ID');
        return;
    }

    try {
        const result = await ipcRenderer.invoke('fetch-group', parseInt(groupId));
        if (result.error) {
            document.getElementById('result').innerHTML = `Error: ${result.error}`;
        } else {
            document.getElementById('result').innerHTML = `
                <h2>${result.name}</h2>
                <p><strong>Member Count:</strong> ${result.memberCount}</p>
                <p><strong>Created At:</strong> ${new Date(result.createdAt).toLocaleString()}</p>
                <p><strong>Last Updated:</strong> ${new Date(result.updatedAt).toLocaleString()}</p>
            `;
        }
    } catch (error) {
        document.getElementById('result').innerHTML = `Error: ${error.message}`;
    }
}

// Handle logs from main process
ipcRenderer.on('log', (event, message) => {
    const logDiv = document.getElementById('log');
    logDiv.innerHTML += message + '\n';
    logDiv.scrollTop = logDiv.scrollHeight;
}); 