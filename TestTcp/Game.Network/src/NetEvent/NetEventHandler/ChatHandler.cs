
using System.Buffers.Binary;
using System.Text;

namespace Game.Network
{
    public class ChatHandler : INetEventHandler
    {
        private INetAPI _net;
        private Task<QueryTaskResult>? _questionTask;


        public static ChatHandler Create(INetAPI net)
        {
            var ch = new ChatHandler(net);
            net.SetReceiveHandler(NetEventHandlerId.Chat, ch);
            return ch;
        }   

        private ChatHandler(INetAPI net)
        {
            _net = net;
            _questionTask = null;
        }

        public void Chat(string targetId, string msg)
        {
            _net.Send(
                NetEventHandlerId.Chat,
                0,
                targetId,
                Encoding.UTF8.GetBytes(msg) 
            );
        }

        public void Question(string targetId, string msg)
        {
            if (_questionTask == null)
            {
                _questionTask = _net.AsyncRequestQuery(
                    NetEventHandlerId.Chat,
                    targetId,
                    Encoding.UTF8.GetBytes(msg),
                    DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() + 3000
                );
                return;
            }

            if (!_questionTask.IsCompletedSuccessfully) return;
            else
            {
                QueryTaskResult result = _questionTask.Result;
                if (result.IsResponded)
                    Log.WriteLog("Answer : " + BitConverter.ToString(result.AnswerRaw));

                else if (result.IsTimeOut) 
                    Log.WriteLog("Question Ignored");

                else if (result.IsCancelled) 
                    Log.WriteLog("Question Failed");
                
                _questionTask = null;
            }
        }

        // Data
        public void OnReceive(string ConnId, byte[] raw)
        {
            Log.WriteLog($"[Chat] From {ConnId} : {BitConverter.ToString(raw)}");    
        }

        public void OnRespond(string ConnId, int queryNum, byte[] raw) {}
        public void OnQuery(string ConnId, int queryNum, byte[] raw)
        {
            Log.WriteLog($"[Chat] From {ConnId} : {BitConverter.ToString(raw)}");  
            Log.WriteLog($"[Chat] Answer? : ...");
        }

        // Control
        public void OnException(string ConnId, byte[] raw, string msg) {}
        public void OnHello(string ConnId, byte[] raw) {}
        public void OnDisconnect(string ConnId, byte[] raw) {}
    };
}