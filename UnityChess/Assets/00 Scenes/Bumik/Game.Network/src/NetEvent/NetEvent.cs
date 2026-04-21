using System.Collections.Concurrent;

namespace Game.Network
{
    public enum NetInEventType
    {
        // Data Event
        Receive,

        // Control Event
        Disconnect,
        Hello,
        Exception
    }

    public readonly struct NetInEvent
    {
        public readonly NetInEventType type;
        public readonly ConnId connId;
        public readonly byte[] data;
        public readonly string msg;

        private NetInEvent(NetInEventType InEventType, ConnId ConnectionId, byte[] Data, string Message)
        {
            // NetEvent
            type = InEventType;
            connId = ConnectionId;

            // Packet With Header
            data = Data;

            // Debug
            msg = Message;
        }    
    
        // public static NetInEvent Query(string connId, byte[] data, string msg = "Get Query") 
        //     => new (NetInEventType.Query, connId, data, msg);
        public static NetInEvent Receive(ConnId connId, byte[] data, string msg = "Received") 
            => new (NetInEventType.Receive, connId, data, msg);

        // public static NetInEvent Respond(string connId, byte[] data, string msg = "Respond")
        //     => new (NetInEventType.Respond, connId, data, msg);

        // public static NetInEvent Query(string connId, byte[] data, string msg = "Query Received")
        //     => new (NetInEventType.Query, connId, data, msg);

        public static NetInEvent Disconnect(ConnId connId, byte[] data, string msg = "Disconnect") 
            => new (NetInEventType.Disconnect, connId, data, msg);
        
        public static NetInEvent Hello(ConnId connId, byte[] data, string msg = "Hello") 
            => new (NetInEventType.Hello, connId, data, msg);
        
        public static NetInEvent Exception(ConnId connId, byte[] data, string msg = "Exception") 
            => new (NetInEventType.Exception, connId, data, msg);
    }


    public enum NetOutEventType
    {
        // Data Event
        Send,
        BroadCast,

        // Control Event
        Disconnect,
    }

    public readonly struct NetOutEvent
    {
        public readonly NetOutEventType type;
        public readonly ConnId ConnId;
        public readonly byte[] data;
        public readonly string msg;

        private NetOutEvent(NetOutEventType t, ConnId id, byte[] d, string m)
        {
            type = t;
            ConnId = id;
            data = d;
            msg = m;
        }


        public static NetOutEvent Send(ConnId connId, byte[] data, string msg = "Send") 
            => new (NetOutEventType.Send, connId, data, msg);
        public static NetOutEvent BroadCast(ConnId connId, byte[] data, string msg = "BroadCast") 
            => new (NetOutEventType.BroadCast, connId, data, msg);
        public static NetOutEvent Disconnect(ConnId connId, byte[] data, string msg = "Disconnect") 
            => new (NetOutEventType.Disconnect, connId, data, msg);
    }



    public sealed class NetEventQueue
    {
        // For Data
        public ConcurrentQueue<NetInEvent> InQueue { get; }
        public ConcurrentQueue<NetOutEvent> OutQueue { get; }

        // For Control
        public ConcurrentQueue<NetInEvent> InControlQueue {get;}
        public ConcurrentQueue<NetOutEvent> OutControlQueue {get;}

        public static NetEventQueue CreateNetworkEventQueue()
        {
            return new NetEventQueue();
        }
        private NetEventQueue()
        {
            InQueue = new ConcurrentQueue<NetInEvent>();
            OutQueue = new ConcurrentQueue<NetOutEvent>();

            InControlQueue = new ConcurrentQueue<NetInEvent>();
            OutControlQueue = new ConcurrentQueue<NetOutEvent>();
        }
    }
}