

using System.Collections.Concurrent;
using System.Diagnostics;
using System.Text;

namespace Game.Network
{
    public class NetEventManger
    {
        private Dictionary<int, INetReceiveEventHandler> _handlerDict;
        private HashSet<INetControlEventHandler> _controlHandler;
        private Dictionary<(ConnId id, int queryNum), QueryRegistery> _queryDict;
        private int _maxDataPerTick;
        private int _maxControlPerTick;
        private int _query_seq;

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



        // for CheckTimeOut() cache
        private readonly List<(ConnId, int)> _removeList = new();
        private static QueryTaskResult _timeOutResult = new QueryTaskResult(QueryResultStatus.TimeOut, Array.Empty<byte>());
        private static QueryTaskResult _cancelResult = new QueryTaskResult(QueryResultStatus.Cancelled, Array.Empty<byte>());


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
                msg += $"\t [Registed Query] - ({item.Key.id}, {item.Key.queryNum})\n";
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
                    registery.tcs.TrySetResult(_timeOutResult);
                    //registery.FailAction?.Invoke(key.Item1);
                    registery.CallBack?.Invoke(key.Item1, _timeOutResult);
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



        public (int, Task<QueryTaskResult>) RegisterQueryTask(ConnId connId, long expireTimeMs)
        {
            var registery = QueryRegistery.CreateQueryRegistery(_query_seq, GameTime.GetNow() + expireTimeMs);
            _queryDict.Add((connId, _query_seq), registery);
            _query_seq++;

            return (registery.QueryNum, registery.tcs.Task);
        }
        public (int, Task<QueryTaskResult>) RegisterQueryTask(ConnId connId, long expireTimeMs, TaskCompletionSource<QueryTaskResult> tcs)
        {
            var registery = QueryRegistery.CreateQueryRegistery(_query_seq, GameTime.GetNow() + expireTimeMs, tcs);
            _queryDict.Add((connId, _query_seq), registery);
            _query_seq++;

            return (registery.QueryNum, registery.tcs.Task);
        }

        // public (int, Task<QueryTaskResult>) RegisterQueryTask(ConnId connId, long expireTimeMs, Action<ConnId, byte[]>? succAction = null, Action<ConnId>? failAction = null)
        // {
        //     var registery = QueryRegistery.CreateQueryRegistery(_query_seq, GameTime.GetNow() + expireTimeMs, succAction, failAction);
        //     _queryDict.Add((connId, _query_seq), registery);
        //     _query_seq++;

        //     return (registery.QueryNum, registery.tcs.Task);
        // }

        public (int, Task<QueryTaskResult>) RegisterQueryTask(ConnId connId, long expireTimeMs, Action<ConnId, QueryTaskResult>? callBack)
        {
            var registery = QueryRegistery.CreateQueryRegistery(_query_seq, GameTime.GetNow() + expireTimeMs, callBack);
            _queryDict.Add((connId, _query_seq), registery);
            _query_seq++;

            return (registery.QueryNum, registery.tcs.Task);
        }

        public bool TryCancelQuery(ConnId connId, int queryNum)
        {
            if (queryNum == 0) return false;

            if (_queryDict.Remove((connId, queryNum), out var registery))
            {
                registery.tcs.TrySetResult(_cancelResult);
                registery.CallBack?.Invoke(connId, _cancelResult);
                return true;
            }
            return false;
        }

        public void SetReceiveHandler(INetReceiveEventHandler handler)
        => _handlerDict[handler.HandlerId] = handler;

        public void SetControlHandler(INetControlEventHandler handler)
        => _controlHandler.Add(handler);

        public void CancelAll(ConnId connId)
        {
            var toDelete = _queryDict.Keys.Where(k => k.id == connId).ToList();

            for (int i = 0; i < toDelete.Count; i++)
            {
                if (_queryDict.Remove(toDelete[i], out var registery))
                { registery.tcs.TrySetResult(_cancelResult); registery.CallBack?.Invoke(connId, _cancelResult); }
            }
        }
        private void ProcessNetInControl(NetInEvent inCon)
        {

            switch (inCon.type)
            {
                case NetInEventType.Hello:
                    foreach (var ch in _controlHandler) ch.OnHello(inCon.connId, inCon.data);
                    break;

                case NetInEventType.Disconnect:
                    foreach (var ch in _controlHandler) ch.OnDisconnect(inCon.connId, inCon.data);
                    break;

                case NetInEventType.Exception:
                    foreach (var ch in _controlHandler) ch.OnException(inCon.connId, inCon.data, inCon.msg);
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
                if (_queryDict.Remove((inEv.connId, c.QueryNum), out var registery))
                {
                    var result = new QueryTaskResult(QueryResultStatus.Responded, c.Data);
                    registery.tcs.TrySetResult(result);
                    registery.CallBack?.Invoke(inEv.connId, result);
                    //registery.SuccAction?.Invoke(inEv.connId, c.Data);
                }
                handler?.OnRespond(inEv.connId, c.QueryNum, c.Data);

            }
            else if (c.IsQuery()) handler?.OnQuery(inEv.connId, c.QueryNum, c.Data);

            else handler?.OnReceive(inEv.connId, c.Data);
        }
    }
}
