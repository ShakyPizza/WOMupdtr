package com.yourname.womintegration;

import com.google.gson.Gson;
import com.google.inject.Provides;
import java.io.IOException;
import java.time.Instant;
import java.util.List;
import javax.inject.Inject;
import lombok.extern.slf4j.Slf4j;
import net.runelite.api.ChatMessageType;
import net.runelite.api.Client;
import net.runelite.api.events.GameTick;
import net.runelite.client.callback.ClientThread;
import net.runelite.client.chat.ChatMessageBuilder;
import net.runelite.client.chat.ChatMessageManager;
import net.runelite.client.chat.ChatColorType;
import net.runelite.client.chat.QueuedMessage;
import net.runelite.client.config.Config;
import net.runelite.client.config.ConfigGroup;
import net.runelite.client.config.ConfigItem;
import net.runelite.client.config.ConfigManager;
import net.runelite.client.plugins.Plugin;
import net.runelite.client.plugins.PluginDescriptor;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

@Slf4j
@PluginDescriptor(
    name = "Wise Old Man Integration (Single File)",
    description = "Fetches group data from the WOM API and shows it in chat",
    tags = {"wiseoldman", "group", "ehb"}
)
public class WomPlugin extends Plugin
{
    // -------------------------------
    // 1) Fields/Objects we need
    // -------------------------------
    private static final Gson GSON = new Gson();
    private static final OkHttpClient HTTP_CLIENT = new OkHttpClient();

    // How often to fetch (in seconds). For demo, every 120s
    private static final int FETCH_INTERVAL = 120;

    @Inject
    private Client client;

    @Inject
    private ClientThread clientThread;

    @Inject
    private ChatMessageManager chatMessageManager;

    // Our config interface is defined below as a nested interface
    @Inject
    private WomPluginConfig config;

    private Instant lastFetch = Instant.now();

    // -------------------------------
    // 2) Provide Config
    // -------------------------------
    @Provides
    WomPluginConfig provideConfig(ConfigManager configManager)
    {
        return configManager.getConfig(WomPluginConfig.class);
    }

    // -------------------------------
    // 3) Plugin Lifecycle
    // -------------------------------
    @Override
    protected void startUp()
    {
        log.info("WOM Plugin (Single File) started!");
    }

    @Override
    protected void shutDown()
    {
        log.info("WOM Plugin (Single File) stopped!");
    }

    // -------------------------------
    // 4) Periodic Update
    // -------------------------------
    @Override
    public void onGameTick(GameTick event)
    {
        // We'll fetch data every FETCH_INTERVAL seconds
        if (Instant.now().isAfter(lastFetch.plusSeconds(FETCH_INTERVAL)))
        {
            lastFetch = Instant.now();
            fetchGroupData();
        }
    }

    // -------------------------------
    // 5) Fetch & Parse Data
    // -------------------------------
    private void fetchGroupData()
    {
        // Read group ID from config (the user sets this in the plugin settings)
        String groupId = config.groupId();
        if (groupId == null || groupId.isEmpty())
        {
            log.warn("No WOM group ID set in plugin config!");
            return;
        }

        String url = "https://api.wiseoldman.net/v2/groups/" + groupId;

        Request request = new Request.Builder()
            .url(url)
            // If you have an API key, you'd do something like:
            // .addHeader("x-api-key", config.apiKey())
            .build();

        // Offload the blocking call to clientThread.invoke(...) 
        clientThread.invoke(() -> {
            try (Response response = HTTP_CLIENT.newCall(request).execute())
            {
                if (!response.isSuccessful())
                {
                    log.error("Failed to fetch WOM group data, HTTP code: {}", response.code());
                    return;
                }

                // Convert JSON -> our data classes (WomData, Membership, Player)
                String body = response.body().string();
                WomData data = GSON.fromJson(body, WomData.class);
                if (data == null)
                {
                    log.error("Received null data or invalid JSON from WOM.");
                    return;
                }

                String groupName = data.getName();
                int memberCount = (data.getMemberships() != null) ? data.getMemberships().size() : 0;

                sendChatMessage("Group: " + groupName + " has " + memberCount + " members!");
            }
            catch (IOException e)
            {
                log.error("Error while fetching group data", e);
            }
        });
    }

    // -------------------------------
    // 6) Send a Chat Message
    // -------------------------------
    private void sendChatMessage(String text)
    {
        String chatMessage = new ChatMessageBuilder()
            .append(ChatColorType.HIGHLIGHT)
            .append(text)
            .build();

        chatMessageManager.queue(
            QueuedMessage.builder()
                .type(ChatMessageType.GAMEMESSAGE)
                .runeLiteFormattedMessage(chatMessage)
                .build()
        );
    }

    // -------------------------------
    // 7) Our Config (Nested Interface)
    // -------------------------------
    @ConfigGroup("womintegration")
    public interface WomPluginConfig extends Config
    {
        @ConfigItem(
            keyName = "groupId",
            name = "WOM Group ID",
            description = "The Wise Old Man group ID to fetch data for"
        )
        default String groupId()
        {
            return "";
        }

        // If you want an API key, uncomment:
        // @ConfigItem(
        //    keyName = "apiKey",
        //    name = "API Key",
        //    description = "Wise Old Man API Key (if you have one)"
        // )
        // default String apiKey() { return ""; }
    }

    // -------------------------------
    // 8) Data Classes (Nested)
    // -------------------------------
    // If you want them separate, normally you'd put these in WomData.java
    private static class WomData
    {
        private int id;
        private String name;
        private List<Membership> memberships;

        public int getId() { return id; }
        public String getName() { return name; }
        public List<Membership> getMemberships() { return memberships; }
    }

    private static class Membership
    {
        private Player player;
        public Player getPlayer() { return player; }
    }

    private static class Player
    {
        private int id;
        private String displayName;
        private double ehb;

        public int getId() { return id; }
        public String getDisplayName() { return displayName; }
        public double getEhb() { return ehb; }
    }
}
