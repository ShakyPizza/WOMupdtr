const { ipcRenderer } = require('electron');

function formatDate(dateString) {
    return new Date(dateString).toLocaleString();
}

function formatNumber(num) {
    return num.toLocaleString();
}

function switchTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.tab-button').forEach(button => {
        button.classList.remove('active');
    });
    document.querySelector(`.tab-button[onclick="switchTab('${tabName}')"]`).classList.add('active');

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');

    // If switching to members tab and we have data, update the members list
    if (tabName === 'members' && window.currentGroupData) {
        updateMembersTab();
    } else if (tabName === 'stats' && window.currentGroupData) {
        updateStatsTab();
    }
}

function updateMembersTab() {
    const membersContent = document.getElementById('members-content');
    const controls = `
        <div class="controls">
            <div class="search-box">
                <input type="text" id="memberSearch" placeholder="Search members..." onkeyup="filterAndSortMembers()">
            </div>
            <div class="sort-controls">
                <select id="sortBy" onchange="filterAndSortMembers()">
                    <option value="name">Name</option>
                    <option value="exp">Experience</option>
                    <option value="ehp">EHP</option>
                    <option value="ehb">EHB</option>
                </select>
                <button onclick="toggleSortDirection()">
                    <span id="sortDirection">v</span>
                </button>
            </div>
        </div>
    `;
    membersContent.innerHTML = controls + '<div id="membersList"></div>';
    filterAndSortMembers();
}

function updateStatsTab() {
    const statsContent = document.getElementById('group-stats');
    if (!window.currentGroupData) {
        statsContent.innerHTML = '<p>Please fetch group details first</p>';
        return;
    }

    const members = window.currentGroupData.memberships;
    const totalExp = members.reduce((sum, m) => sum + (m.player.exp || 0), 0);
    const totalEHP = members.reduce((sum, m) => sum + (m.player.ehp || 0), 0);
    const totalEHB = members.reduce((sum, m) => sum + (m.player.ehb || 0), 0);
    const avgExp = totalExp / members.length;
    const avgEHP = totalEHP / members.length;
    const avgEHB = totalEHB / members.length;

    statsContent.innerHTML = `
        <div class="stats-grid">
            <div class="stat-item">
                <div class="stat-label">Total Experience</div>
                <div class="stat-value">${formatNumber(totalExp)}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Average Experience</div>
                <div class="stat-value">${formatNumber(Math.floor(avgExp))}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Total EHP</div>
                <div class="stat-value">${formatNumber(Math.floor(totalEHP))}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Average EHP</div>
                <div class="stat-value">${formatNumber(Math.floor(avgEHP))}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Total EHB</div>
                <div class="stat-value">${formatNumber(Math.floor(totalEHB))}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Average EHB</div>
                <div class="stat-value">${formatNumber(Math.floor(avgEHB))}</div>
            </div>
        </div>
    `;
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
            document.getElementById('saveButton').disabled = true;
            window.currentGroupData = null;
        } else {
            window.currentGroupData = result;

            // Display group info in the group tab
            const groupInfo = `
                <div class="group-info">
                    <h2>${result.name}</h2>
                    <p><strong>Member Count:</strong> ${formatNumber(result.memberships.length)}</p>
                    <p><strong>Created At:</strong> ${formatDate(result.createdAt)}</p>
                    <p><strong>Last Updated:</strong> ${formatDate(result.updatedAt)}</p>
                    <p><strong>Description:</strong> ${result.description || 'No description'}</p>
                    <p><strong>Clan Chat:</strong> ${result.clanChat || 'Not specified'}</p>
                    <p><strong>Homepage:</strong> ${result.homeworld ? `World ${result.homeworld}` : 'Not specified'}</p>
                </div>
            `;
            document.getElementById('result').innerHTML = groupInfo;
            document.getElementById('saveButton').disabled = false;

            // Update other tabs
            updateMembersTab();
            updateStatsTab();
        }
    } catch (error) {
        document.getElementById('result').innerHTML = `Error: ${error.message}`;
        document.getElementById('saveButton').disabled = true;
        window.currentGroupData = null;
    }
}

// Global variables for sorting state
window.sortAscending = false;

function toggleSortDirection() {
    window.sortAscending = !window.sortAscending;
    document.getElementById('sortDirection').textContent = window.sortAscending ? '^' : 'v';
    filterAndSortMembers();
}

function filterAndSortMembers() {
    if (!window.currentGroupData) return;

    const searchTerm = document.getElementById('memberSearch').value.toLowerCase();
    const sortBy = document.getElementById('sortBy').value;
    
    let filteredMembers = window.currentGroupData.memberships.filter(membership => {
        const playerName = (membership.player.displayName || membership.player.username).toLowerCase();
        return playerName.includes(searchTerm);
    });

    // Sort members
    filteredMembers.sort((a, b) => {
        let valueA, valueB;
        
        switch(sortBy) {
            case 'name':
                valueA = (a.player.displayName || a.player.username).toLowerCase();
                valueB = (b.player.displayName || b.player.username).toLowerCase();
                return window.sortAscending ? 
                    valueA.localeCompare(valueB) : 
                    valueB.localeCompare(valueA);
            case 'exp':
                valueA = a.player.exp || 0;
                valueB = b.player.exp || 0;
                break;
            case 'ehp':
                valueA = a.player.ehp || 0;
                valueB = b.player.ehp || 0;
                break;
            case 'ehb':
                valueA = a.player.ehb || 0;
                valueB = b.player.ehb || 0;
                break;
        }

        return window.sortAscending ? valueA - valueB : valueB - valueA;
    });

    // Render filtered and sorted members
    const membersList = `
        <h3>Members (${filteredMembers.length})</h3>
        <div class="members-list">
            ${filteredMembers.map(membership => `
                <div class="member-card">
                    <h3>${membership.player.displayName || membership.player.username}</h3>
                    <div class="member-stats">
                        <div class="stats-grid">
                            <div class="stat-item">
                                <div class="stat-label">Role</div>
                                <div class="stat-value">${membership.role || 'Member'}</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-label">Type</div>
                                <div class="stat-value">${membership.player.type || 'regular'}</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-label">Experience</div>
                                <div class="stat-value">${formatNumber(membership.player.exp || 0)}</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-label">EHP</div>
                                <div class="stat-value">${formatNumber(Math.floor(membership.player.ehp || 0))}</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-label">EHB</div>
                                <div class="stat-value">${formatNumber(Math.floor(membership.player.ehb || 0))}</div>
                            </div>
                        </div>
                    </div>
                </div>
            `).join('')}
        </div>
    `;

    document.getElementById('membersList').innerHTML = membersList;
}

async function saveInfo() {
    if (!window.currentGroupData) {
        alert('Please fetch group details first');
        return;
    }

    try {
        const result = await ipcRenderer.invoke('save-group-info', window.currentGroupData);
        if (result.success) {
            alert(`Group info saved successfully as "${result.displayName}"`);
        } else {
            alert('Failed to save group info: ' + result.error);
        }
    } catch (error) {
        alert('Error saving group info: ' + error.message);
    }
}

// Handle logs from main process
ipcRenderer.on('log', (event, message) => {
    const logDiv = document.getElementById('log');
    // Add a newline before the message if the log is not empty
    if (logDiv.innerHTML) {
        logDiv.innerHTML += '\n' + message;
    } else {
        logDiv.innerHTML = message;
    }
    logDiv.scrollTop = logDiv.scrollHeight;
}); 