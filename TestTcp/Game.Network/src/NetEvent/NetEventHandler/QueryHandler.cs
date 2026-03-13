
using System.IO.Compression;

namespace Game.Network
{
    // public class QueryManager
    // {
    //     private Dictionary<(string ConnId, int queryNum), QueryRegistery> _queryDict;
    //     private int _seq;
        


    //     public (int, Task<QueryTaskResult>) RegisterQueryTask(string ConnId, int timer_ms = 3000)  
    //     {
    //         var registery = QueryRegistery.CreateQueryRegistery(_seq, timer_ms);
    //         _queryDict.Add((ConnId, _seq), registery);
    //         _seq++;

    //         return (registery.QueryNum, registery.tcs.Task);
    //     }

    //     public (int, Task<QueryTaskResult>) RegisterQueryTask(string ConnId, Action<byte[]>? succAction = null, Action<byte[]>? failAction = null, int timer_ms = 3000)  
    //     {
    //         var registery = QueryRegistery.CreateQueryRegistery(_seq, timer_ms, succAction, failAction);
    //         _queryDict.Add((ConnId, _seq), registery);
    //         _seq++;

    //         return (registery.QueryNum, registery.tcs.Task);
    //     }

    //     public bool TryCancelQuery(string ConnId, int queryNum)
    //     {
    //         if (queryNum == 0) return false;

    //         if (_queryDict.Remove((ConnId, queryNum), out var registery))
    //         {
    //             registery.tcs.TrySetResult(new QueryTaskResult(false, Array.Empty<byte>()));
    //             return true;
    //         }
    //         return false;
    //     }

    //     public QueryManager()
    //     {
    //         _queryDict = new Dictionary<(string ConnId, int queryNum), QueryRegistery>();
    //         _seq = 1;
    //     }

    // }


}