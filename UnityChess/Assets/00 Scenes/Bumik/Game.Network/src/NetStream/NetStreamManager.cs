
using System;
using System.Collections;
using System.Collections.Generic;
using System.ComponentModel;
using System.Runtime.InteropServices;


namespace Game.Network
{
    public class NetStreamManager
    {
        private Queue<NetOutEvent> _reqDataQueue;
        private Queue<NetOutEvent> _reqControlQueue;
        private int _maxControlPerTick;
        private int _maxDataPerTick;
        private int _totalProcessedEvents;

        public NetStreamManager(int maxControlPerTick, int maxDataPerTick)
        {
            if (maxControlPerTick < 0 || maxDataPerTick < 0) throw new ArgumentException();
            _maxDataPerTick = maxDataPerTick;
            _maxControlPerTick = maxControlPerTick;
            _reqDataQueue = new Queue<NetOutEvent>();
            _reqControlQueue = new Queue<NetOutEvent>();
            _totalProcessedEvents = 0;
        }

        public void Init(NetEventQueue q)
        {
            
        }

        public void Tick(NetEventQueue q)
        {
            for (int i = 0; i < _maxControlPerTick; i++)
            {
                if (_reqControlQueue.Count == 0) break;

                q.OutControlQueue.Enqueue(_reqControlQueue.Dequeue());
                _totalProcessedEvents++;
            }

            for (int i = 0; i < _maxDataPerTick; i++)
            {
                if (_reqDataQueue.Count == 0) break;

                q.OutQueue.Enqueue(_reqDataQueue.Dequeue());
                _totalProcessedEvents++;
            }
        }

        public void Stop()
        {
            
        }

        public string GetState()
        {
            return $"[StreamManager:{this}] \n" + 
                    $"\t Max Process Per Tick     : Control={_maxControlPerTick}, Data={_maxDataPerTick}\n" +
                    $"\t Requested Data Events    : {_reqDataQueue.Count}\n" + 
                    $"\t Requested Control Events : {_reqControlQueue.Count}\n" + 
                    $"\t Total Processed Events   : {_totalProcessedEvents}\n";
        }

        public void Send(int handlerId, int queryNum, ConnId connId, byte[] raw)
        {
            Codec c = (queryNum == 0)? Codec.CreateMessage(handlerId, raw) : Codec.CreateRespond(handlerId, queryNum, raw);         
            var packet = NetCodec.EncodeWithHeader(c);

            _reqDataQueue.Enqueue(NetOutEvent.Send(connId, packet));
        }

        public void Query(int handlerId, int queryNum, ConnId connId, byte[] raw)
        {
            Codec c = Codec.CreateQuery(handlerId, queryNum, raw);         
            var packet = NetCodec.EncodeWithHeader(c);

            _reqDataQueue.Enqueue(NetOutEvent.Send(connId, packet));
        }

        public void BroadCast(int handlerId, int queryNum, byte[] raw)
        {
            Codec c = (queryNum == 0)? Codec.CreateMessage(handlerId, raw) : Codec.CreateRespond(handlerId, queryNum, raw);         
            var packet = NetCodec.EncodeWithHeader(c);
            
            _reqDataQueue.Enqueue(NetOutEvent.BroadCast(ConnId.Default(), packet));
        }

        public void Disconnect(ConnId connId)
        {   
            Codec c = Codec.CreateEmpty();
            var packet = NetCodec.EncodeWithHeader(c);
            
            _reqControlQueue.Enqueue(NetOutEvent.Disconnect(connId, packet));
        }
    }
}