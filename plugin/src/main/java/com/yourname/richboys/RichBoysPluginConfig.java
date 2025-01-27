package com.yourname.richboys;

import net.runelite.client.config.Config;
import net.runelite.client.config.ConfigGroup;
import net.runelite.client.config.ConfigItem;

@ConfigGroup("richboys")
public interface RichBoysPluginConfig extends Config
{
    @ConfigItem(
        keyName = "groupId",
        name = "Group ID",
        description = "The Wise Old Man group ID for the Rich Boys"
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
