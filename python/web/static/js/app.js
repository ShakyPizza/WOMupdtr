function getRankPalette() {
    const paletteNode = document.getElementById("rank-palette");
    if (!paletteNode) {
        return {};
    }
    try {
        return JSON.parse(paletteNode.textContent);
    } catch (_error) {
        return {};
    }
}

const RANK_COLORS = getRankPalette();
const chartInstances = new Map();

function formatDuration(startedAt) {
    const diff = Math.max(0, Math.floor((Date.now() - startedAt.getTime()) / 1000));
    const hours = Math.floor(diff / 3600);
    const minutes = Math.floor((diff % 3600) / 60);
    const seconds = diff % 60;
    return `${hours}h ${minutes}m ${seconds}s`;
}

function initUptime() {
    document.querySelectorAll("[data-uptime]").forEach((element) => {
        const { started } = element.dataset;
        if (!started) {
            element.textContent = "N/A";
            return;
        }
        const startDate = new Date(started);
        const render = () => {
            element.textContent = formatDuration(startDate);
        };
        render();
        window.setInterval(render, 1000);
    });
}

function chartMessage(targetId, message, isError = false) {
    const messageNode = document.getElementById(targetId);
    if (!messageNode) {
        return;
    }
    messageNode.textContent = message;
    messageNode.classList.toggle("error", isError);
}

function destroyChart(canvasId) {
    const instance = chartInstances.get(canvasId);
    if (instance) {
        instance.destroy();
        chartInstances.delete(canvasId);
    }
}

async function fetchJson(url) {
    const response = await fetch(url);
    const data = await response.json();
    return {
        data,
        error: response.headers.get("X-Data-Error"),
    };
}

function baseChartOptions(title, extra = {}) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                labels: { color: "#f4efe2" },
            },
            title: {
                display: true,
                text: title,
                color: "#f4efe2",
                font: { family: "Cinzel" },
            },
        },
        scales: {
            x: {
                ticks: { color: "#d9d3c4" },
                grid: { color: "rgba(255, 255, 255, 0.08)" },
            },
            y: {
                ticks: { color: "#d9d3c4" },
                grid: { color: "rgba(255, 255, 255, 0.08)" },
            },
        },
        ...extra,
    };
}

function doughnutChartOptions(title) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: "right",
                labels: { color: "#f4efe2" },
            },
            title: {
                display: true,
                text: title,
                color: "#f4efe2",
                font: { family: "Cinzel" },
            },
        },
    };
}

async function loadRankDistribution() {
    const canvas = document.getElementById("rankDistChart");
    if (!canvas) {
        return;
    }
    destroyChart("rankDistChart");
    const result = await fetchJson("/charts/api/rank-distribution");
    const labels = Object.keys(result.data || {});
    if (!labels.length) {
        canvas.closest("[data-chart-panel]").innerHTML = '<p class="empty-state">No rank distribution data available yet.</p>';
        return;
    }
    const chart = new Chart(canvas, {
        type: "doughnut",
        data: {
            labels,
            datasets: [{
                data: Object.values(result.data),
                backgroundColor: labels.map((label) => RANK_COLORS[label] || "#69707d"),
                borderColor: "#101416",
                borderWidth: 2,
            }],
        },
        options: doughnutChartOptions("Rank Distribution"),
    });
    chartInstances.set("rankDistChart", chart);
    if (result.error) {
        canvas.insertAdjacentHTML("beforebegin", `<p class="chart-message error">${result.error}</p>`);
    }
}

async function loadTopPlayers(limit = 15) {
    const canvas = document.getElementById("topPlayersChart");
    if (!canvas) {
        return;
    }
    destroyChart("topPlayersChart");
    const result = await fetchJson(`/charts/api/top-players?limit=${limit}`);
    if (!result.data?.length) {
        canvas.closest("[data-chart-panel]").innerHTML = '<p class="empty-state">No player data is available yet.</p>';
        return;
    }
    const chart = new Chart(canvas, {
        type: "bar",
        data: {
            labels: result.data.map((player) => player.username),
            datasets: [{
                label: "EHB",
                data: result.data.map((player) => player.ehb),
                backgroundColor: result.data.map((player) => RANK_COLORS[player.rank] || "#dcbc71"),
                borderColor: "#101416",
                borderWidth: 1,
            }],
        },
        options: baseChartOptions("Top Players by EHB", {
            indexAxis: "y",
            plugins: {
                ...baseChartOptions("Top Players by EHB").plugins,
                legend: { display: false },
            },
        }),
    });
    chartInstances.set("topPlayersChart", chart);
}

async function renderPlayerHistory(username, canvasId, messageId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !username) {
        return;
    }
    destroyChart(canvasId);
    chartMessage(messageId, "Loading chart...");
    const result = await fetchJson(`/charts/api/ehb-history?player=${encodeURIComponent(username)}`);
    if (result.error) {
        chartMessage(messageId, result.error, true);
        return;
    }
    if (!result.data?.length) {
        chartMessage(messageId, "No EHB history data is available for this player.");
        return;
    }
    chartMessage(messageId, `${username} history loaded.`);
    const chart = new Chart(canvas, {
        type: "line",
        data: {
            labels: result.data.map((entry) => entry.timestamp),
            datasets: [{
                label: "EHB",
                data: result.data.map((entry) => entry.ehb),
                borderColor: "#dcbc71",
                backgroundColor: "rgba(220, 188, 113, 0.16)",
                fill: true,
                tension: 0.28,
            }],
        },
        options: baseChartOptions(`${username} - EHB History`, {
            plugins: {
                ...baseChartOptions(`${username} - EHB History`).plugins,
                legend: { display: false },
            },
        }),
    });
    chartInstances.set(canvasId, chart);
}

function initHistorySelect() {
    const container = document.querySelector("[data-player-history-select]");
    if (!container) {
        return;
    }
    const select = container.querySelector("select");
    const canvasId = container.dataset.historyTarget;
    const messageId = container.dataset.historyMessage;
    if (!select) {
        return;
    }
    select.addEventListener("change", () => {
        if (!select.value) {
            chartMessage(messageId, "Choose a player to load their history chart.");
            destroyChart(canvasId);
            return;
        }
        renderPlayerHistory(select.value, canvasId, messageId);
    });
}

function initHistoryPlayer() {
    const container = document.querySelector("[data-player-history-player]");
    if (!container) {
        return;
    }
    const username = container.dataset.playerHistoryPlayer;
    renderPlayerHistory(username, container.dataset.historyTarget, container.dataset.historyMessage);
}

document.addEventListener("DOMContentLoaded", () => {
    initUptime();
    loadRankDistribution();
    loadTopPlayers();
    initHistorySelect();
    initHistoryPlayer();
});
