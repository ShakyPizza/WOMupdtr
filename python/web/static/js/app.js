/* global Chart */

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
    messageNode.setAttribute("role", isError ? "alert" : "status");
    messageNode.setAttribute("aria-live", isError ? "assertive" : "polite");
}

function chartPanelMessage(canvas, message, isError = false) {
    const panel = canvas.closest("[data-chart-panel]");
    if (!panel) {
        return;
    }
    let messageNode = panel.querySelector("[data-chart-state]");
    if (!messageNode) {
        messageNode = document.createElement("p");
        messageNode.dataset.chartState = "";
        panel.insertBefore(messageNode, canvas);
    }
    messageNode.className = isError ? "chart-message error" : "empty-state";
    messageNode.textContent = message;
    messageNode.setAttribute("role", isError ? "alert" : "status");
    messageNode.setAttribute("aria-live", isError ? "assertive" : "polite");
    canvas.hidden = true;
}

function clearChartPanelMessage(canvas) {
    const panel = canvas.closest("[data-chart-panel]");
    panel?.querySelector("[data-chart-state]")?.remove();
    canvas.hidden = false;
}

function destroyChart(canvasId) {
    const instance = chartInstances.get(canvasId);
    if (instance) {
        instance.destroy();
        chartInstances.delete(canvasId);
    }
}

function safeRankColor(rank, fallback) {
    return Object.hasOwn(RANK_COLORS, rank) ? RANK_COLORS[rank] : fallback;
}

async function fetchJson(url) {
    if (typeof url !== "string" || (!url.startsWith("/") && !url.startsWith(window.location.origin))) {
        throw new Error("Invalid URL");
    }
    const response = await fetch(url);
    const serverError = response.headers.get("X-Data-Error");
    if (!response.ok || serverError) {
        throw new Error(serverError || `Chart data request failed (${response.status}).`);
    }
    let data;
    try {
        data = await response.json();
    } catch (_error) {
        throw new Error("The server returned an invalid chart data response.");
    }
    return {
        data,
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
    clearChartPanelMessage(canvas);
    try {
        const result = await fetchJson("/charts/api/rank-distribution");
        const labels = Object.keys(result.data || {});
        if (!labels.length) {
            chartPanelMessage(canvas, "No rank distribution data available yet.");
            return;
        }
        const chart = new Chart(canvas, {
            type: "doughnut",
            data: {
                labels,
                datasets: [{
                    data: Object.values(result.data),
                    backgroundColor: labels.map((label) => safeRankColor(label, "#69707d")),
                    borderColor: "#101416",
                    borderWidth: 2,
                }],
            },
            options: doughnutChartOptions("Rank Distribution"),
        });
        chartInstances.set("rankDistChart", chart);
    } catch (error) {
        chartPanelMessage(canvas, error.message || "Rank distribution could not be loaded.", true);
    }
}

async function loadTopPlayers(limit = 15) {
    const canvas = document.getElementById("topPlayersChart");
    if (!canvas) {
        return;
    }
    destroyChart("topPlayersChart");
    clearChartPanelMessage(canvas);
    try {
        const result = await fetchJson(`/charts/api/top-players?limit=${limit}`);
        if (!result.data?.length) {
            chartPanelMessage(canvas, "No player data is available yet.");
            return;
        }
        const chart = new Chart(canvas, {
            type: "bar",
            data: {
                labels: result.data.map((player) => player.username),
                datasets: [{
                    label: "EHB",
                    data: result.data.map((player) => player.ehb),
                    backgroundColor: result.data.map((player) => safeRankColor(player.rank, "#dcbc71")),
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
    } catch (error) {
        chartPanelMessage(canvas, error.message || "Top-player data could not be loaded.", true);
    }
}

async function renderPlayerHistory(username, canvasId, messageId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !username) {
        return;
    }
    destroyChart(canvasId);
    chartMessage(messageId, "Loading chart...");
    try {
        const result = await fetchJson(`/charts/api/ehb-history?player=${encodeURIComponent(username)}`);
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
    } catch (error) {
        chartMessage(messageId, error.message || "EHB history could not be loaded.", true);
    }
}

async function renderPlayerMetricHistory(url, label, valueKey, canvasId, messageId, color) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) {
        return;
    }
    destroyChart(canvasId);
    chartMessage(messageId, "Loading chart...");
    try {
        const result = await fetchJson(url);
        if (!result.data?.length) {
            chartMessage(messageId, `No ${label} data is available for this player.`);
            return;
        }
        chartMessage(messageId, `${label} loaded.`);
        const chart = new Chart(canvas, {
            type: "line",
            data: {
                labels: result.data.map((entry) => entry.timestamp),
                datasets: [{
                    label,
                    // valueKey is a fixed, developer-supplied metric name (not user input); entry is our own API row.
                    // eslint-disable-next-line security/detect-object-injection
                    data: result.data.map((entry) => entry[valueKey]),
                    borderColor: color,
                    backgroundColor: "rgba(220, 188, 113, 0.16)",
                    fill: true,
                    tension: 0.28,
                }],
            },
            options: baseChartOptions(label, {
                plugins: {
                    ...baseChartOptions(label).plugins,
                    legend: { display: false },
                },
            }),
        });
        chartInstances.set(canvasId, chart);
    } catch (error) {
        chartMessage(messageId, error.message || `${label} could not be loaded.`, true);
    }
}

function initEhpHistoryPlayer() {
    const container = document.querySelector("[data-player-ehp-player]");
    if (!container) {
        return;
    }
    const username = container.dataset.playerEhpPlayer;
    renderPlayerMetricHistory(
        `/charts/api/ehp-history?player=${encodeURIComponent(username)}`,
        `${username} - EHP History`,
        "ehp",
        container.dataset.ehpTarget,
        container.dataset.ehpMessage,
        "#6fb2d6",
    );
}

function initEhpHistorySelect() {
    const container = document.querySelector("[data-player-ehp-select]");
    if (!container) {
        return;
    }
    const select = container.querySelector("select");
    const canvasId = container.dataset.ehpTarget;
    const messageId = container.dataset.ehpMessage;
    if (!select) {
        return;
    }
    select.addEventListener("change", () => {
        if (!select.value) {
            chartMessage(messageId, "Choose a player to load their EHP history.");
            destroyChart(canvasId);
            return;
        }
        renderPlayerMetricHistory(
            `/charts/api/ehp-history?player=${encodeURIComponent(select.value)}`,
            `${select.value} - EHP History`,
            "ehp",
            canvasId,
            messageId,
            "#6fb2d6",
        );
    });
}

function initGainsSelect() {
    const container = document.querySelector("[data-player-gains-select]");
    if (!container) {
        return;
    }
    const select = container.querySelector("select");
    const metricSelect = container.querySelector("[data-gains-metric]");
    const canvasId = container.dataset.gainsTarget;
    const messageId = container.dataset.gainsMessage;
    if (!select) {
        return;
    }
    const load = () => {
        if (!select.value) {
            chartMessage(messageId, "Choose a player to load their gains history.");
            destroyChart(canvasId);
            return;
        }
        const metric = metricSelect ? metricSelect.value : "overall";
        renderPlayerMetricHistory(
            `/charts/api/gains-history?player=${encodeURIComponent(select.value)}&metric=${encodeURIComponent(metric)}`,
            `${select.value} - ${metric} gains`,
            "gained",
            canvasId,
            messageId,
            "#c8a24a",
        );
    };
    select.addEventListener("change", load);
    if (metricSelect) {
        metricSelect.addEventListener("change", load);
    }
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
    initEhpHistoryPlayer();
    initEhpHistorySelect();
    initGainsSelect();
});
