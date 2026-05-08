using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Globalization;
using System.IO.Compression;
using Game.Network.Service;


namespace Game.Network.Service
{

    public class DispatchMap
    {
        private Dictionary<int, DispatchRegistery> _dispatchMap = new();

        public void Register<T>(IPacketMeta<T> meta, DispatchRegistery registery)
        {
            _dispatchMap[meta.Id] = registery;
        }

        public void Register<TParam, TResult>(Func<ConnId, TParam, TResult?> fn, 
                                                        IPacketMeta<TParam> Pmeta, IPacketCodec<TParam> Pcodec, 
                                                        IPacketMeta<TResult> Rmeta, IPacketCodec<TResult> Rcodec)
        {
            _dispatchMap[Pmeta.Id] = DispatchRegistery.MakeRegistery(fn, Pmeta, Pcodec, Rmeta, Rcodec);
        }

        public bool TryDispatch(int id, out DispatchRegistery registery)
        => _dispatchMap.TryGetValue(id, out registery);

        public void Deregister(int id)
        => _dispatchMap.Remove(id);

    }

    public class DispatchRegistery
    {
        public PacketWrapper Handle(ConnId Id, PacketWrapper wrapper)
            => _handle(Id, wrapper);
        private Func<ConnId, PacketWrapper, PacketWrapper> _handle;
        public DispatchRegistery(Func<ConnId, PacketWrapper, PacketWrapper> fn)
        {
            _handle = fn;
        }
        public static DispatchRegistery MakeRegistery<TParam, TResult>(Func<ConnId, TParam, TResult?> fn, 
                                                        IPacketMeta<TParam> Pmeta, IPacketCodec<TParam> Pcodec, 
                                                        IPacketMeta<TResult> Rmeta, IPacketCodec<TResult> Rcodec)
        {
            return new DispatchRegistery((id, wrapper) =>
            {
                TParam? packet = wrapper.Unwrap(Pmeta, Pcodec);
                if (packet == null)
                    return PacketWrapper.MakeWrap(new FailPacket(FailPacket.FailType.FailDeserialize), FailPacket.Meta, FailPacket.Codec);

                TResult? result = fn(id, packet);

                if (result == null) 
                    return PacketWrapper.MakeWrap(new FailPacket(FailPacket.FailType.ServerFault), FailPacket.Meta, FailPacket.Codec);
                
                return PacketWrapper.MakeWrap(result, Rmeta, Rcodec);
            });
        }


        private static PacketWrapper DefaultHandle(ConnId Id, PacketWrapper data) { return PacketWrapper.Empty; }
        public static Func<ConnId, PacketWrapper, PacketWrapper> Default => DefaultHandle;
    }
}