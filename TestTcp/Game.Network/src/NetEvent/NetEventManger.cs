

using System.Collections.Concurrent;
using System.Diagnostics;
using System.Text;

namespace Game.Network
{
    public class NetEventManger
    {
        private Dictionary<int, INetEventHandler> _handlerDict;
        private HashSet<INetEventHandler> _controlHandler;
        private Dictionary<(string ConnId, int queryNum), QueryRegistery> _queryDict;
        private int _maxDataPerTick;
        private int _maxControlPerTick;
        private int _query_seq;


        // for CheckTimeOut() cache
        private readonly List<(string, int)> _removeList = new();


        public void Init(NetEventQueue q)
        {

        }

        /// <summary>
        /// NetInEvent를 처리하면서, 등록된 핸들러를 호출.
        /// </summary>
        public void Tick(NetEventQueue q)
        {
            for (int i = 0; i < _maxControlPerTick; i++)
            {
                if (q.InControlQueue.TryDequeue(out var inEv))
                    ProcessNetInControl(inEv);
            }

            for (int i = 0; i < _maxDataPerTick; i++)
            {
                if (q.InQueue.TryDequeue(out var inCon))
                    ProcessNetInEvent(inCon);
            }

            CheckTimeOut();
        }

        public string GetState()
        {
            string msg = "";
            foreach (var item in _queryDict)
            {
                msg += $"\t [Registed Query] - ({item.Key.ConnId}, {item.Key.queryNum})\n";
            }

            return $"[EventManager:{this}] \n" +
                $"\t Max Process Per Tick : Control={_maxControlPerTick}, Data={_maxDataPerTick}\n" +
                $"\t Requested Handler : {_handlerDict.Count}\n" +
                $"\t Requested Query : {_queryDict.Count}\n" +
                msg;
        }

        public void CheckTimeOut()
        {
            // TODO: GameTime으로 바꾸기.
            var nowMs = GameTime.GetNow();
            _removeList.Clear();

            foreach (var item in _queryDict)
            {
                if (item.Value.ExpireTimeMs <= nowMs)
                    _removeList.Add(item.Key);
            }

            for (int i = 0; i < _removeList.Count; i++)
            {
                var key = _removeList[i];
                if (_queryDict.Remove(key, out var registery))
                {
                    registery.tcs.TrySetResult(new QueryTaskResult(QueryResultStatus.TimeOut, Array.Empty<byte>()));
                    registery.FailAction?.Invoke();
                }
            }
        }

        public void Stop()
        {

            var toDelete = _queryDict.Keys.ToList();

            for (int i = 0; i < toDelete.Count; i++)
            {
                if (_queryDict.Remove(toDelete[i], out var registery))
                    registery.tcs.TrySetResult(new QueryTaskResult(QueryResultStatus.Cancelled, Array.Empty<byte>()));
            }

        }
        public NetEventManger(int maxControlPerTick, int maxDataPerTick)
        {
            if (maxControlPerTick < 0 || maxDataPerTick < 0)
                throw new ArgumentException();

            _handlerDict = new();
            _controlHandler = new();

            _maxControlPerTick = maxControlPerTick;
            _maxDataPerTick = maxDataPerTick;

            _queryDict = new();
            _query_seq = 1;
        }



        public (int, Task<QueryTaskResult>) RegisterQueryTask(string ConnId, long expireTimeMs)
        {
            var registery = QueryRegistery.CreateQueryRegistery(_query_seq, GameTime.GetNow() + expireTimeMs);
            _queryDict.Add((ConnId, _query_seq), registery);
            _query_seq++;

            return (registery.QueryNum, registery.tcs.Task);
        }
        public (int, Task<QueryTaskResult>) RegisterQueryTask(string ConnId, long expireTimeMs, TaskCompletionSource<QueryTaskResult> tcs)
        {
            var registery = QueryRegistery.CreateQueryRegistery(_query_seq, GameTime.GetNow() + expireTimeMs, tcs);
            _queryDict.Add((ConnId, _query_seq), registery);
            _query_seq++;

            return (registery.QueryNum, registery.tcs.Task);
        }

        public (int, Task<QueryTaskResult>) RegisterQueryTask(string ConnId, long expireTimeMs, Action<byte[]>? succAction = null, Action? failAction = null)
        {
            var registery = QueryRegistery.CreateQueryRegistery(_query_seq, GameTime.GetNow() + expireTimeMs, succAction, failAction);
            _queryDict.Add((ConnId, _query_seq), registery);
            _query_seq++;

            return (registery.QueryNum, registery.tcs.Task);
        }

        public bool TryCancelQuery(string ConnId, int queryNum)
        {
            if (queryNum == 0) return false;

            if (_queryDict.Remove((ConnId, queryNum), out var registery))
            {
                registery.tcs.TrySetResult(new QueryTaskResult(QueryResultStatus.Cancelled, Array.Empty<byte>()));
                return true;
            }
            return false;
        }

        public void SetReceiveHandler(int handlerNum, INetEventHandler handler)
        => _handlerDict[handlerNum] = handler;

        public void SetControlHandler(INetEventHandler handler)
        => _controlHandler.Add(handler);

        public void CancelAll(string connId)
        {
            var toDelete = _queryDict.Keys.Where(k => k.ConnId == connId).ToList();

            for (int i = 0; i < toDelete.Count; i++)
            {
                if (_queryDict.Remove(toDelete[i], out var registery))
                    registery.tcs.TrySetResult(new QueryTaskResult(QueryResultStatus.Cancelled, Array.Empty<byte>()));
            }
        }
        private void ProcessNetInControl(NetInEvent inCon)
        {

            switch (inCon.type)
            {
                case NetInEventType.Hello:
                    foreach (var ch in _controlHandler) ch.OnHello(inCon.ConnId, inCon.data);
                    break;

                case NetInEventType.Disconnect:
                    foreach (var ch in _controlHandler) ch.OnDisconnect(inCon.ConnId, inCon.data);
                    break;

                case NetInEventType.Exception:
                    foreach (var ch in _controlHandler) ch.OnException(inCon.ConnId, inCon.data, inCon.msg);
                    break;
            }
        }

        private void ProcessNetInEvent(NetInEvent inEv)
        {
            Codec c = NetCodec.DecodeWithHeader(inEv.data);
            if (!c.IsPacketValid()) return;

            _handlerDict.TryGetValue(c.HandlerNum, out var handler);


            if (c.IsRespond())
            {
                if (_queryDict.Remove((inEv.ConnId, c.QueryNum), out var registery))
                {
                    registery.tcs.TrySetResult(new QueryTaskResult(QueryResultStatus.Responded, c.Data));
                    registery.SuccAction?.Invoke(c.Data);
                }
                handler?.OnRespond(inEv.ConnId, c.QueryNum, c.Data);

            }
            else if (c.IsQuery()) handler?.OnQuery(inEv.ConnId, c.QueryNum, c.Data);

            else handler?.OnReceive(inEv.ConnId, c.Data);
        }
    }
}
