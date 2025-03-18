const { ipcRenderer } = require('electron');

function formatDate(dateString) {
    return new Date(dateString).toLocaleString();
}

function formatNumber(num) {
    return num.toLocaleString();
}

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
            // Display group info
            const groupInfo = `
                <div class="group-info">
                    <h2>${result.name}</h2>
                    <p><strong>Member Count:</strong> ${formatNumber(result.memberCount)}</p>
                    <p><strong>Created At:</strong> ${formatDate(result.createdAt)}</p>
                    <p><strong>Last Updated:</strong> ${formatDate(result.updatedAt)}</p>
                    <p><strong>Description:</strong> ${result.description || 'No description'}</p>
                    <p><strong>Clan Chat:</strong> ${result.clanChat || 'Not specified'}</p>
                    <p><strong>Homepage:</strong> ${result.homeworld ? `World ${result.homeworld}` : 'Not specified'}</p>
                </div>
            `;

            // Display member list
            const membersList = `
                <h3>Members (${result.members.length})</h3>
                <div class="members-list">
                    ${result.members.map(member => `
                        <div class="member-card">
                            <h3>${member.username}</h3>
                            <div class="member-stats">
                                <div class="stats-grid">
                                    <div class="stat-item">
                                        <div class="stat-label">Role</div>
                                        <div class="stat-value">${member.role || 'Member'}</div>
                                    </div>
                                    <div class="stat-item">
                                        <div class="stat-label">Experience</div>
                                        <div class="stat-value">${formatNumber(member.exp || 0)}</div>
                                    </div>
                                    <div class="stat-item">
                                        <div class="stat-label">Achievements</div>
                                        <div class="stat-value">${member.achievements ? formatNumber(member.achievements) : '0'}</div>
                                    </div>
                                    <div class="stat-item">
                                        <div class="stat-label">Combat Level</div>
                                        <div class="stat-value">${member.combatLevel || 'N/A'}</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;

            document.getElementById('result').innerHTML = groupInfo + membersList;
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