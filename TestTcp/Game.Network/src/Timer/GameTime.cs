

using System;

namespace Game.Network
{
    public static class GameTime
    {
        public static long GetNow() => DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
    };
}