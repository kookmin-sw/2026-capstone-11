
using System.Runtime.InteropServices;

namespace Game.Network
{
    public enum QueryResultStatus
    {
        Responded,
        TimeOut,
        Cancelled
    }

    public readonly struct QueryTaskResult
    {

        public QueryResultStatus Status {get;}
        public byte[] AnswerRaw {get;}

        public QueryTaskResult(QueryResultStatus s, byte[] answer_raw)
        {
            Status = s;
            AnswerRaw = answer_raw;
        }  

        public static QueryTaskResult CancelledResult => new (QueryResultStatus.Cancelled, Array.Empty<byte>());  

        public bool IsResponded => Status == QueryResultStatus.Responded;
        public bool IsTimeOut => Status == QueryResultStatus.TimeOut;
        public bool IsCancelled => Status == QueryResultStatus.Cancelled;
    }

    public struct QueryRegistery
    {
        public TaskCompletionSource<QueryTaskResult> tcs;
        public readonly int QueryNum;
        public readonly long ExpireTimeMs; 
        // public Action<ConnId, byte[]>? SuccAction;
        // public Action<ConnId>? FailAction; 
        public Action<ConnId, QueryTaskResult>? CallBack;


        public static QueryRegistery CreateQueryRegistery(int queryNum, long expireTimeMs)
        {
            var registery = new QueryRegistery(queryNum, expireTimeMs);
            return registery;
        }

        public static QueryRegistery CreateQueryRegistery(int queryNum, long expireTimeMs, TaskCompletionSource<QueryTaskResult> tcs)
        {
            var registery = new QueryRegistery(queryNum, expireTimeMs, tcs);
            return registery;
        }

        // public static QueryRegistery CreateQueryRegistery(int queryNum, long expireTimeMs, Action<ConnId, byte[]>? respondedAction = null, Action<ConnId>? timeOutAction = null)
        // {
        //     var registery = new QueryRegistery(queryNum, expireTimeMs);
        //     registery.SuccAction = respondedAction;
        //     registery.FailAction = timeOutAction;
        //     return registery;
        // }
        public static QueryRegistery CreateQueryRegistery(int queryNum, long expireTimeMs, Action<ConnId, QueryTaskResult>? callBack)
        {
            var registery = new QueryRegistery(queryNum, expireTimeMs);
            registery.CallBack = callBack;
            return registery;
        }  

        private QueryRegistery(int queryNum, long expireTimeMs)
        {
            tcs = new TaskCompletionSource<QueryTaskResult>();
            QueryNum = queryNum;
            ExpireTimeMs = expireTimeMs;
            // SuccAction = null;
            // FailAction = null;
            CallBack = null;
        }

        private QueryRegistery(int queryNum, long expireTimeMs, TaskCompletionSource<QueryTaskResult> taskCompSource)
        {
            tcs = taskCompSource;
            QueryNum = queryNum;
            ExpireTimeMs = expireTimeMs;
            // SuccAction = null;
            // FailAction = null;
            CallBack = null;
        }

    }
}