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

    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
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
        const groupDetails = await client.groups.getGroupDetails(groupId);
        log("Group details fetched successfully");

        return groupDetails;

    } catch (error) {
        log(`Error: ${error.message}`);
        throw error;
    }
}

async function saveGroupInfo(groupData) {
    try {
        const outputDir = path.join(__dirname, '../../output');
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir);
        }

        // Debug logging
        log('Group data received:');
        log(JSON.stringify(groupData, null, 2));

        // Create a filename with the group ID and simplified timestamp
        const now = new Date();
        const dateStr = now.toLocaleDateString().replace(/\//g, '-');
        const timeStr = now.toLocaleTimeString('en-IS', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        }).replace(':', '-').replace(' ', '');
        
        // Ensure we have a valid group name and log it
        log('Raw group name: ' + groupData.name);
        const groupName = groupData.name || 'Unknown Group';
        log('Processed group name: ' + groupName);
        const safeGroupName = groupName.replace(/[^a-z0-9]/gi, '_').toLowerCase();
        
        const filename = `${safeGroupName}_${dateStr}_${timeStr}.json`;
        const displayName = `${groupName} (${dateStr} ${timeStr})`;
        
        const outputPath = path.join(outputDir, filename);

        // Save to JSON file with pretty formatting
        fs.writeFileSync(
            outputPath,
            JSON.stringify(groupData, null, 2)
        );
        log(`Group info saved to ${outputPath}`);

        return { 
            success: true, 
            filePath: outputPath, 
            filename: filename,
            displayName: displayName
        };
    } catch (error) {
        log(`Error saving group info: ${error.message}`);
        return { success: false, error: error.message };
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

ipcMain.handle('save-group-info', async (event, groupData) => {
    return await saveGroupInfo(groupData);
}); 