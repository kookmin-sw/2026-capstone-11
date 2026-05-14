

using System;
using System.Data.Common;
using System.Diagnostics.Contracts;
using System.Dynamic;

namespace Game.Network.Service
{
    public class RequestSendModule : IServiceModule
    {
        private IHostReader _host;
        private INetAPI _net;

        public void Init(ServiceContext_V2 context)
        {
            _host = context.Host;
            _net = context.Net;
        }


        public void SendRequest<TReq, TRsp>(
            TReq data,
            IPacketMeta<TReq> meta,
            IPacketCodec<TReq> codec,
            Action<ConnId, TRsp> onService,
            Action<TRsp> onUser,
            Action<string> onFail,
            IPacketMeta<TRsp> rsp_meta,
            IPacketCodec<TRsp> rsp_codec,
            long expireTimeMs
        )
        {
            PacketWrapper wrapper = PacketWrapper.MakeWrap(data, meta, codec);
            RespondCallBack<TRsp> onRespond = RespondCallBack<TRsp>.Create(onService, onUser, onFail, rsp_meta, rsp_codec);

            _ = _net.AsyncRequestQuery(
                NetEventHandlerId.Constant.RequestReceiver,
                _host.connId,
                wrapper.Raw,
                expireTimeMs,
                onRespond.CallBack
                );
        }

        private record struct RespondCallBack<T>
        {
            public Action<ConnId, T> onService;
            public Action<T> onUser;
            public Action<string> onFail;
            public IPacketMeta<T> meta;
            public IPacketCodec<T> codec;

            public static RespondCallBack<T> Create(Action<ConnId, T> service, Action<T> user, Action<string> fail, IPacketMeta<T> rsp_meta, IPacketCodec<T> rsp_codec)
            {
                var callback = new RespondCallBack<T>();
                callback.onService = service;
                callback.onUser = user;
                callback.onFail = fail;
                callback.meta = rsp_meta;
                callback.codec = rsp_codec;

                return callback;
            }

            public void CallBack(ConnId id, QueryTaskResult result)
            {
                if (result.IsResponded)
                {
                    PacketWrapper wrapper = new(result.AnswerRaw);
                    T? rsp = wrapper.Unwrap(meta, codec);

                    if (rsp != null)
                    {
                        onService.Invoke(id,rsp);
                        onUser.Invoke(rsp);
                        return;
                    }

                    FailPacket? fail = wrapper.Unwrap(FailPacket.Meta, FailPacket.Codec);
                    if (fail != null)
                    {
                        onFail.Invoke(fail.msg);
                        return;
                    }
                    else
                    {
                        onFail.Invoke(FailPacket.GetMessage(FailPacket.FailType.FailDeserialize));
                        return;
                    }
                }

                if (result.IsCancelled)
                {
                    onFail.Invoke("Cancelled");
                }

                if (result.IsTimeOut)
                {
                    onFail.Invoke("Time Out");
                }
            }


        }





    }
}