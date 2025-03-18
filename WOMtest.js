// WOMtest.js
// A test script to gather data from the Wise Old Man API, now with javascript!

const { app, BrowserWindow, ipcMain } = require('electron');
const { WOMClient } = require('@wise-old-man/utils');
const fs = require('fs');
const path = require('path');

let mainWindow;

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 800,
        height: 600,
        webPreferences: {
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    mainWindow.loadFile('index.html');
}

// Helper function to log messages with timestamp
function log(message) {
    const timestamp = new Date().toISOString();
    const logMessage = `${timestamp} - ${message}`;
    console.log(logMessage);
    if (mainWindow) {
        mainWindow.webContents.send('log', logMessage);
    }
}

async function fetchGroupDetails(groupId) {
    try {
        // Initialize WOM client
        const client = new WOMClient();
        log("WOM client initialized");

        // Fetch group details
        const result = await client.groups.getGroupDetails(groupId);
        log("Group details fetched successfully");

        // Create output directory if it doesn't exist
        const outputDir = path.join(__dirname, 'output');
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir);
        }

        // Save to JSON file with pretty formatting
        const outputPath = path.join(outputDir, 'group_details.json');
        fs.writeFileSync(
            outputPath,
            JSON.stringify(result, null, 2)
        );
        log(`Group details saved to ${outputPath}`);

        return {
            name: result.name,
            memberCount: result.memberCount,
            createdAt: result.createdAt,
            updatedAt: result.updatedAt
        };

    } catch (error) {
        log(`Error: ${error.message}`);
        throw error;
    }
}

// Set up electron app
app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});

// Handle IPC messages from renderer
ipcMain.handle('fetch-group', async (event, groupId) => {
    try {
        return await fetchGroupDetails(groupId);
    } catch (error) {
        return { error: error.message };
    }
});


