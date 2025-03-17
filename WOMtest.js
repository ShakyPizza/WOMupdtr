// WOMtest.js
// A test script to gather data from the Wise Old Man API

const { WOMClient } = require('@wise-old-man/utils');
const fs = require('fs');
const path = require('path');

// Helper function to log messages with timestamp
function log(message) {
    const timestamp = new Date().toISOString();
    console.log(`${timestamp} - ${message}`);
}

async function main() {
    try {
        // Initialize WOM client
        const client = new WOMClient();
        log("WOM client initialized");

        // Fetch group details (replace 123 with your group ID)
        const result = await client.groups.getGroupDetails(2300);
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

        // Print summary to console
        console.log("\nGroup Summary:");
        console.log(`Name: ${result.name}`);
        console.log(`Member Count: ${result.memberCount}`);
        console.log(`Created At: ${result.createdAt}`);
        console.log(`Last Updated: ${result.updatedAt}`);

    } catch (error) {
        console.error("Error:", error.message);
    }
}

// Run the main function
main();

