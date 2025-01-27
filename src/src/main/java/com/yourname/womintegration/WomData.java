package com.yourname.womintegration;

import java.util.List;

/**
 * Represents the JSON response for a Wise Old Man group.
 */
public class WomData
{
    private int id;
    private String name;
    private String description;
    private List<Membership> memberships;

    public int getId()
    {
        return id;
    }

    public String getName()
    {
        return name;
    }

    public String getDescription()
    {
        return description;
    }

    public List<Membership> getMemberships()
    {
        return memberships;
    }

    /**
     * Represents a group membership.
     */
    public static class Membership
    {
        private Player player;

        public Player getPlayer()
        {
            return player;
        }
    }

    /**
     * Represents a player in the group.
     */
    public static class Player
    {
        private int id;
        private String displayName;
        private double ehb; // Efficient hours bossed
        private double ehp; // Efficient hours played

        public int getId()
        {
            return id;
        }

        public String getDisplayName()
        {
            return displayName;
        }

        public double getEhb()
        {
            return ehb;
        }

        public double getEhp()
        {
            return ehp;
        }
    }
}
