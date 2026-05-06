
using System;

namespace Game.Network.Service
{
    public class DispatcherRegistery
    {
        public byte[] Handle(ConnId Id, byte[] data)
            => handle(Id, data);

        private Func<ConnId, byte[], byte[]> handle;

        public DispatcherRegistery(Func<ConnId, byte[], byte[]> fn)
        {
            handle = fn;
        } 
        private static byte[] DefaultHandle(ConnId Id, byte[] data) { return Array.Empty<byte>();}
        public static Func<ConnId, byte[], byte[]> Default => DefaultHandle;

        
    }
}