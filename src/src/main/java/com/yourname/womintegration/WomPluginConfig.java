package com.yourname.womintegration;

import net.runelite.client.config.Config;
import net.runelite.client.config.ConfigGroup;
import net.runelite.client.config.ConfigItem;

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

    @ConfigItem(
        keyName = "apiKey",
        name = "API Key",
        description = "Wise Old Man API Key (optional)"
    )
    default String apiKey()
    {
        return "";
    }
}
