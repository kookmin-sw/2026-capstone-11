using System.Runtime.InteropServices;

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

        public void Clear()
        {
            OnSessionStart = null;
            OnSessionEnd = null;
            OnPlayerEnter = null;
            OnPlayerExit = null;
            OnGetQuery = null;
            OnGetResponse = null;
            OnGetMessage = null;
        }
    }

}