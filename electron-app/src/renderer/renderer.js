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
            // Store the result globally for filtering/sorting
            window.currentGroupData = result;

            // Display group info
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

            // Add filter and sort controls
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

            // Display member list (initial render)
            document.getElementById('result').innerHTML = groupInfo + controls + '<div id="membersList"></div>';
            filterAndSortMembers();
        }
    } catch (error) {
        document.getElementById('result').innerHTML = `Error: ${error.message}`;
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

// Handle logs from main process
ipcRenderer.on('log', (event, message) => {
    const logDiv = document.getElementById('log');
    logDiv.innerHTML += message + '\n';
    logDiv.scrollTop = logDiv.scrollHeight;
}); 