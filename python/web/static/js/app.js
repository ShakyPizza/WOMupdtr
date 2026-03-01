// OSRS-themed colors for rank distribution
const RANK_COLORS = {
    'goblin': '#2d5016',
    'Opal': '#a8c8e0',
    'Sapphire': '#0f52ba',
    'Emerald': '#50c878',
    'Red Topaz': '#ff6347',
    'Ruby': '#e0115f',
    'Diamond': '#b9f2ff',
    'Dragonstone': '#7851a9',
    'Onyx': '#353839',
    'Zenyte': '#ffd700',
};

async function loadRankDistribution() {
    const canvas = document.getElementById('rankDistChart');
    if (!canvas) return;
    const resp = await fetch('/charts/api/rank-distribution');
    const data = await resp.json();
    const labels = Object.keys(data);
    const values = Object.values(data);
    const colors = labels.map(l => RANK_COLORS[l] || '#888');
    new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: colors,
                borderWidth: 1,
                borderColor: '#333',
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'right', labels: { color: '#ccc' } },
                title: { display: true, text: 'Rank Distribution', color: '#ccc' }
            }
        }
    });
}

async function loadTopPlayers(limit = 15) {
    const canvas = document.getElementById('topPlayersChart');
    if (!canvas) return;
    const resp = await fetch(`/charts/api/top-players?limit=${limit}`);
    const data = await resp.json();
    new Chart(canvas, {
        type: 'bar',
        data: {
            labels: data.map(p => p.username),
            datasets: [{
                label: 'EHB',
                data: data.map(p => p.ehb),
                backgroundColor: data.map(p => RANK_COLORS[p.rank] || '#4CAF50'),
                borderWidth: 1,
                borderColor: '#333',
            }]
        },
        options: {
            responsive: true,
            indexAxis: 'y',
            plugins: {
                legend: { display: false },
                title: { display: true, text: 'Top Players by EHB', color: '#ccc' }
            },
            scales: {
                x: { ticks: { color: '#ccc' }, grid: { color: '#333' } },
                y: { ticks: { color: '#ccc' }, grid: { color: '#333' } }
            }
        }
    });
}

async function loadPlayerChart(username) {
    const canvas = document.getElementById('ehbChart');
    if (!canvas) return;
    const resp = await fetch(`/charts/api/ehb-history?player=${encodeURIComponent(username)}`);
    const data = await resp.json();
    if (!data.length) {
        canvas.parentElement.innerHTML = '<p>No EHB history data available for this player.</p>';
        return;
    }
    new Chart(canvas, {
        type: 'line',
        data: {
            labels: data.map(e => e.timestamp),
            datasets: [{
                label: 'EHB',
                data: data.map(e => e.ehb),
                borderColor: '#4CAF50',
                backgroundColor: 'rgba(76, 175, 80, 0.1)',
                fill: true,
                tension: 0.3,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                title: { display: true, text: `${username} - EHB History`, color: '#ccc' }
            },
            scales: {
                x: { ticks: { color: '#ccc', maxTicksLimit: 10 }, grid: { color: '#333' } },
                y: { ticks: { color: '#ccc' }, grid: { color: '#333' } }
            }
        }
    });
}

// Auto-initialize charts on page load
document.addEventListener('DOMContentLoaded', () => {
    loadRankDistribution();
    loadTopPlayers();
});
