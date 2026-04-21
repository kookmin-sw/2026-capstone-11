using System.Runtime.InteropServices;
using Game.Network.Service;

namespace Game.Server
{
    public class SessionEvents
    {
        public Func<string, SimpleReq, SimpleRsp>? OnSessionPlayerDataUpdate = null;
        public Func<string, SimpleReq, SimpleRsp>? OnSessionPlayerReady = null;
        public Action<string>? OnPlayerEnter = null;
        public Action<string>? OnPlayerExit = null;
        public Func<string, byte[], byte[]>? OnGetQuery = null;
        public Action<string, byte[]>? OnGetResponse = null;
        public Action<string, byte[]>? OnGetMessage = null;

        public void Clear()
        {
            OnSessionPlayerDataUpdate = null;
            OnSessionPlayerReady = null;
            OnPlayerEnter = null;
            OnPlayerExit = null;
            OnGetQuery = null;
            OnGetResponse = null;
            OnGetMessage = null;
        }
    }

}