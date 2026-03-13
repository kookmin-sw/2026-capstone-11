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
        public readonly string ConnId;
        public readonly byte[] data;
        public readonly string msg;

        private NetInEvent(NetInEventType InEventType, string ConnectionId, byte[] Data, string Message)
        {
            // NetEvent
            type = InEventType;
            ConnId = ConnectionId;

            // Packet With Header
            data = Data;

            // Debug
            msg = Message;
        }    
    
        // public static NetInEvent Query(string connId, byte[] data, string msg = "Get Query") 
        //     => new (NetInEventType.Query, connId, data, msg);
        public static NetInEvent Receive(string connId, byte[] data, string msg = "Received") 
            => new (NetInEventType.Receive, connId, data, msg);

        // public static NetInEvent Respond(string connId, byte[] data, string msg = "Respond")
        //     => new (NetInEventType.Respond, connId, data, msg);

        // public static NetInEvent Query(string connId, byte[] data, string msg = "Query Received")
        //     => new (NetInEventType.Query, connId, data, msg);

        public static NetInEvent Disconnect(string connId, byte[] data, string msg = "Disconnect") 
            => new (NetInEventType.Disconnect, connId, data, msg);
        
        public static NetInEvent Hello(string connId, byte[] data, string msg = "Hello") 
            => new (NetInEventType.Hello, connId, data, msg);
        
        public static NetInEvent Exception(string connId, byte[] data, string msg = "Exception") 
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
        public readonly string ConnId;
        public readonly byte[] data;
        public readonly string msg;

        private NetOutEvent(NetOutEventType t, string id, byte[] d, string m)
        {
            type = t;
            ConnId = id;
            data = d;
            msg = m;
        }


        public static NetOutEvent Send(string connId, byte[] data, string msg = "Send") 
            => new (NetOutEventType.Send, connId, data, msg);
        public static NetOutEvent BroadCast(string connId, byte[] data, string msg = "BroadCast") 
            => new (NetOutEventType.BroadCast, connId, data, msg);
        public static NetOutEvent Disconnect(string connId, byte[] data, string msg = "Disconnect") 
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