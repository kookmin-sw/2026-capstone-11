namespace Game.Server
{
    public class SessionEvents
    {
        public Action? OnSessionStart = null;
        public Action? OnSessionEnd = null;
        public Action<string>? OnPlayerEnter = null;
        public Action<string>? OnPlayerExit = null;
        public Func<string, byte[], byte[]>? OnGetQuery = null;
        public Action<string, byte[]>? OnGetResponse = null;
        public Action<string, byte[]>? OnGetMessage = null;
    }

}