package com.yourname.richboys;

import com.google.gson.Gson;
import com.google.gson.JsonSyntaxException;
import net.runelite.client.config.ConfigManager;
import net.runelite.client.plugins.Plugin;
import net.runelite.client.plugins.PluginDescriptor;
import okhttp3.Call;
import okhttp3.Callback;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;

import javax.inject.Inject;
import java.io.IOException;

@PluginDescriptor(
    name = "Rich Boys",
    description = "Fetches and displays Wise Old Man group stats for the Rich Boys",
    tags = {"wiseoldman", "group", "ehb"}
)
public class RichBoysPlugin extends Plugin
{
    private static final String API_URL = "https://api.wiseoldman.net/v2/groups/";
    private static final Gson GSON = new Gson();

    @Inject
    private OkHttpClient httpClient;

    @Inject
    private RichBoysPluginConfig config;

    @Inject
    private ConfigManager configManager;

    @Override
    protected void startUp() throws Exception
    {
        fetchGroupData(config.groupId());
    }

    @Override
    protected void shutDown() throws Exception
    {
        // Plugin cleanup logic here
    }

    private void fetchGroupData(String groupId)
    {
        if (groupId == null || groupId.isEmpty())
        {
            sendChatMessage("Please configure your Wise Old Man group ID in the plugin settings.");
            return;
        }

        String url = API_URL + groupId;
        if (!config.apiKey().isEmpty())
        {
            url += "?x-api-key=" + config.apiKey();
        }

        Request request = new Request.Builder()
            .url(url)
            .build();

        httpClient.newCall(request).enqueue(new Callback()
        {
            @Override
            public void onFailure(Call call, IOException e)
            {
                sendChatMessage("Failed to fetch data from Wise Old Man API: " + e.getMessage());
            }

            @Override
            public void onResponse(Call call, Response response) throws IOException
            {
                if (!response.isSuccessful())
                {
                    sendChatMessage("Failed to fetch data. Response code: " + response.code());
                    return;
                }

                try
                {
                    String responseBody = response.body().string();
                    RichBoysData womData = GSON.fromJson(responseBody, RichBoysData.class);
                    processGroupData(womData);
                }
                catch (JsonSyntaxException e)
                {
                    sendChatMessage("Error parsing response from Wise Old Man API.");
                }
            }
        });
    }

    private void processGroupData(RichBoysData womData)
    {
        if (womData == null || womData.getMemberships() == null)
        {
            sendChatMessage("No data found for the specified group.");
            return;
        }

        sendChatMessage("Group Name: " + womData.getName());
        sendChatMessage("Group Description: " + womData.getDescription());
        sendChatMessage("Number of Members: " + womData.getMemberships().size());
    }

    private void sendChatMessage(String message)
    {
        // You can replace this with your RuneLite chat message system
        System.out.println(message);
    }
}
